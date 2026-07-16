# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Relation validation for knowledge deltas."""

from __future__ import annotations

# Standard Libraries Imports
from typing import TYPE_CHECKING

# Application Modules Imports
from brain.application.knowledge.models.dtos.graph import EntityDTO, RelationDTO
from brain.application.knowledge.models.relation_types import is_relation_type_allowed
from brain.application.knowledge.validation.labels import normalize_key_fragment

if TYPE_CHECKING:
    from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


DOCUMENT_STRUCTURE_RELATION_PREDICATES: set[str] = {
    "belongs_to_source",
    "derived_from",
    "from_source",
    "has_date",
    "has_entry",
    "has_heading",
    "has_line",
    "has_path",
    "has_section",
    "has_source",
    "has_time",
    "has_title",
    "located_in_file",
    "read_from",
}
"""Predicates that model document metadata instead of semantic content."""


def validate_relation(
    relation_dto: RelationDTO,
    minimum_confidence: float,
    accepted_entity_ids: set[int],
    accepted_entities_by_id: dict[int, EntityDTO],
    repository: "KnowledgeRepository | None",
) -> list[str]:
    """
    Validate one relation candidate.

    Args:
        relation_dto (RelationDTO): Relation candidate.
        minimum_confidence (float): Minimum accepted confidence.
        accepted_entity_ids (set[int]): Candidate-local entity IDs accepted from the same delta.
        accepted_entities_by_id (dict[int, EntityDTO]): Accepted local entities by candidate ID.
        repository (KnowledgeRepository | None): Optional repository used to verify existing endpoint IDs.

    Returns:
        list[str]: Validation failures.
    """
    errors: list[str] = []
    if relation_dto.source_id is None:
        errors.append(f"Rejected relation `{relation_dto.predicate}` without source_id.")
    if relation_dto.subject_id is None:
        errors.append(f"Rejected relation `{relation_dto.predicate}` without subject_id.")
    elif relation_dto.subject_id <= 0:
        errors.append(f"Rejected relation `{relation_dto.predicate}` with non-positive subject_id.")
    elif not _endpoint_exists(
        entity_id=relation_dto.subject_id,
        accepted_entity_ids=accepted_entity_ids,
        repository=repository,
    ):
        errors.append(f"Rejected relation `{relation_dto.predicate}` with unknown subject_id.")

    if relation_dto.object_id is None:
        errors.append(f"Rejected relation `{relation_dto.predicate}` without object_id.")
    elif relation_dto.object_id <= 0:
        errors.append(f"Rejected relation `{relation_dto.predicate}` with non-positive object_id.")
    elif not _endpoint_exists(
        entity_id=relation_dto.object_id,
        accepted_entity_ids=accepted_entity_ids,
        repository=repository,
    ):
        errors.append(f"Rejected relation `{relation_dto.predicate}` with unknown object_id.")

    if not is_relation_type_allowed(relation_dto.predicate):
        errors.append(f"Rejected relation with invalid predicate key `{relation_dto.predicate}`.")
    errors.extend(
        _validate_predicate_semantics(
            relation_dto=relation_dto,
            accepted_entities_by_id=accepted_entities_by_id,
        ),
    )
    if relation_dto.confidence < minimum_confidence:
        errors.append(f"Rejected relation `{relation_dto.predicate}` below confidence threshold.")
    return errors


def _validate_predicate_semantics(
    relation_dto: RelationDTO,
    accepted_entities_by_id: dict[int, EntityDTO],
) -> list[str]:
    """
    Reject predicates that look like entity-bearing labels instead of verbal nuclei.

    Args:
        relation_dto (RelationDTO): Relation candidate.
        accepted_entities_by_id (dict[int, EntityDTO]): Accepted local entities by candidate ID.

    Returns:
        list[str]: Validation failures for predicate semantics.
    """
    predicate: str = relation_dto.predicate.strip()
    errors: list[str] = []
    if predicate in DOCUMENT_STRUCTURE_RELATION_PREDICATES:
        errors.append(f"Rejected relation `{predicate}` because source structure must stay metadata.")
        return errors
    if len([token for token in predicate.split("_") if token]) > 4:
        errors.append(f"Rejected relation `{predicate}` because predicates must be compact verbal nuclei.")
        return errors

    endpoint_entities: list[EntityDTO] = []
    for endpoint_id in (relation_dto.subject_id, relation_dto.object_id):
        if endpoint_id is None:
            continue
        endpoint_entity: EntityDTO | None = accepted_entities_by_id.get(endpoint_id)
        if endpoint_entity is not None:
            endpoint_entities.append(endpoint_entity)

    for entity_dto in endpoint_entities:
        normalized_name: str = normalize_key_fragment(entity_dto.canonical_name)
        if len(normalized_name) > 3 and normalized_name in predicate:
            errors.append(
                f"Rejected relation `{predicate}` because predicates must not contain endpoint entity names.",
            )
            break
    return errors


def _endpoint_exists(
    entity_id: int,
    accepted_entity_ids: set[int],
    repository: "KnowledgeRepository | None",
) -> bool:
    """
    Return whether a relation endpoint references a local or persisted entity.

    Args:
        entity_id (int): Candidate endpoint identifier.
        accepted_entity_ids (set[int]): Candidate-local entity IDs accepted from the same delta.
        repository (KnowledgeRepository | None): Optional repository for persisted entity lookup.

    Returns:
        bool: True when the endpoint can be resolved during application.
    """
    if entity_id in accepted_entity_ids:
        return True
    if repository is None:
        return True
    return repository.find_entity_by_ref(entity_ref=entity_id) is not None
