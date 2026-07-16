# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Deduplication helpers for knowledge graph consolidation."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.models.dtos.graph import EntityDTO
from brain.application.knowledge.models.ontology_keys import normalize_label
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def find_duplicate_entity(repository: KnowledgeRepository, entity_dto: EntityDTO) -> dict | None:
    """
    Find an existing entity matching a candidate.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        entity_dto (EntityDTO): Entity candidate.

    Returns:
        dict | None: Existing entity row when matched.
    """
    return repository.find_entity_by_ref(entity_ref=entity_dto.canonical_name)


def upsert_deduped_entity(repository: KnowledgeRepository, entity_dto: EntityDTO) -> int:
    """
    Insert an entity or reuse its duplicate.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        entity_dto (EntityDTO): Entity candidate.

    Returns:
        int: Entity identifier.
    """
    duplicate_row: dict | None = find_duplicate_entity(repository=repository, entity_dto=entity_dto)
    if duplicate_row is not None:
        return repository.upsert_entity(entity_dto=entity_dto)
    return repository.upsert_entity(entity_dto=entity_dto)


def should_merge_alias(candidate_name: str, alias: str) -> bool:
    """
    Check whether an alias can safely attach to an entity.

    Args:
        candidate_name (str): Canonical entity name.
        alias (str): Alias candidate.

    Returns:
        bool: True when the alias is non-empty and not identical after normalization.
    """
    normalized_name: str = normalize_label(candidate_name)
    normalized_alias: str = normalize_label(alias)
    return bool(normalized_alias) and normalized_alias != normalized_name
