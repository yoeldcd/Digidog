"""Event helpers for knowledge LLM stage diagnostics."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any, Callable

# Application Modules Imports
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO


LLMEventCallback = Callable[[dict[str, Any]], None]
"""Callback used to stream model-stage diagnostics to the caller."""


def _emit_event(event_callback: LLMEventCallback | None, payload: dict[str, Any]) -> None:
    """
    Emit a model-stage event when a callback is available.

    Args:
        event_callback (LLMEventCallback | None): Optional event sink.
        payload (dict[str, Any]): JSON-compatible event payload.
    """
    if event_callback is not None:
        event_callback(payload)


def _delta_counts(delta_dto: KnowledgeDeltaDTO | None) -> dict[str, int]:
    """
    Return compact counts for a knowledge delta.

    Args:
        delta_dto (KnowledgeDeltaDTO | None): Optional delta.

    Returns:
        dict[str, int]: Entity, relation, alias, and schema counts.
    """
    if delta_dto is None:
        return {"Et": 0, "Re": 0, "Ale": 0, "Sch": 0}
    return {
        "Et": len(delta_dto.entities),
        "Re": len(delta_dto.relations),
        "Ale": len(delta_dto.aliases),
        "Sch": len(delta_dto.schema_suggestions),
    }


def _preview_text(text: str, limit: int = 500) -> str:
    """
    Return a single-line preview of a longer text.

    Args:
        text (str): Raw text.
        limit (int): Maximum preview characters.

    Returns:
        str: Single-line preview text.
    """
    normalized_text: str = " ".join(text.split())
    if len(normalized_text) <= limit:
        return normalized_text
    return f"{normalized_text[: limit - 3]}..."
