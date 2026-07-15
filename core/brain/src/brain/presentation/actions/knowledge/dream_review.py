"""Review-row helpers for knowledge dream application flow."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.application.knowledge.pipeline.delta_revalidation import revalidate_pending_delta_rows
from brain.application.knowledge.pipeline.delta_status import is_delta_applicable
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def is_bootstrap_required(repository: KnowledgeRepository) -> bool:
    """
    Return whether the graph needs first-run automatic population.

    Args:
        repository (KnowledgeRepository): Knowledge repository.

    Returns:
        bool: True when no graph entities or relations exist yet.
    """
    counts: dict[str, int] = repository.status().get("counts", {})
    return int(counts.get("entities", 0)) == 0 and int(counts.get("relations", 0)) == 0


def select_applicable_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Filter rows down to deltas that can be applied automatically.

    Args:
        rows (list[dict[str, Any]]): Pending delta review rows.

    Returns:
        list[dict[str, Any]]: Applicable rows.
    """
    applicable_rows: list[dict[str, Any]] = [row for row in rows if is_delta_applicable(row=row)]
    return sorted(applicable_rows, key=_class_definition_sort_key)


def _class_definition_sort_key(row: dict[str, Any]) -> tuple[int, int]:
    """
    Sort class-definition deltas before object deltas for bootstrap application.

    Args:
        row (dict[str, Any]): Pending delta row.

    Returns:
        tuple[int, int]: Stable sort key with CLS-bearing rows first.
    """
    accepted_delta: dict[str, Any] = row.get("validation", {}).get("accepted_delta", {})
    entities: list[dict[str, Any]] = accepted_delta.get("entities", [])
    defines_class: bool = any(str(entity.get("entity_class")) == "CLS" for entity in entities)
    return (0 if defines_class else 1, int(row.get("id") or 0))


def reload_review_rows(
    repository: KnowledgeRepository,
    previous_rows: list[dict[str, Any]],
    pending_delta_ids: list[int],
) -> list[dict[str, Any]]:
    """
    Reload rows after bootstrap changes so rendered statuses are current.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        previous_rows (list[dict[str, Any]]): Rows shown before bootstrap application.
        pending_delta_ids (list[int]): Dream-produced row identifiers.

    Returns:
        list[dict[str, Any]]: Refreshed review rows.
    """
    row_ids: list[int] = pending_delta_ids or [
        int(row["id"])
        for row in previous_rows
        if row.get("id") is not None
    ]
    return load_pending_rows(repository=repository, pending_delta_ids=row_ids)


def load_pending_rows(repository: KnowledgeRepository, pending_delta_ids: list[int]) -> list[dict[str, Any]]:
    """
    Load pending delta rows preserving the current dream order.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        pending_delta_ids (list[int]): Pending delta identifiers from the dream run.

    Returns:
        list[dict[str, Any]]: Pending delta review rows.
    """
    rows: list[dict[str, Any]] = []
    for pending_delta_id in pending_delta_ids:
        row = repository.get_pending_delta(delta_id=pending_delta_id)
        if row is not None:
            rows.append(row)
    return revalidate_pending_delta_rows(repository=repository, rows=rows)
