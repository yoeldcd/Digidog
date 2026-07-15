"""Pure delta rules for dream orchestration."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO


def delta_has_records(delta_dto: KnowledgeDeltaDTO) -> bool:
    """
    Return whether a delta contains any proposed graph records.

    Args:
        delta_dto (KnowledgeDeltaDTO): Candidate delta.

    Returns:
        bool: True when the delta has records worth validating and persisting.
    """
    return bool(
        delta_dto.entities
        or delta_dto.aliases
        or delta_dto.relations
        or delta_dto.schema_suggestions
    )
