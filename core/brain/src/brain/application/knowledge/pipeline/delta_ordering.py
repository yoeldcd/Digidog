"""Ordering rules for applying reviewed knowledge deltas."""

from __future__ import annotations


def class_definition_sort_key(row: dict) -> tuple[int, int]:
    """
    Sort class-definition deltas before object deltas.

    Args:
        row (dict): Pending delta row.

    Returns:
        tuple[int, int]: Stable sort key with CLS-bearing rows first.
    """
    delta_payload: dict = row.get("payload", {})
    entities: list[dict] = delta_payload.get("entities", [])
    defines_class: bool = any(str(entity.get("entity_class")) == "CLS" for entity in entities)
    return (0 if defines_class else 1, int(row.get("id") or 0))
