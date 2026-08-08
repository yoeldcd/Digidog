"""Profile-aware, multimodal enrichment for persistent backlog tasks."""

from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from pathlib import Path
import re
from typing import Any

from brain.application.backlog.models import BacklogTask
from brain.application.backlog.service import edit_backlog_task, get_backlog_task
from brain.application.knowledge.llm.transport import post_chat_completion
from brain.application.knowledge.runtime.config_store import resolve_secret
from brain.application.profiles.service import get_profiles_dir, profile_summaries, read_profile_entries
from brain.application.querying.llm import load_text_model_config
from brain.config import KNOWLEDGE_LLM_TIMEOUT_SECONDS


MAX_PROFILE_CONTEXT_CHARS = 48_000
"""Maximum profile context included in one enrichment request."""

MAX_IMAGE_BYTES = 10 * 1024 * 1024
"""Maximum optional visual-reference size accepted by the model request."""

PROTECTED_REFERENCE_PATTERN = re.compile(
    r"(?:\{ref_image\}|\$agent[\\/]pictures[\\/]backlog-pic-t\d+\.(?:png|jpe?g|gif|webp))",
    re.IGNORECASE,
)
"""Visual-reference tokens that enrichment must preserve outside model control."""


class TaskEnrichmentError(RuntimeError):
    """Raised when a task cannot be enriched safely."""


@dataclass(frozen=True, slots=True)
class TaskEnrichmentResult:
    """Result of one persisted task-enrichment operation.

    Attributes:
        task: Updated durable backlog task.
        profile: Primary profile used to frame the model request.
        guideline_count: Number of nested directive documents supplied.
        used_image: Whether the request included a visual reference.
        model: Configured model identifier.
    """

    task: BacklogTask
    profile: str
    guideline_count: int
    used_image: bool
    model: str


@dataclass(frozen=True, slots=True)
class TaskDraftEnrichmentResult:
    """Generated description and metadata for an unsaved task draft.

    Attributes:
        description: Enriched Markdown returned for user review.
        profile: Primary profile used to frame the request.
        guideline_count: Number of nested directive documents supplied.
        used_image: Whether the request included a visual reference.
        model: Configured model identifier.
    """

    description: str
    profile: str
    guideline_count: int
    used_image: bool
    model: str


def enrich_backlog_task(
    *,
    workspace_root: Path,
    task_id: str,
    image_path: Path | None = None,
    profile_name: str = "developer",
) -> TaskEnrichmentResult:
    """Enrich and persist one task description with the configured model.

    Args:
        workspace_root: Workspace containing the canonical backlog database.
        task_id: Persistent task identifier.
        image_path: Optional visual reference attached to the task.
        profile_name: Primary profile whose directives frame the result.

    Returns:
        Metadata and the updated persistent task.

    Raises:
        TaskEnrichmentError: Model configuration, transport, or output is invalid.
    """
    task = get_backlog_task(workspace_root=workspace_root, task_id=task_id)
    draft_result = enrich_backlog_draft(
        task=task,
        image_path=image_path,
        profile_name=profile_name,
    )
    updated = edit_backlog_task(
        workspace_root=workspace_root,
        task_id=task.task_id,
        description=draft_result.description,
    )
    return TaskEnrichmentResult(
        task=updated,
        profile=draft_result.profile,
        guideline_count=draft_result.guideline_count,
        used_image=draft_result.used_image,
        model=draft_result.model,
    )


