# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Transport and completion parsing for knowledge LLM stages."""

from __future__ import annotations

# Standard Libraries Imports
import time
from typing import Any

# Application Modules Imports
from brain.application.knowledge.llm.errors import KnowledgeLLMError
from brain.application.knowledge.llm.events import LLMEventCallback, _delta_counts, _emit_event, _preview_text
from brain.application.knowledge.llm.parsing import _parse_model_stage_output
from brain.application.knowledge.llm.sanitization import _sanitize_model_delta_payload
from brain.application.knowledge.llm.transport import ChatCompletionHTTPError, post_chat_completion
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO
from brain.config import KNOWLEDGE_LLM_TIMEOUT_SECONDS


def request_stage_completion(
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
    stage_name: str,
    source_path: str,
    started_at: float,
    event_callback: LLMEventCallback | None,
) -> dict[str, Any]:
    """
    Execute the chat-completion request for one stage.

    Args:
        endpoint (str): Chat-completion endpoint.
        api_key (str): Resolved API key.
        payload (dict[str, Any]): Provider request payload.
        stage_name (str): Configured stage name.
        source_path (str): Source path for diagnostics.
        started_at (float): Stage start timestamp.
        event_callback (LLMEventCallback | None): Optional event sink.

    Returns:
        dict[str, Any]: Provider response payload.
    """
    try:
        completion_result = post_chat_completion(
            endpoint=endpoint,
            api_key=api_key,
            payload=payload,
            timeout_seconds=KNOWLEDGE_LLM_TIMEOUT_SECONDS,
        )
        _emit_event(
            event_callback=event_callback,
            payload={
                "event": "http_response",
                "stage": stage_name,
                "source_path": source_path,
                "status": completion_result.status,
                "response_chars": completion_result.response_chars,
                "elapsed_ms": int((time.time() - started_at) * 1000),
            },
        )
        return completion_result.response_payload
    except ChatCompletionHTTPError as exc:
        _emit_event(
            event_callback=event_callback,
            payload={
                "event": "stage_error",
                "stage": stage_name,
                "source_path": source_path,
                "status": exc.status_code,
                "error": exc.response_text,
                "elapsed_ms": int((time.time() - started_at) * 1000),
            },
        )
        raise KnowledgeLLMError(f"Knowledge LLM HTTP error {exc.status_code}: {exc.response_text}") from exc
    except Exception as exc:
        _emit_event(
            event_callback=event_callback,
            payload={
                "event": "stage_error",
                "stage": stage_name,
                "source_path": source_path,
                "error": str(exc),
                "elapsed_ms": int((time.time() - started_at) * 1000),
            },
        )
        raise KnowledgeLLMError(f"Knowledge LLM request failed: {exc}") from exc


def parse_stage_completion(
    response_payload: dict[str, Any],
    stage_name: str,
    source_path: str,
    prior_delta: KnowledgeDeltaDTO | None,
    entity_name_to_id: dict[str, int] | None,
    started_at: float,
    event_callback: LLMEventCallback | None,
) -> KnowledgeDeltaDTO:
    """
    Parse, sanitize, and validate one stage completion payload.

    Args:
        response_payload (dict[str, Any]): Provider response payload.
        stage_name (str): Configured stage name.
        source_path (str): Source path for diagnostics.
        prior_delta (KnowledgeDeltaDTO | None): Accumulated prior delta.
        entity_name_to_id (dict[str, int] | None): Hidden entity resolver.
        started_at (float): Stage start timestamp.
        event_callback (LLMEventCallback | None): Optional event sink.

    Returns:
        KnowledgeDeltaDTO: Parsed model proposal.
    """
    try:
        content_text: str = response_payload["choices"][0]["message"]["content"]
        parsed_json: dict[str, Any] = _parse_model_stage_output(
            stage_name=stage_name,
            content_text=content_text,
        )
        parsed_json.setdefault("source_path", source_path)
        parsed_json = _sanitize_model_delta_payload(
            stage_name=stage_name,
            payload=parsed_json,
            prior_delta=prior_delta,
            entity_name_to_id=entity_name_to_id,
        )
        delta_dto: KnowledgeDeltaDTO = KnowledgeDeltaDTO.model_validate(parsed_json)
        _emit_event(
            event_callback=event_callback,
            payload={
                "event": "stage_success",
                "stage": stage_name,
                "source_path": source_path,
                "output_chars": len(content_text),
                "output_text": content_text,
                "output_preview": _preview_text(content_text),
                "delta_counts": _delta_counts(delta_dto=delta_dto),
                "elapsed_ms": int((time.time() - started_at) * 1000),
            },
        )
        return delta_dto
    except Exception as exc:
        content_text = _extract_response_text(response_payload=response_payload)
        _emit_event(
            event_callback=event_callback,
            payload={
                "event": "stage_error",
                "stage": stage_name,
                "source_path": source_path,
                "error": f"invalid delta output: {exc}",
                "output_text": content_text,
                "output_preview": _preview_text(content_text),
                "elapsed_ms": int((time.time() - started_at) * 1000),
            },
        )
        raise KnowledgeLLMError(f"Knowledge LLM returned invalid delta output: {exc}") from exc


def _extract_response_text(response_payload: dict[str, Any]) -> str:
    """
    Return best-effort response text for invalid output diagnostics.

    Args:
        response_payload (dict[str, Any]): Provider response payload.

    Returns:
        str: Diagnostic response text.
    """
    try:
        return str(response_payload["choices"][0]["message"]["content"])
    except Exception:
        return str(response_payload)
