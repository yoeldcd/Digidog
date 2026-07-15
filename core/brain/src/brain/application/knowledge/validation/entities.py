"""Entity validation for knowledge deltas."""

from __future__ import annotations

# Standard Libraries Imports
from typing import TYPE_CHECKING

# Application Modules Imports
from brain.application.knowledge.models.dtos.graph import EntityDTO
from brain.application.knowledge.models.entity_classes import (
    canonical_class_name,
    class_name_from_entity_class,
    is_class_definition_entity,
    is_entity_class_allowed,
    is_valid_class_name,
)
from brain.application.knowledge.models.ontology_definitions import CORE_ENTITY_CLASS_DEFINITIONS
from brain.application.knowledge.validation.labels import (
    has_trailing_descriptor_adjective,
    is_document_structure_label,
    is_sentence_like_label,
)

if TYPE_CHECKING:
    from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def validate_entity(entity_dto: EntityDTO, minimum_confidence: float) -> list[str]:
    """
    Validate one entity candidate.

    Args:
        entity_dto (EntityDTO): Entity candidate.
        minimum_confidence (float): Minimum accepted confidence.

    Returns:
        list[str]: Validation failures.
    """
    errors: list[str] = []
    canonical_name: str = entity_dto.canonical_name.strip()
    is_class_entity: bool = is_class_definition_entity(entity_class=entity_dto.entity_class)
    if not canonical_name:
        errors.append("Rejected entity with empty canonical_name.")
    if is_document_structure_label(label=canonical_name):
        errors.append(
            f"Rejected entity `{entity_dto.canonical_name}` because source structure must stay metadata.",
        )
    if is_class_entity and not is_valid_class_name(canonical_class_name(canonical_name)):
        errors.append(
            f"Rejected class definition `{entity_dto.canonical_name}` with invalid PascalCase class name.",
        )
    if not is_class_entity and has_trailing_descriptor_adjective(label=canonical_name):
        errors.append(
            f"Rejected entity `{entity_dto.canonical_name}` because descriptive adjectives belong in description.",
        )
    if not is_class_entity and is_sentence_like_label(label=canonical_name):
        errors.append(f"Rejected entity `{entity_dto.canonical_name}` because labels must not be full sentences.")
    if entity_dto.source_id is None:
        errors.append(f"Rejected entity `{entity_dto.canonical_name}` without source_id.")
    if not is_entity_class_allowed(entity_dto.entity_class):
        errors.append(f"Rejected entity `{entity_dto.canonical_name}` with invalid class key.")
    if entity_dto.confidence < minimum_confidence:
        errors.append(f"Rejected entity `{entity_dto.canonical_name}` below confidence threshold.")
    return errors


def validate_discovered_class_definitions(
    accepted_entities: list[EntityDTO],
    repository: "KnowledgeRepository | None",
    known_class_names: set[str] | None,
) -> tuple[list[str], list[EntityDTO]]:
    """
    Require discovered subtype classes to be known or defined by a CLS entity.

    Args:
        accepted_entities (list[EntityDTO]): Entity candidates that passed individual validation.
        repository (KnowledgeRepository | None): Optional repository for known class lookup.
        known_class_names (set[str] | None): Run-local class names already declared by accepted CLS entities.

    Returns:
        tuple[list[str], list[EntityDTO]]: Warnings and filtered entity candidates.
    """
    warnings: list[str] = []
    class_definition_entities: list[EntityDTO] = [
        entity_dto
        for entity_dto in accepted_entities
        if is_class_definition_entity(entity_class=entity_dto.entity_class)
    ]
    object_entities: list[EntityDTO] = [
        entity_dto
        for entity_dto in accepted_entities
        if not is_class_definition_entity(entity_class=entity_dto.entity_class)
    ]
    core_class_names: set[str] = {
        class_name
        for class_key in CORE_ENTITY_CLASS_DEFINITIONS
        for class_name in (class_name_from_entity_class(class_key),)
        if class_name
    }
    registered_class_names: set[str] = set(core_class_names)
    registered_class_names.update(
        canonical_class_name(class_name)
        for class_name in (known_class_names or set())
        if class_name
    )
    if repository is not None:
        registered_class_names.update(
            canonical_class_name(str(row.get("canonical_name") or ""))
            for row in repository.list_entities()
            if str(row.get("entity_class")) == "CLS"
        )
        registered_class_names.update(
            _class_cache_names(class_rows=repository.list_entity_classes()),
        )

    delta_defined_classes: set[str] = {
        canonical_class_name(entity_dto.canonical_name)
        for entity_dto in class_definition_entities
    }
    available_class_names: set[str] = registered_class_names | delta_defined_classes
    missing_classes: set[str] = {
        entity_dto.entity_class
        for entity_dto in object_entities
        if "." in entity_dto.entity_class
        and (class_name_from_entity_class(entity_dto.entity_class) not in available_class_names)
    }
    if not missing_classes:
        return warnings, class_definition_entities + object_entities

    for class_name in sorted(missing_classes):
        warnings.append(f"Rejected discovered class `{class_name}` without CLS class definition.")

    filtered_object_entities: list[EntityDTO] = [
        entity_dto
        for entity_dto in object_entities
        if entity_dto.entity_class not in missing_classes
    ]
    return warnings, class_definition_entities + filtered_object_entities


def _class_cache_names(class_rows: list[dict]) -> set[str]:
    """
    Convert `entity_classes` cache rows into comparable class names.

    Args:
        class_rows (list[dict]): Repository class cache rows.

    Returns:
        set[str]: PascalCase subtype names backed by the cache.
    """
    class_names: set[str] = set()
    for row in class_rows:
        row_name: str = str(row.get("name") or "")
        subtype_name: str | None = class_name_from_entity_class(row_name)
        class_names.add(subtype_name or canonical_class_name(row_name))
    return class_names
