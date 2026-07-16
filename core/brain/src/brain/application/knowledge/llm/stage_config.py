# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Configuration resolution for knowledge LLM stages."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.llm.errors import KnowledgeLLMError
from brain.application.knowledge.llm.events import LLMEventCallback, _emit_event
from brain.application.knowledge.models.dtos.runtime_config import StageModelConfigDTO
from brain.application.knowledge.runtime.config_store import load_knowledge_config, resolve_secret


def resolve_enabled_stage_config(
    stage_name: str,
    source_path: str,
    event_callback: LLMEventCallback | None,
) -> StageModelConfigDTO:
    """
    Return an enabled stage configuration.

    Args:
        stage_name (str): Configured stage name.
        source_path (str): Source path for diagnostics.
        event_callback (LLMEventCallback | None): Optional event sink.

    Returns:
        StageModelConfigDTO: Enabled stage configuration.
    """
    config_dto = load_knowledge_config()
    stage_config: StageModelConfigDTO | None = config_dto.stages.get(stage_name)
    if stage_config is not None and stage_config.enabled:
        return stage_config
    _emit_event(
        event_callback=event_callback,
        payload={
            "event": "stage_error",
            "stage": stage_name,
            "source_path": source_path,
            "error": "stage disabled",
        },
    )
    raise KnowledgeLLMError(f"Knowledge LLM stage `{stage_name}` is disabled.")


def resolve_stage_api_key(
    stage_name: str,
    source_path: str,
    stage_config: StageModelConfigDTO,
    event_callback: LLMEventCallback | None,
) -> str:
    """
    Resolve the configured API key for one stage.

    Args:
        stage_name (str): Configured stage name.
        source_path (str): Source path for diagnostics.
        stage_config (StageModelConfigDTO): Stage configuration.
        event_callback (LLMEventCallback | None): Optional event sink.

    Returns:
        str: Resolved API key.
    """
    api_key: str = resolve_secret(stage_config.api_key)
    if not api_key.startswith("$"):
        return api_key
    _emit_event(
        event_callback=event_callback,
        payload={
            "event": "stage_error",
            "stage": stage_name,
            "source_path": source_path,
            "model": stage_config.model,
            "error": "api key unresolved",
        },
    )
    raise KnowledgeLLMError(f"Knowledge LLM stage `{stage_name}` has no resolved API key.")
