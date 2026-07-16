# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Schema suggestion validation for knowledge deltas."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.models.dtos.deltas import SchemaSuggestionDTO
from brain.application.knowledge.models.entity_classes import is_entity_class_allowed
from brain.application.knowledge.models.relation_types import is_relation_type_allowed


def validate_schema_suggestion(
    suggestion_dto: SchemaSuggestionDTO,
    minimum_confidence: float,
) -> list[str]:
    """
    Validate one schema suggestion.

    Args:
        suggestion_dto (SchemaSuggestionDTO): Schema suggestion candidate.
        minimum_confidence (float): Minimum accepted confidence.

    Returns:
        list[str]: Validation failures.
    """
    errors: list[str] = []
    if suggestion_dto.suggestion_type not in ("entity_class", "relation_type"):
        errors.append(f"Rejected unsupported schema suggestion type `{suggestion_dto.suggestion_type}`.")
    elif suggestion_dto.suggestion_type == "entity_class" and not is_entity_class_allowed(suggestion_dto.name):
        errors.append(f"Rejected schema suggestion `{suggestion_dto.name}` with invalid class key.")
    elif suggestion_dto.suggestion_type == "relation_type" and not is_relation_type_allowed(suggestion_dto.name):
        errors.append(f"Rejected schema suggestion `{suggestion_dto.name}` with invalid predicate key.")
    if suggestion_dto.confidence < minimum_confidence:
        errors.append(f"Rejected schema suggestion `{suggestion_dto.name}` below confidence threshold.")
    return errors
