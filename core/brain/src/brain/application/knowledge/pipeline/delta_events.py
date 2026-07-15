"""Diagnostic event helpers for reviewed knowledge deltas."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any, Callable

# Application Modules Imports
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO

ApplicationEventCallback = Callable[[dict[str, Any]], None]
"""Callback contract for verbose delta application diagnostics."""


def emit_application_event(
    event_callback: ApplicationEventCallback | None,
    payload: dict[str, Any],
) -> None:
    """
    Emit a delta application event when a callback is available.

    Args:
        event_callback (ApplicationEventCallback | None): Optional event sink.
        payload (dict[str, Any]): JSON-compatible diagnostic payload.
    """
    if event_callback is not None:
        event_callback(payload)


def delta_counts(delta_dto: KnowledgeDeltaDTO) -> dict[str, int]:
    """
    Return compact counts for application diagnostics.

    Args:
        delta_dto (KnowledgeDeltaDTO): Delta being applied or validated.

    Returns:
        dict[str, int]: Entity, relation, alias, and schema counts.
    """
    return {
        "Et": len(delta_dto.entities),
        "Re": len(delta_dto.relations),
        "Ale": len(delta_dto.aliases),
        "Sch": len(delta_dto.schema_suggestions),
    }
