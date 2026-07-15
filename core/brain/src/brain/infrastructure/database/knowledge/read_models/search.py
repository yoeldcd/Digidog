"""Repository search orchestration for the knowledge graph read model."""

from __future__ import annotations

# Standard Libraries Imports
from typing import TYPE_CHECKING, Any

from brain.infrastructure.database.knowledge.read_models.entity_search import (
    rank_fallback_entity_rows,
    rank_fts_entity_rows,
)
from brain.infrastructure.database.knowledge.read_models.evidence_search import (
    rank_fallback_evidence_rows,
    rank_fts_evidence_rows,
)
from brain.infrastructure.database.knowledge.read_models.relation_search import rank_relation_rows
from brain.infrastructure.database.knowledge.read_models.scoring import _query_tokens, build_fts_query
from brain.infrastructure.database.knowledge.read_models.search_queries import (
    fetch_entity_fts_rows,
    fetch_evidence_fts_rows,
    fetch_fallback_entity_rows,
    fetch_fallback_evidence_rows,
    fetch_relation_rows,
)

if TYPE_CHECKING:
    from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def search_repository(repository: "KnowledgeRepository", text: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search entities and evidence through SQLite FTS5.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        text (str): Search query.
        limit (int): Maximum result count.

    Returns:
        list[dict[str, Any]]: Ranked result payloads.
    """
    fts_query: str = build_fts_query(text)
    tokens: list[str] = _query_tokens(text=text)
    results: list[dict[str, Any]] = []
    with repository.session() as connection:
        entity_rows: list[dict[str, Any]] = fetch_entity_fts_rows(
            connection=connection,
            fts_query=fts_query,
            limit=limit,
        )
        evidence_rows: list[dict[str, Any]] = fetch_evidence_fts_rows(
            connection=connection,
            fts_query=fts_query,
            limit=limit,
        )
        results.extend(rank_fts_entity_rows(connection=connection, rows=entity_rows, tokens=tokens))
        results.extend(rank_fts_evidence_rows(rows=evidence_rows, tokens=tokens))
        results.extend(rank_relation_rows(connection=connection, rows=fetch_relation_rows(connection), tokens=tokens))
        results.extend(
            rank_fallback_entity_rows(
                connection=connection,
                rows=fetch_fallback_entity_rows(connection),
                tokens=tokens,
                existing_ids={int(row["id"]) for row in entity_rows},
            ),
        )
        results.extend(
            rank_fallback_evidence_rows(
                rows=fetch_fallback_evidence_rows(connection),
                tokens=tokens,
                existing_ids={int(row["id"]) for row in evidence_rows},
            ),
        )
    results.sort(key=lambda item: float(item["rank"]))
    return results[:limit]
