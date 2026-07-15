"""Evidence result ranking for knowledge search read models."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.infrastructure.database.knowledge.read_models.payloads import _evidence_payload
from brain.infrastructure.database.knowledge.read_models.scoring import _score_values


def rank_fts_evidence_rows(
    rows: list[dict[str, Any]],
    tokens: list[str],
) -> list[dict[str, Any]]:
    """
    Rank evidence rows returned by FTS.

    Args:
        rows (list[dict[str, Any]]): Evidence rows.
        tokens (list[str]): Normalized query tokens.

    Returns:
        list[dict[str, Any]]: Ranked evidence search results.
    """
    return _rank_evidence_rows(
        rows=rows,
        tokens=tokens,
        existing_ids=set(),
        rank_base=0.25,
    )


def rank_fallback_evidence_rows(
    rows: list[dict[str, Any]],
    tokens: list[str],
    existing_ids: set[int],
) -> list[dict[str, Any]]:
    """
    Rank evidence rows outside FTS with token and fuzzy matching.

    Args:
        rows (list[dict[str, Any]]): Evidence rows.
        tokens (list[str]): Normalized query tokens.
        existing_ids (set[int]): IDs already returned by FTS.

    Returns:
        list[dict[str, Any]]: Ranked evidence search results.
    """
    return _rank_evidence_rows(
        rows=rows,
        tokens=tokens,
        existing_ids=existing_ids,
        rank_base=1.2,
    )


def _rank_evidence_rows(
    rows: list[dict[str, Any]],
    tokens: list[str],
    existing_ids: set[int],
    rank_base: float,
) -> list[dict[str, Any]]:
    """
    Rank evidence rows using shared evidence scoring rules.

    Args:
        rows (list[dict[str, Any]]): Evidence rows.
        tokens (list[str]): Normalized query tokens.
        existing_ids (set[int]): IDs to skip.
        rank_base (float): Rank offset used to preserve search source priority.

    Returns:
        list[dict[str, Any]]: Ranked evidence search results.
    """
    ranked_results: list[dict[str, Any]] = []
    for row in rows:
        evidence_id: int = int(row["id"])
        if evidence_id in existing_ids:
            continue
        score: float = _score_values(
            tokens=tokens,
            values=[
                row.get("quote"),
                row.get("location"),
                row.get("source_path"),
            ],
        )
        if score <= 0.0:
            continue
        ranked_results.append(
            {
                "kind": "evidence",
                "rank": rank_base - score,
                "data": _evidence_payload(row=row),
            },
        )
    return ranked_results