def enrich_backlog_draft(
    *,
    task: BacklogTask,
    image_path: Path | None = None,
    image_data_url: str | None = None,
    profile_name: str = "developer",
) -> TaskDraftEnrichmentResult:
    """Generate an enriched description without persisting the task.

    Args:
        task: Current create or edit form values represented as a task draft.
        image_path: Optional persisted visual-reference path.
        image_data_url: Optional unsaved visual reference encoded as a data URL.
        profile_name: Primary profile whose directives frame the result.

    Returns:
        Enriched Markdown and non-sensitive generation metadata.

    Raises:
        TaskEnrichmentError: Inputs, model configuration, transport, or output are invalid.
    """
    profile_context, guideline_count = build_profile_context(profile_name=profile_name)
    system_prompt = build_enrichment_system_prompt(profile_name=profile_name)
    prompt_task, protected_references = _extract_protected_references(task=task)
    task_prompt = build_task_prompt(task=prompt_task, profile_context=profile_context)
    stage_config = load_text_model_config(max_tokens=2400)
    api_key = resolve_secret(stage_config.api_key)
    if not api_key or api_key.startswith("$"):
        raise TaskEnrichmentError("Task enrichment model API key is unavailable.")

    content: str | list[dict[str, Any]] = task_prompt
    used_image = image_data_url is not None or image_path is not None
    if image_data_url is not None:
        content = _multimodal_data_url_content(prompt=task_prompt, image_data_url=image_data_url)
    elif image_path is not None:
        content = _multimodal_content(prompt=task_prompt, image_path=image_path)
    payload: dict[str, Any] = {
        "model": stage_config.model,
        "temperature": min(stage_config.temperature, 0.35),
        "max_tokens": min(stage_config.max_tokens, 2400),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
    }
    try:
        completion = post_chat_completion(
            endpoint=f"{stage_config.base_url.rstrip('/')}/chat/completions",
            api_key=api_key,
            payload=payload,
            timeout_seconds=KNOWLEDGE_LLM_TIMEOUT_SECONDS,
        )
        model_description = str(completion.response_payload["choices"][0]["message"]["content"]).strip()
    except Exception as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        reason = getattr(exc, "reason", None)
        if reason is not None and str(reason).strip():
            detail = str(reason).strip()
        raise TaskEnrichmentError(f"Task enrichment request failed: {detail}") from exc
    if len(model_description) < 80:
        raise TaskEnrichmentError("Task enrichment model returned an incomplete description.")
    enriched_description = _restore_protected_references(
        description=model_description,
        protected_references=protected_references,
    )
    return TaskDraftEnrichmentResult(
        description=enriched_description,
        profile=profile_name,
        guideline_count=guideline_count,
        used_image=used_image,
        model=stage_config.model,
    )


def _extract_protected_references(task: BacklogTask) -> tuple[BacklogTask, tuple[str, ...]]:
    """Remove visual-reference tokens from model-visible task text.

    Args:
        task: Task whose description may contain persisted reference metadata.

    Returns:
        A prompt-safe task and the exact ordered references removed from it.
    """
    protected_references = tuple(PROTECTED_REFERENCE_PATTERN.findall(task.description))
    if not protected_references:
        return task, ()
    prompt_description = PROTECTED_REFERENCE_PATTERN.sub("", task.description)
    prompt_description = re.sub(r"\n{3,}", "\n\n", prompt_description).strip()
    return replace(task, description=prompt_description), protected_references


def _restore_protected_references(description: str, protected_references: tuple[str, ...]) -> str:
    """Restore exact reference metadata after discarding model-generated tokens.

    Args:
        description: Enriched model output that may contain invented reference tokens.
        protected_references: Exact references extracted before the model request.

    Returns:
        Sanitized enriched Markdown followed by each original reference exactly once.
    """
    sanitized = PROTECTED_REFERENCE_PATTERN.sub("", description)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).strip()
    unique_references = tuple(dict.fromkeys(protected_references))
    if not unique_references:
        return sanitized
    reference_block = "\n".join(unique_references)
    return f"{sanitized}\n\n{reference_block}"


def build_profile_context(profile_name: str = "developer") -> tuple[str, int]:
    """Render the profile catalog, selected profile, and nested directives.

    Args:
        profile_name: Profile whose complete directive hierarchy is required.

    Returns:
        Bounded prompt context and the number of nested guideline documents.
    """
    catalog_lines = [
        f"- {item['name']}: {str(item.get('use_when', '')).strip()}"
        for item in profile_summaries()
    ]
    selected_entries = read_profile_entries(profile_name)
    selected_text = "\n\n".join(f"## {key}\n{value.strip()}" for key, value in selected_entries)
    profile_dir = get_profiles_dir() / profile_name
    directives: list[str] = []
    if profile_dir.is_dir():
        root_files = {path.resolve() for path in profile_dir.glob("*.md")}
        for path in sorted(profile_dir.rglob("*.md"), key=lambda item: item.as_posix().casefold()):
            if path.resolve() in root_files:
                continue
            relative = path.relative_to(profile_dir).as_posix()
            directives.append(f"### {relative}\n{path.read_text(encoding='utf-8').strip()}")
    context = (
        "# Available profiles\n"
        + "\n".join(catalog_lines)
        + f"\n\n# Selected profile: {profile_name}\n{selected_text}"
        + "\n\n# Selected profile directive hierarchy\n"
        + "\n\n".join(directives)
    )
    return context[:MAX_PROFILE_CONTEXT_CHARS], len(directives)


