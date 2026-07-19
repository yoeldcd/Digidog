"""Manual and model-backed picture description workflows."""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from collections.abc import Callable
from typing import Any

import requests

from brain.application.knowledge.runtime.config_store import resolve_secret
from brain.application.pictures.config import load_pictures_config
from brain.application.knowledge.models.dtos.runtime_config import PictureGuidanceConfigDTO
from brain.infrastructure.pictures.models import PictureRecord
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.runtime.paths import get_pictures_dir


DEFAULT_DESCRIPTION_PROMPT = (
    "Describe this image for a personal knowledge index. Identify the main subjects, "
    "setting, activity, visible objects, colors, mood, and any legible text. Be factual, "
    "concise, and useful for semantic search. Do not infer sensitive attributes."
)

PictureDescriptionProgress = Callable[[int, int, PictureRecord], None]
"""Callback invoked before one model-backed picture description."""


def describe_registered_pictures(
    *,
    only_undescribed: bool,
    prompt: str = "",
    repository: PictureRepository | None = None,
    pictures_root: Path | None = None,
    on_progress: PictureDescriptionProgress | None = None,
) -> dict[str, Any]:
    """Describe active pictures in deterministic order while isolating per-file failures."""
    repo = repository or PictureRepository()
    records = repo.list(active_only=True)
    candidates = [record for record in records if not only_undescribed or not record.description.strip()]
    described: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    for index, record in enumerate(candidates, start=1):
        if on_progress is not None:
            on_progress(index, len(candidates), record)
        try:
            updated = set_picture_description(
                picture_id=record.id,
                prompt=prompt,
                repository=repo,
                pictures_root=pictures_root,
            )
        except Exception as exc:
            errors.append({"id": record.id, "relative_path": record.relative_path, "error": str(exc)})
            continue
        described.append(updated.as_mapping())

    return {
        "ok": not errors,
        "mode": "undescribed" if only_undescribed else "all",
        "total": len(records),
        "requested": len(candidates),
        "described": len(described),
        "failed": len(errors),
        "skipped": len(records) - len(candidates),
        "pictures": described,
        "errors": errors,
    }


def set_picture_description(
    picture_id: str,
    description: str = "",
    prompt: str = "",
    repository: PictureRepository | None = None,
    pictures_root: Path | None = None,
) -> PictureRecord:
    """Persist a manual description or generate one with the configured vision model."""
    repo = repository or PictureRepository()
    record = repo.get(picture_id=picture_id)
    if record is None or not record.active:
        raise ValueError(f"Unknown active picture `{picture_id}`.")

    normalized_description = description.strip()
    source = "manual"
    if not normalized_description:
        root = (pictures_root or get_pictures_dir()).resolve()
        normalized_description = _generate_description(
            picture_path=(root / record.relative_path).resolve(),
            mime_type=record.mime_type,
            prompt=prompt.strip() or DEFAULT_DESCRIPTION_PROMPT,
        )
        source = "image_model"
    described_at = datetime.now().astimezone().isoformat()
    return repo.update_description(
        picture_id=record.id,
        description=normalized_description,
        source=source,
        described_at=described_at,
    )


def _generate_description(picture_path: Path, mime_type: str, prompt: str) -> str:
    """Call the configured OpenAI-compatible img2text model for one image."""
    pictures_config = load_pictures_config()
    config = pictures_config.image_model
    if not config.enabled:
        raise ValueError("Picture image_model is disabled; provide a manual description or enable it in brain_configs.")
    api_key = resolve_secret(config.api_key)
    if not api_key or api_key.startswith("$"):
        raise ValueError("Picture image_model API key is unavailable.")
    encoded = base64.b64encode(picture_path.read_bytes()).decode("ascii")
    guided_prompt = build_guided_description_prompt(prompt=prompt, guidance=pictures_config.guidance)
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": guided_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                ],
            },
        ],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    response = requests.post(
        f"{config.base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    content = str(data["choices"][0]["message"]["content"]).strip()
    if not content:
        raise ValueError("Picture image_model returned an empty description.")
    return content


def build_guided_description_prompt(prompt: str, guidance: PictureGuidanceConfigDTO) -> str:
    """
    Compose one img2text request with environment-specific recognition rules.

    Args:
        prompt: Base description instruction supplied by the command or default workflow.
        guidance: Known character descriptions and semantic tag criteria.

    Returns:
        Prompt enriched with evidence-bound recognition guidance when configured.
    """
    sections: list[str] = []
    if guidance.characters:
        characters = "\n".join(
            f"- {name}: {description.strip()}"
            for name, description in sorted(guidance.characters.items(), key=lambda item: item[0].casefold())
            if description.strip()
        )
        if characters:
            sections.append(f"Known characters:\n{characters}")
    if guidance.tags:
        tags = "\n".join(
            f"- {name}: {description.strip()}"
            for name, description in sorted(guidance.tags.items(), key=lambda item: item[0].casefold())
            if description.strip()
        )
        if tags:
            sections.append(f"Semantic tags:\n{tags}")
    if not sections:
        return prompt
    recognition_rules = (
        "Recognition rules:\n"
        "- Use the exact configured character name instead of a generic subject label only when visible traits clearly match.\n"
        "- Apply configured semantic tag names explicitly when their observable criteria are satisfied.\n"
        "- Never force a configured identity or tag; state uncertainty when evidence is insufficient.\n"
        "- Do not infer hidden relationships, emotions, or sensitive attributes beyond visible evidence."
    )
    guidance_text = "\n\n".join(sections)
    return f"{prompt.strip()}\n\nEnvironment-specific vision guidance:\n{guidance_text}\n\n{recognition_rules}"
