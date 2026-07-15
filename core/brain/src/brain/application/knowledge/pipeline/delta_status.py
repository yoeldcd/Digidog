"""Lifecycle status rules for persisted knowledge delta rows."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any


def is_delta_applicable(row: dict[str, Any]) -> bool:
    """
    Return whether a pending row contains applicable accepted records.

    Args:
        row (dict[str, Any]): Pending delta review row.

    Returns:
        bool: True when validation is valid and accepted records are present.
    """
    validation: dict[str, Any] = row["validation"]
    if not validation.get("valid"):
        return False
    if is_legacy_delta(delta=row.get("payload", {})):
        return False
    return any(delta_counts(delta=validation.get("accepted_delta", {})).values())


def is_delta_legacy(row: dict[str, Any]) -> bool:
    """
    Return whether a pending row uses a retired delta payload contract.

    Args:
        row (dict[str, Any]): Pending delta review row.

    Returns:
        bool: True when the row should be treated as legacy.
    """
    return is_legacy_delta(delta=row.get("payload", {}))


def delta_counts(delta: dict[str, Any]) -> dict[str, int]:
    """
    Return entity, alias, relation, and schema suggestion counts.

    Args:
        delta (dict[str, Any]): Delta payload.

    Returns:
        dict[str, int]: Count summary.
    """
    return {
        "entities": len(delta.get("entities", [])),
        "aliases": len(delta.get("aliases", [])),
        "relations": len(delta.get("relations", [])),
        "schema": len(delta.get("schema_suggestions", [])),
    }


def empty_delta_counts() -> dict[str, int]:
    """
    Return zero proposal counters.

    Returns:
        dict[str, int]: Empty entity, alias, relation, and schema counts.
    """
    return {
        "entities": 0,
        "aliases": 0,
        "relations": 0,
        "schema": 0,
    }


def is_legacy_delta(delta: dict[str, Any]) -> bool:
    """
    Return whether a delta uses a retired pre-source-anchor contract.

    Args:
        delta (dict[str, Any]): Delta payload.

    Returns:
        bool: True when the payload should not be rendered or applied as current KG objects.
    """
    rationale: str = str(delta.get("rationale") or "")
    if "Deterministic fallback extraction" in rationale:
        return True
    for entity in delta.get("entities", []):
        if entity.get("entity_class") == "source_document":
            return True
        if entity.get("source_id") is None and entity.get("sourceId") is None:
            return True
    retired_relation_fields: set[str] = {"subject_ref", "object_ref", "object_value", "evidence_quote"}
    for relation in delta.get("relations", []):
        if retired_relation_fields.intersection(relation):
            return True
        if relation.get("source_id") is None and relation.get("sourceId") is None:
            return True
    return False
