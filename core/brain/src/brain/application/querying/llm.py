"""OpenAI-compatible helper calls used by deep query mode."""

from __future__ import annotations

# Standard Libraries Imports
import json
import re
from typing import Any

# Application Modules Imports
from brain.application.knowledge.llm.transport import post_chat_completion
from brain.application.knowledge.models.dtos.runtime_config import StageModelConfigDTO
from brain.application.knowledge.runtime.config_store import resolve_secret
from brain.config import KNOWLEDGE_LLM_TIMEOUT_SECONDS
from brain.infrastructure.vectorstores.settings import load_config


def request_query_json(system_prompt: str, user_prompt: str, max_tokens: int = 1200) -> dict[str, Any]:
    """
    Request one JSON object from the configured memory text model.

    Args:
        system_prompt (str): System instruction.
        user_prompt (str): User instruction.
        max_tokens (int): Maximum response token count.

    Returns:
        dict[str, Any]: Parsed JSON object.

    Raises:
        RuntimeError: If configuration, transport, or parsing fails.
    """
    stage_config: StageModelConfigDTO = load_text_model_config(max_tokens=max_tokens)
    api_key: str = resolve_secret(stage_config.api_key)
    if api_key.startswith("$"):
        raise RuntimeError("text model API key unresolved")
    endpoint: str = f"{stage_config.base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": stage_config.model,
        "temperature": stage_config.temperature,
        "max_tokens": min(stage_config.max_tokens, max_tokens),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    completion = post_chat_completion(
        endpoint=endpoint,
        api_key=api_key,
        payload=payload,
        timeout_seconds=KNOWLEDGE_LLM_TIMEOUT_SECONDS,
    )
    content_text: str = str(completion.response_payload["choices"][0]["message"]["content"])
    return parse_json_object(text=content_text)


def load_text_model_config(max_tokens: int) -> StageModelConfigDTO:
    """
    Return the configured memory text model.

    Args:
        max_tokens (int): Fallback token budget when config has no explicit value.

    Returns:
        StageModelConfigDTO: Text-model configuration.

    Raises:
        RuntimeError: If the model is disabled.
    """
    raw_config: dict[str, Any] = load_config()
    text_model_payload: dict[str, Any] = dict(raw_config.get("text_model") or {})
    if "max_tokens" not in text_model_payload:
        text_model_payload["max_tokens"] = max_tokens
    stage_config: StageModelConfigDTO = StageModelConfigDTO.model_validate(text_model_payload)
    if not stage_config.enabled:
        raise RuntimeError("text model disabled")
    return stage_config


def parse_json_object(text: str) -> dict[str, Any]:
    """
    Parse a JSON object, accepting fenced JSON blocks.

    Args:
        text (str): Raw model text.

    Returns:
        dict[str, Any]: Parsed JSON object.

    Raises:
        RuntimeError: If no JSON object is present.
    """
    stripped: str = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1)
    else:
        object_match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if object_match:
            stripped = object_match.group(0)
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise RuntimeError("text model did not return a JSON object")
    return payload
