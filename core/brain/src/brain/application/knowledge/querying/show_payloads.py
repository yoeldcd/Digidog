# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Read payload builders for the `knowledge-show` command."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def selected_modes(args: Any) -> set[str]:
    """
    Return selected listing modes from parsed command arguments.

    Args:
        args (Any): Parsed command arguments.

    Returns:
        set[str]: Selected listing modes.
    """
    modes: set[str] = set()
    if bool(args.entities):
        modes.add("entities")
    if bool(args.relations):
        modes.add("relations")
    if bool(args.classes):
        modes.add("classes")
    return modes


def filter_text(args: Any, modes: set[str]) -> str:
    """
    Return explicit filter text or positional listing filter.

    Args:
        args (Any): Parsed command arguments.
        modes (set[str]): Selected listing modes.

    Returns:
        str: Filter text.
    """
    explicit_filter = str(getattr(args, "filter", "") or "").strip()
    if explicit_filter:
        return explicit_filter
    if modes and args.entity is not None:
        return str(args.entity).strip()
    return ""


def entity_payload(repository: KnowledgeRepository, entity: str) -> dict[str, Any] | None:
    """
    Load one entity by ID, canonical name, or alias.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        entity (str): Entity reference.

    Returns:
        dict[str, Any] | None: Entity payload when found.
    """
    entity_ref: int | str = int(entity) if entity.isdigit() else entity
    return repository.get_entity(entity_ref=entity_ref)


def overview_payload(repository: KnowledgeRepository, scope: str) -> dict[str, Any]:
    """
    Build the no-argument overview payload.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        scope (str): Knowledge scope.

    Returns:
        dict[str, Any]: Overview payload.
    """
    return {
        "ok": True,
        "scope": scope,
        "counts": repository.status().get("counts", {}),
        "modes": ["--entities", "--relations", "--classes"],
    }


def listing_payload(
    repository: KnowledgeRepository,
    scope: str,
    modes: set[str],
    filter_value: str,
) -> dict[str, Any]:
    """
    Build a filtered listing payload for selected graph record kinds.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        scope (str): Knowledge scope.
        modes (set[str]): Listing modes to include.
        filter_value (str): Optional filter text.

    Returns:
        dict[str, Any]: Listing payload.
    """
    payload: dict[str, Any] = {"ok": True, "scope": scope, "filter": filter_value}
    if "entities" in modes:
        payload["entities"] = [
            row
            for row in repository.list_entities()
            if matches(row=row, filter_text=filter_value, keys=("id", "entity_class", "canonical_name", "description", "status", "source_path"))
            or assertion_matches(row=row, filter_text=filter_value)
        ]
    if "relations" in modes:
        payload["relations"] = [
            row
            for row in repository.list_relations()
            if matches(
                row=row,
                filter_text=filter_value,
                keys=("id", "subject_name", "subject_class", "predicate", "object_name", "object_class", "source_path"),
            )
        ]
    if "classes" in modes:
        payload["classes"] = [
            row
            for row in repository.list_entity_classes()
            if matches(row=row, filter_text=filter_value, keys=("name", "description", "status"))
        ]
    return payload


def assertion_matches(row: dict[str, Any], filter_text: str) -> bool:
    """
    Return true when any source-scoped type assertion matches.

    Args:
        row (dict[str, Any]): Entity row.
        filter_text (str): Optional filter text.

    Returns:
        bool: True when a type assertion matches.
    """
    return any(
        matches(
            row=assertion,
            filter_text=filter_text,
            keys=("entity_class", "description", "source_path"),
        )
        for assertion in row.get("type_assertions", [])
    )


def matches(row: dict[str, Any], filter_text: str, keys: tuple[str, ...]) -> bool:
    """
    Return true when no filter exists or a row field contains it.

    Args:
        row (dict[str, Any]): Candidate row.
        filter_text (str): Optional filter text.
        keys (tuple[str, ...]): Row keys to search.

    Returns:
        bool: True when row matches.
    """
    if not filter_text:
        return True
    needle = filter_text.casefold()
    return any(needle in str(row.get(key) or "").casefold() for key in keys)
