# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Entity class catalog helpers for dream runs."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO
from brain.application.knowledge.models.entity_classes import canonical_class_name, class_name_from_entity_class
from brain.application.knowledge.models.ontology_definitions import CORE_ENTITY_CLASS_DEFINITIONS
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def build_entity_class_catalog(repository: KnowledgeRepository) -> dict[str, str]:
    """
    Build known classifier definitions from the repository.

    Args:
        repository (KnowledgeRepository): Knowledge repository.

    Returns:
        dict[str, str]: Class names mapped to descriptions.
    """
    class_catalog: dict[str, str] = {}
    for class_row in repository.list_entity_classes():
        class_key: str = str(class_row.get("name") or "")
        if class_key in CORE_ENTITY_CLASS_DEFINITIONS:
            continue
        class_name: str = class_name_from_entity_class(class_key) or canonical_class_name(class_key)
        class_catalog[class_name] = str(class_row.get("description") or "")
    for entity_row in repository.list_entities():
        if str(entity_row.get("entity_class")) != "CLS":
            continue
        class_name = canonical_class_name(str(entity_row.get("canonical_name") or ""))
        class_catalog[class_name] = str(entity_row.get("description") or "")
    return class_catalog


def merge_entity_class_catalog(
    entity_class_catalog: dict[str, str],
    delta_dto: KnowledgeDeltaDTO,
) -> None:
    """
    Add class definitions discovered in one delta to the run-local catalog.

    Args:
        entity_class_catalog (dict[str, str]): Mutable run-local class catalog.
        delta_dto (KnowledgeDeltaDTO): Delta produced for one source.
    """
    for entity_dto in delta_dto.entities:
        if entity_dto.entity_class == "CLS":
            class_name: str = canonical_class_name(entity_dto.canonical_name)
            entity_class_catalog.setdefault(class_name, entity_dto.description)
