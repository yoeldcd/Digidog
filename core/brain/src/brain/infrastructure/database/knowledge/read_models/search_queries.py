# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""SQLite row collection queries for knowledge search read models."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any


def fetch_entity_fts_rows(connection: Any, fts_query: str, limit: int) -> list[dict[str, Any]]:
    """
    Return entity rows matched through the entity FTS table.

    Args:
        connection: Open SQLite connection.
        fts_query (str): Sanitized FTS query.
        limit (int): Maximum row count.

    Returns:
        list[dict[str, Any]]: Entity rows with source metadata.
    """
    rows = connection.execute(
        """
        SELECT
            entities.*,
            sources.path AS source_path,
            sources.source_type AS source_type,
            sources.title AS source_title,
            bm25(entity_fts) AS rank
        FROM entity_fts
        JOIN entities ON entities.id = entity_fts.entity_id
        LEFT JOIN sources ON sources.id = entities.source_id
        WHERE entity_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (fts_query, max(limit, 1)),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_evidence_fts_rows(connection: Any, fts_query: str, limit: int) -> list[dict[str, Any]]:
    """
    Return evidence rows matched through the evidence FTS table.

    Args:
        connection: Open SQLite connection.
        fts_query (str): Sanitized FTS query.
        limit (int): Maximum row count.

    Returns:
        list[dict[str, Any]]: Evidence rows with source metadata.
    """
    rows = connection.execute(
        """
        SELECT
            evidence.*,
            sources.path AS source_path,
            sources.source_type AS source_type,
            sources.title AS source_title,
            bm25(evidence_fts) AS rank
        FROM evidence_fts
        JOIN evidence ON evidence.id = evidence_fts.evidence_id
        JOIN sources ON sources.id = evidence.source_id
        WHERE evidence_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (fts_query, max(limit, 1)),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_relation_rows(connection: Any) -> list[dict[str, Any]]:
    """
    Return relation rows enriched with endpoint labels and source metadata.

    Args:
        connection: Open SQLite connection.

    Returns:
        list[dict[str, Any]]: Relation rows.
    """
    rows = connection.execute(
        """
        SELECT
            relations.*,
            sources.path AS source_path,
            sources.source_type AS source_type,
            sources.title AS source_title,
            subjects.entity_class AS subject_class,
            subjects.canonical_name AS subject_name,
            subjects.description AS subject_description,
            subjects.confidence AS subject_confidence,
            objects.entity_class AS object_class,
            objects.canonical_name AS object_name,
            objects.description AS object_description,
            objects.confidence AS object_confidence
        FROM relations
        JOIN entities AS subjects ON subjects.id = relations.subject_entity_id
        JOIN entities AS objects ON objects.id = relations.object_entity_id
        LEFT JOIN sources ON sources.id = relations.source_id
        """,
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_fallback_entity_rows(connection: Any) -> list[dict[str, Any]]:
    """
    Return non-merged entity rows for non-FTS fallback scoring.

    Args:
        connection: Open SQLite connection.

    Returns:
        list[dict[str, Any]]: Entity rows.
    """
    rows = connection.execute(
        """
        SELECT
            entities.*,
            sources.path AS source_path,
            sources.source_type AS source_type,
            sources.title AS source_title
        FROM entities
        LEFT JOIN sources ON sources.id = entities.source_id
        WHERE entities.status != 'merged'
        """,
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_fallback_evidence_rows(connection: Any) -> list[dict[str, Any]]:
    """
    Return evidence rows for non-FTS fallback scoring.

    Args:
        connection: Open SQLite connection.

    Returns:
        list[dict[str, Any]]: Evidence rows.
    """
    rows = connection.execute(
        """
        SELECT
            evidence.*,
            sources.path AS source_path,
            sources.source_type AS source_type,
            sources.title AS source_title
        FROM evidence
        JOIN sources ON sources.id = evidence.source_id
        """,
    ).fetchall()
    return [dict(row) for row in rows]
