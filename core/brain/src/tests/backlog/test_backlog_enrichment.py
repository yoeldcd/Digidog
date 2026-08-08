"""Write-free contracts for profile-aware backlog task enrichment."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from brain.application.backlog.enrichment import (
    TaskEnrichmentError,
    _extract_protected_references,
    _multimodal_data_url_content,
    _restore_protected_references,
    build_enrichment_system_prompt,
    build_task_prompt,
    enrich_backlog_draft,
    enrich_backlog_task,
)
from brain.application.backlog.models import BacklogTask
from brain.application.knowledge.llm.transport import ChatCompletionResult
from brain.application.knowledge.models.dtos.runtime_config import StageModelConfigDTO


def _task() -> BacklogTask:
    """Return one in-memory task fixture without touching the backlog store."""
    return BacklogTask(
        task_id="t42",
        domain="core.brain.backlog",
        title="Enrich task",
        description="Add a model-backed enrichment action.",
        priority="HIGH",
        status="TODO",
        completed_at="",
    )


def test_prompt_preserves_task_facts_and_requires_detailed_output() -> None:
    """The model contract must carry task facts and implementation criteria."""
    prompt = build_task_prompt(task=_task(), profile_context="# developer\nPEP 257")
    system_prompt = build_enrichment_system_prompt(profile_name="developer")
    assert "core.brain.backlog" in prompt
    assert "Add a model-backed enrichment action." in prompt
    assert "PEP 257" in prompt
    assert "acceptance criteria" in system_prompt
    assert "Return only the enriched task description" in system_prompt


def test_reference_metadata_is_hidden_from_model_and_restored_exactly() -> None:
    """The LLM must neither see nor control a persisted visual-reference path."""
    reference = "$agent/pictures/backlog-pic-t42.png"
    task = replace(_task(), description=f"Inspect the screenshot.\n\n{reference}")
    prompt_task, references = _extract_protected_references(task=task)
    assert reference not in prompt_task.description
    assert references == (reference,)

    restored = _restore_protected_references(
        description="# Objective\nDetailed output.\n\n{ref_image}",
        protected_references=references,
    )
    assert "{ref_image}" not in restored
    assert restored.endswith(reference)
    assert restored.count(reference) == 1


def test_enrichment_persists_valid_model_description() -> None:
    """A validated completion must update only the description field."""
    task = _task()
    updated = replace(task, description="# Objective\n" + "Detailed result. " * 8)
    completion = ChatCompletionResult(
        response_payload={"choices": [{"message": {"content": updated.description}}]},
        response_chars=200,
        status=200,
    )
    config = StageModelConfigDTO(
        enabled=True,
        base_url="https://example.invalid/v1",
        api_key="secret",
        model="multimodal-test",
        temperature=0.2,
        max_tokens=2400,
    )
    with (
        patch("brain.application.backlog.enrichment.get_backlog_task", return_value=task),
        patch("brain.application.backlog.enrichment.build_profile_context", return_value=("profile", 7)),
        patch("brain.application.backlog.enrichment.load_text_model_config", return_value=config),
        patch("brain.application.backlog.enrichment.resolve_secret", return_value="secret"),
        patch("brain.application.backlog.enrichment.post_chat_completion", return_value=completion),
        patch("brain.application.backlog.enrichment.edit_backlog_task", return_value=updated) as edit_task,
    ):
        result = enrich_backlog_task(workspace_root=Path("workspace"), task_id="t42")
    assert result.task.description.startswith("# Objective")
    assert result.guideline_count == 7
    assert result.used_image is False
    edit_task.assert_called_once_with(
        workspace_root=Path("workspace"),
        task_id="t42",
        description=updated.description.strip(),
    )


def test_enrichment_rejects_incomplete_model_output() -> None:
    """A short completion must never overwrite the durable task."""
    config = Mock(model="test", base_url="https://example.invalid", api_key="secret", temperature=0.2, max_tokens=500)
    completion = ChatCompletionResult(
        response_payload={"choices": [{"message": {"content": "Too short"}}]},
        response_chars=30,
        status=200,
    )
    with (
        patch("brain.application.backlog.enrichment.get_backlog_task", return_value=_task()),
        patch("brain.application.backlog.enrichment.build_profile_context", return_value=("profile", 1)),
        patch("brain.application.backlog.enrichment.load_text_model_config", return_value=config),
        patch("brain.application.backlog.enrichment.resolve_secret", return_value="secret"),
        patch("brain.application.backlog.enrichment.post_chat_completion", return_value=completion),
        patch("brain.application.backlog.enrichment.edit_backlog_task") as edit_task,
    ):
        try:
            enrich_backlog_task(workspace_root=Path("workspace"), task_id="t42")
        except TaskEnrichmentError as exc:
            assert "incomplete" in str(exc)
        else:
            raise AssertionError("Incomplete model output was accepted.")
    edit_task.assert_not_called()


def test_draft_enrichment_returns_markdown_without_persisting() -> None:
    """Draft enrichment must return the proposal without touching durable storage."""
    description = "# Objective\n" + "Detailed result. " * 8
    completion = ChatCompletionResult(
        response_payload={"choices": [{"message": {"content": description}}]},
        response_chars=len(description),
        status=200,
    )
    config = Mock(model="test", base_url="https://example.invalid", api_key="secret", temperature=0.2, max_tokens=500)
    with (
        patch("brain.application.backlog.enrichment.build_profile_context", return_value=("profile", 2)),
        patch("brain.application.backlog.enrichment.load_text_model_config", return_value=config),
        patch("brain.application.backlog.enrichment.resolve_secret", return_value="secret"),
        patch("brain.application.backlog.enrichment.post_chat_completion", return_value=completion),
        patch("brain.application.backlog.enrichment.edit_backlog_task") as edit_task,
    ):
        result = enrich_backlog_draft(task=_task())
    assert result.description == description.strip()
    assert result.guideline_count == 2
    edit_task.assert_not_called()


def test_data_url_image_content_is_validated_in_memory() -> None:
    """Unsaved PNG data must remain in memory and malformed data must be rejected."""
    content = _multimodal_data_url_content("Prompt", "data:image/png;base64,iVBORw0KGgo=")
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    try:
        _multimodal_data_url_content("Prompt", "data:text/plain;base64,SGVsbG8=")
    except TaskEnrichmentError as exc:
        assert "invalid image data URL" in str(exc)
    else:
        raise AssertionError("A non-image data URL was accepted.")
