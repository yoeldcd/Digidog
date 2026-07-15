"""Event emission helpers for knowledge LLM stages."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.llm.events import LLMEventCallback, _delta_counts, _emit_event
from brain.application.knowledge.models.dtos.runtime_config import StageModelConfigDTO
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO
from brain.infrastructure.prompts import get_stage_prompt_template_path


def emit_stage_start(
    event_callback: LLMEventCallback | None,
    stage_name: str,
    source_path: str,
    stage_config: StageModelConfigDTO,
    content: str,
    prompt: str,
    graph_context: str,
    prior_delta: KnowledgeDeltaDTO | None,
    entity_class_catalog: dict[str, str] | None,
) -> None:
    """
    Emit the structured start event for one model stage.

    Args:
        event_callback (LLMEventCallback | None): Optional event sink.
        stage_name (str): Configured stage name.
        source_path (str): Source path for diagnostics.
        stage_config (StageModelConfigDTO): Stage configuration.
        content (str): Model input content.
        prompt (str): Rendered prompt.
        graph_context (str): Rendered graph context.
        prior_delta (KnowledgeDeltaDTO | None): Accumulated prior delta.
        entity_class_catalog (dict[str, str] | None): Known class definitions.
    """
    _emit_event(
        event_callback=event_callback,
        payload={
            "event": "stage_start",
            "stage": stage_name,
            "source_path": source_path,
            "model": stage_config.model,
            "base_url": stage_config.base_url,
            "temperature": stage_config.temperature,
            "max_tokens": stage_config.max_tokens,
            "source_chars": len(content),
            "prompt_chars": len(prompt),
            "graph_context_chars": len(graph_context),
            "entity_class_catalog_size": len(entity_class_catalog or {}),
            "prior_delta_counts": _delta_counts(delta_dto=prior_delta),
            "prompt_template_path": str(get_stage_prompt_template_path(stage_name=stage_name)),
        },
    )
