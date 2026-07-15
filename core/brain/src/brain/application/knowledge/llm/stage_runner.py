"""Single-stage LLM runner for knowledge delta generation."""

from __future__ import annotations

import time
from typing import Any

# Application Modules Imports
from brain.application.knowledge.llm.events import LLMEventCallback
from brain.application.knowledge.llm.prompts import build_delta_prompt
from brain.application.knowledge.llm.stage_completion import parse_stage_completion, request_stage_completion
from brain.application.knowledge.llm.stage_config import resolve_enabled_stage_config, resolve_stage_api_key
from brain.application.knowledge.llm.stage_events import emit_stage_start
from brain.application.knowledge.models.dtos.runtime_config import StageModelConfigDTO
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO
from brain.infrastructure.prompts import get_stage_system_prompt


def generate_delta_with_llm(
    stage_name: str,
    source_path: str,
    content: str,
    prior_delta: KnowledgeDeltaDTO | None = None,
    graph_context: str = "",
    entity_name_to_id: dict[str, int] | None = None,
    entity_class_catalog: dict[str, str] | None = None,
    event_callback: LLMEventCallback | None = None,
) -> KnowledgeDeltaDTO:
    """
    Request a structured knowledge delta from the configured model.

    Args:
        stage_name (str): Configured model stage name.
        source_path (str): Stable source path.
        content (str): Source text to analyze.
        prior_delta (KnowledgeDeltaDTO | None): Accumulated delta from earlier stages.
        graph_context (str): Compact read-only snapshot of existing graph state.
        entity_name_to_id (dict[str, int] | None): Hidden exact-name resolver for existing entities.
        entity_class_catalog (dict[str, str] | None): Known class definitions for NER prompts.
        event_callback (LLMEventCallback | None): Optional live event sink.

    Returns:
        KnowledgeDeltaDTO: Parsed model proposal.

    Raises:
        KnowledgeLLMError: If the stage is disabled, unavailable, or returns invalid output.
    """
    stage_config: StageModelConfigDTO = resolve_enabled_stage_config(
        stage_name=stage_name,
        source_path=source_path,
        event_callback=event_callback,
    )
    api_key: str = resolve_stage_api_key(
        stage_name=stage_name,
        source_path=source_path,
        stage_config=stage_config,
        event_callback=event_callback,
    )
    endpoint: str = f"{stage_config.base_url.rstrip('/')}/chat/completions"
    prompt: str = build_delta_prompt(
        stage_name=stage_name,
        source_path=source_path,
        content=content,
        prior_delta=prior_delta,
        graph_context=graph_context,
        entity_class_catalog=entity_class_catalog,
    )
    payload: dict[str, Any] = {
        "model": stage_config.model,
        "temperature": stage_config.temperature,
        "max_tokens": stage_config.max_tokens,
        "messages": [
            {
                "role": "system",
                "content": get_stage_system_prompt(stage_name=stage_name),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }
    started_at: float = time.time()
    emit_stage_start(
        event_callback=event_callback,
        stage_name=stage_name,
        source_path=source_path,
        stage_config=stage_config,
        content=content,
        prompt=prompt,
        graph_context=graph_context,
        prior_delta=prior_delta,
        entity_class_catalog=entity_class_catalog,
    )
    response_payload: dict[str, Any] = request_stage_completion(
        endpoint=endpoint,
        api_key=api_key,
        payload=payload,
        stage_name=stage_name,
        source_path=source_path,
        started_at=started_at,
        event_callback=event_callback,
    )
    return parse_stage_completion(
        response_payload=response_payload,
        stage_name=stage_name,
        source_path=source_path,
        prior_delta=prior_delta,
        entity_name_to_id=entity_name_to_id,
        started_at=started_at,
        event_callback=event_callback,
    )
