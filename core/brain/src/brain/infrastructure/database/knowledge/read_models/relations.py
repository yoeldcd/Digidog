# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Relation read models for the knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def list_relation_views(repository: "KnowledgeRepository") -> list[dict[str, Any]]:
    """
    Return all stored relations.

    Args:
        repository (KnowledgeRepository): Knowledge repository.

    Returns:
        list[dict[str, Any]]: Relation row payloads.
    """
    with repository.session() as connection:
        rows = connection.execute(
            """
            SELECT
                relations.*,
                subjects.entity_class AS subject_class,
                subjects.canonical_name AS subject_name,
                objects.entity_class AS object_class,
                objects.canonical_name AS object_name,
                sources.path AS source_path
            FROM relations
            JOIN entities AS subjects ON subjects.id = relations.subject_entity_id
            JOIN entities AS objects ON objects.id = relations.object_entity_id
            LEFT JOIN sources ON sources.id = relations.source_id
            ORDER BY relations.id DESC
            """,
        ).fetchall()
    return [dict(row) for row in rows]


def recurrent_literal_relation_views(
    repository: "KnowledgeRepository",
    min_sources: int = 2,
) -> list[dict[str, Any]]:
    """
    Return repeated graph relations supported by multiple sources.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        min_sources (int): Required distinct source count.

    Returns:
        list[dict[str, Any]]: Recurrent relation groups.
    """
    with repository.session() as connection:
        rows = connection.execute(
            """
            SELECT
                MIN(relations.source_id) AS source_id,
                relations.subject_entity_id,
                relations.predicate,
                relations.object_entity_id,
                subjects.canonical_name AS subject_name,
                objects.canonical_name AS object_name,
                COUNT(DISTINCT relations.source_id) AS source_count,
                MAX(relations.confidence) AS confidence
            FROM relations
            JOIN entities AS subjects ON subjects.id = relations.subject_entity_id
            JOIN entities AS objects ON objects.id = relations.object_entity_id
            GROUP BY relations.subject_entity_id, relations.predicate, relations.object_entity_id
            HAVING source_count >= ?
            """,
            (min_sources,),
        ).fetchall()
    return [dict(row) for row in rows]
