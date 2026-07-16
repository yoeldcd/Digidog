# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Entity result ranking for knowledge search read models."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.infrastructure.database.knowledge.read_models.payloads import _entity_payload, _type_assertions_for_entity
from brain.infrastructure.database.knowledge.read_models.scoring import _assertion_search_text, _score_values


def rank_fts_entity_rows(
    connection: Any,
    rows: list[dict[str, Any]],
    tokens: list[str],
) -> list[dict[str, Any]]:
    """
    Rank entity rows returned by FTS.

    Args:
        connection: Open SQLite connection.
        rows (list[dict[str, Any]]): Entity rows.
        tokens (list[str]): Normalized query tokens.

    Returns:
        list[dict[str, Any]]: Ranked entity search results.
    """
    return _rank_entity_rows(
        connection=connection,
        rows=rows,
        tokens=tokens,
        existing_ids=set(),
        rank_base=0.2,
    )


def rank_fallback_entity_rows(
    connection: Any,
    rows: list[dict[str, Any]],
    tokens: list[str],
    existing_ids: set[int],
) -> list[dict[str, Any]]:
    """
    Rank entity rows outside FTS with token and fuzzy matching.

    Args:
        connection: Open SQLite connection.
        rows (list[dict[str, Any]]): Entity rows.
        tokens (list[str]): Normalized query tokens.
        existing_ids (set[int]): IDs already returned by FTS.

    Returns:
        list[dict[str, Any]]: Ranked entity search results.
    """
    return _rank_entity_rows(
        connection=connection,
        rows=rows,
        tokens=tokens,
        existing_ids=existing_ids,
        rank_base=1.1,
    )


def _rank_entity_rows(
    connection: Any,
    rows: list[dict[str, Any]],
    tokens: list[str],
    existing_ids: set[int],
    rank_base: float,
) -> list[dict[str, Any]]:
    """
    Rank entity rows using shared entity scoring rules.

    Args:
        connection: Open SQLite connection.
        rows (list[dict[str, Any]]): Entity rows.
        tokens (list[str]): Normalized query tokens.
        existing_ids (set[int]): IDs to skip.
        rank_base (float): Rank offset used to preserve search source priority.

    Returns:
        list[dict[str, Any]]: Ranked entity search results.
    """
    ranked_results: list[dict[str, Any]] = []
    for row in rows:
        entity_id: int = int(row["id"])
        if entity_id in existing_ids:
            continue
        type_assertions: list[dict[str, Any]] = _type_assertions_for_entity(
            connection=connection,
            entity_id=entity_id,
        )
        row["type_assertions"] = type_assertions
        score: float = _score_values(
            tokens=tokens,
            values=[
                row.get("entity_class"),
                row.get("canonical_name"),
                row.get("normalized_name"),
                row.get("description"),
                row.get("source_path"),
                _assertion_search_text(assertions=type_assertions),
            ],
        )
        if score <= 0.0:
            continue
        ranked_results.append(
            {
                "kind": "entity",
                "rank": rank_base - score,
                "data": _entity_payload(connection=connection, row=row),
            },
        )
    return ranked_results
