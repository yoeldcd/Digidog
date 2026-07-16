# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Validation service for knowledge graph deltas."""

from __future__ import annotations

# Standard Libraries Imports
from typing import TYPE_CHECKING

# Application Modules Imports
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO, SchemaSuggestionDTO, ValidationReportDTO
from brain.application.knowledge.models.dtos.graph import EntityDTO, RelationDTO
from brain.application.knowledge.validation.entities import validate_discovered_class_definitions, validate_entity
from brain.application.knowledge.validation.relations import validate_relation
from brain.application.knowledge.validation.schema import validate_schema_suggestion

if TYPE_CHECKING:
    from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def validate_delta(
    delta_dto: KnowledgeDeltaDTO,
    source_content: str,
    minimum_confidence: float = 0.65,
    repository: "KnowledgeRepository | None" = None,
    known_class_names: set[str] | None = None,
) -> ValidationReportDTO:
    """
    Validate and filter a proposed knowledge delta.

    Args:
        delta_dto (KnowledgeDeltaDTO): Proposed delta.
        source_content (str): Source content kept for backward-compatible validation callers.
        minimum_confidence (float): Minimum confidence for accepted records.
        repository (KnowledgeRepository | None): Optional repository used to verify existing endpoint IDs.
        known_class_names (set[str] | None): Run-local class names already declared by accepted CLS entities.

    Returns:
        ValidationReportDTO: Validation report with accepted delta.
    """
    errors: list[str] = []
    warnings: list[str] = []
    accepted_entities: list[EntityDTO] = []
    accepted_relations: list[RelationDTO] = []
    accepted_suggestions: list[SchemaSuggestionDTO] = []

    for entity_dto in delta_dto.entities:
        entity_errors: list[str] = validate_entity(
            entity_dto=entity_dto,
            minimum_confidence=minimum_confidence,
        )
        if entity_errors:
            warnings.extend(entity_errors)
            continue
        accepted_entities.append(entity_dto)

    class_definition_warnings, accepted_entities = validate_discovered_class_definitions(
        accepted_entities=accepted_entities,
        repository=repository,
        known_class_names=known_class_names,
    )
    warnings.extend(class_definition_warnings)

    accepted_entity_ids: set[int] = {
        int(entity_dto.id)
        for entity_dto in accepted_entities
        if entity_dto.id is not None
    }
    accepted_entities_by_id: dict[int, EntityDTO] = {
        int(entity_dto.id): entity_dto
        for entity_dto in accepted_entities
        if entity_dto.id is not None
    }
    for relation_dto in delta_dto.relations:
        relation_errors: list[str] = validate_relation(
            relation_dto=relation_dto,
            accepted_entity_ids=accepted_entity_ids,
            accepted_entities_by_id=accepted_entities_by_id,
            minimum_confidence=minimum_confidence,
            repository=repository,
        )
        if relation_errors:
            warnings.extend(relation_errors)
            continue
        accepted_relations.append(relation_dto)

    for suggestion_dto in delta_dto.schema_suggestions:
        suggestion_errors: list[str] = validate_schema_suggestion(
            suggestion_dto=suggestion_dto,
            minimum_confidence=minimum_confidence,
        )
        if suggestion_errors:
            warnings.extend(suggestion_errors)
            continue
        accepted_suggestions.append(suggestion_dto)

    if not accepted_entities and not accepted_relations and not accepted_suggestions:
        errors.append("Delta contains no applicable records after validation.")

    accepted_delta: KnowledgeDeltaDTO = KnowledgeDeltaDTO(
        source_path=delta_dto.source_path,
        entities=accepted_entities,
        aliases=[],
        relations=accepted_relations,
        schema_suggestions=accepted_suggestions,
        rationale=delta_dto.rationale,
    )
    return ValidationReportDTO(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        accepted_delta=accepted_delta,
    )