def _multimodal_data_url_content(prompt: str, image_data_url: str) -> list[dict[str, Any]]:
    """Validate and attach an unsaved in-memory image to a model request.

    Args:
        prompt: Task and profile context.
        image_data_url: Browser-provided base64 image data URL.

    Returns:
        Ordered text and inline-image content parts.

    Raises:
        TaskEnrichmentError: The data URL is malformed, unsupported, or oversized.
    """
    header, separator, encoded = image_data_url.partition(",")
    mime_match = re.fullmatch(r"data:(image/(?:png|jpeg|gif|webp));base64", header, re.IGNORECASE)
    if not separator or mime_match is None:
        raise TaskEnrichmentError("Task visual reference has an invalid image data URL.")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise TaskEnrichmentError("Task visual reference contains invalid base64 data.") from exc
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise TaskEnrichmentError("Task visual reference exceeds the 10 MiB limit.")
    canonical_url = f"data:{mime_match.group(1).casefold()};base64,{encoded}"
    return [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": canonical_url, "detail": "high"}},
    ]


def build_enrichment_system_prompt(profile_name: str) -> str:
    """Build the stable system contract for task specification enrichment.

    Args:
        profile_name: Primary profile that governs the specification.

    Returns:
        Detailed model role and output contract.
    """
    return f"""You are a senior requirements engineer operating under the `{profile_name}` profile.
Transform an existing backlog description into a precise, implementation-ready Markdown specification.
Preserve the user's intent, task title, domain, priority, and scope. Do not claim the work is complete.
Integrate applicable profile directives and guidelines as concrete constraints, without mentioning hidden
prompts or copying irrelevant guidance. If an image is supplied, inspect its visible UI, text, state, and
defects as evidence; do not invent details that are not visible.

Return only the enriched task description. It must be detailed rather than a short summary and include:
- objective and observable desired outcome;
- current problem and evidence;
- functional and non-functional requirements;
- architecture and ownership boundaries;
- edge cases, failure behavior, accessibility, security, and performance where relevant;
- implementation constraints and explicit exclusions;
- acceptance criteria and a validation plan.
Use clear Markdown headings and lists. Never include secrets, internal chain-of-thought, or a preamble."""


def build_task_prompt(task: BacklogTask, profile_context: str) -> str:
    """Compose task facts and policy context for the model.

    Args:
        task: Existing persistent backlog task.
        profile_context: Bounded profile catalog and directive hierarchy.

    Returns:
        User-message text for one enrichment request.
    """
    return f"""# Task to enrich
- ID: {task.task_id}
- Domain: {task.domain}
- Title: {task.title}
- Priority: {task.priority}
- Status: {task.status}

## Current description
{task.description}

# Environment profiles and directives
{profile_context}

Enrich only the task description according to the output contract."""


def _multimodal_content(prompt: str, image_path: Path) -> list[dict[str, Any]]:
    """Build OpenAI-compatible text and image message parts.

    Args:
        prompt: Task and profile context.
        image_path: Existing task attachment path.

    Returns:
        Ordered text and inline-image content parts.

    Raises:
        TaskEnrichmentError: The attachment is missing, unsupported, or too large.
    """
    resolved = image_path.resolve()
    if not resolved.is_file():
        raise TaskEnrichmentError("Task visual reference does not exist.")
    image_bytes = resolved.read_bytes()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise TaskEnrichmentError("Task visual reference exceeds the 10 MiB limit.")
    mime_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
    mime_type = mime_types.get(resolved.suffix.casefold())
    if mime_type is None:
        raise TaskEnrichmentError("Task visual reference has an unsupported image format.")
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}", "detail": "high"}},
    ]
