"""Relation result ranking for knowledge search read models."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.infrastructure.database.knowledge.read_models.payloads import (
    _relation_object_entity,
    _relation_payload,
    _relation_subject_entity,
)
from brain.infrastructure.database.knowledge.read_models.scoring import _score_values


def rank_relation_rows(
    connection: Any,
    rows: list[dict[str, Any]],
    tokens: list[str],
) -> list[dict[str, Any]]:
    """
    Rank relation rows by token overlap and fuzzy similarity.

    Args:
        connection: Open SQLite connection.
        rows (list[dict[str, Any]]): Relation rows.
        tokens (list[str]): Normalized query tokens.

    Returns:
        list[dict[str, Any]]: Ranked relation results.
    """
    ranked_results: list[dict[str, Any]] = []
    for row in rows:
        score: float = _score_values(
            tokens=tokens,
            values=[
                row.get("predicate"),
                row.get("subject_name"),
                row.get("subject_description"),
                row.get("object_name"),
                row.get("object_description"),
                row.get("source_path"),
            ],
        )
        if score <= 0.0:
            continue
        row["entities"] = [
            _relation_subject_entity(row=row, connection=connection),
            _relation_object_entity(row=row, connection=connection),
        ]
        row["relations"] = [_relation_payload(row=row, connection=connection)]
        ranked_results.append({"kind": "relation", "rank": 1.0 - score, "data": row})
    return ranked_results
