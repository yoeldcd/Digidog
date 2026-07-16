# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Row-to-payload builders for knowledge graph read models."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any


def _entity_payload(connection: Any, row: dict[str, Any]) -> dict[str, Any]:
    """
    Build an enriched entity search payload.

    Args:
        connection: Open SQLite connection.
        row: Entity row.

    Returns:
        dict[str, Any]: Entity payload with source, entities, and adjacent relations.
    """
    if "type_assertions" not in row and row.get("id") is not None:
        row["type_assertions"] = _type_assertions_for_entity(
            connection=connection,
            entity_id=int(row["id"]),
        )
    entity = _entity_from_row(row=row)
    row["entities"] = [entity]
    row["relations"] = _adjacent_relation_payloads(connection=connection, entity_id=int(row["id"]))
    return row


def _evidence_payload(row: dict[str, Any]) -> dict[str, Any]:
    """
    Build an enriched evidence search payload.

    Args:
        row: Evidence row.

    Returns:
        dict[str, Any]: Evidence payload.
    """
    row["content_excerpt"] = str(row.get("quote") or "")
    row["entities"] = []
    row["relations"] = []
    return row


def _adjacent_relation_payloads(connection: Any, entity_id: int, limit: int = 8) -> list[dict[str, Any]]:
    """
    Return relation payloads adjacent to an entity.

    Args:
        connection: Open SQLite connection.
        entity_id: Entity identifier.
        limit: Maximum relations.

    Returns:
        list[dict[str, Any]]: Relation payloads.
    """
    rows = connection.execute(
        """
        SELECT
            relations.*,
            sources.path AS source_path,
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
        WHERE relations.subject_entity_id = ? OR relations.object_entity_id = ?
        ORDER BY relations.confidence DESC, relations.id DESC
        LIMIT ?
        """,
        (entity_id, entity_id, limit),
    ).fetchall()
    return [_relation_payload(row=dict(row), connection=connection) for row in rows]


def _entity_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """
    Build a compact entity payload from an entity row.

    Args:
        row: Entity row.

    Returns:
        dict[str, Any]: Entity payload.
    """
    return {
        "id": row.get("id"),
        "entity_class": row.get("entity_class", ""),
        "name": row.get("canonical_name", ""),
        "description": row.get("description", ""),
        "confidence": row.get("confidence", 0.0),
        "type_assertions": row.get("type_assertions", []),
    }


def _relation_subject_entity(row: dict[str, Any], connection: Any | None = None) -> dict[str, Any]:
    """
    Build the subject entity payload for a relation row.

    Args:
        row: Relation row.

    Returns:
        dict[str, Any]: Subject entity payload.
    """
    type_assertions: list[dict[str, Any]] = []
    if connection is not None and row.get("subject_entity_id") is not None:
        type_assertions = _type_assertions_for_entity(
            connection=connection,
            entity_id=int(row["subject_entity_id"]),
        )
    return {
        "id": row.get("subject_entity_id"),
        "entity_class": row.get("subject_class", ""),
        "name": row.get("subject_name", ""),
        "description": row.get("subject_description", ""),
        "confidence": row.get("subject_confidence", 0.0),
        "type_assertions": type_assertions,
    }


def _relation_object_entity(row: dict[str, Any], connection: Any | None = None) -> dict[str, Any]:
    """
    Build the object entity payload for a relation row.

    Args:
        row: Relation row.

    Returns:
        dict[str, Any]: Object entity payload.
    """
    type_assertions: list[dict[str, Any]] = []
    if connection is not None and row.get("object_entity_id") is not None:
        type_assertions = _type_assertions_for_entity(
            connection=connection,
            entity_id=int(row["object_entity_id"]),
        )
    return {
        "id": row.get("object_entity_id"),
        "entity_class": row.get("object_class", ""),
        "name": row.get("object_name", ""),
        "description": row.get("object_description", ""),
        "confidence": row.get("object_confidence", 0.0),
        "type_assertions": type_assertions,
    }


def _relation_payload(row: dict[str, Any], connection: Any | None = None) -> dict[str, Any]:
    """
    Build a compact relation payload from a relation row.

    Args:
        row: Relation row.

    Returns:
        dict[str, Any]: Relation payload.
    """
    return {
        "id": row.get("id"),
        "predicate": row.get("predicate", ""),
        "subject": _relation_subject_entity(row=row, connection=connection),
        "object": _relation_object_entity(row=row, connection=connection),
        "confidence": row.get("confidence", 0.0),
        "source_path": row.get("source_path", ""),
    }


def _type_assertions_for_entity(connection: Any, entity_id: int) -> list[dict[str, Any]]:
    """
    Return active source-scoped type assertions for one entity.

    Args:
        connection: Open SQLite connection.
        entity_id (int): Entity identifier.

    Returns:
        list[dict[str, Any]]: Assertion payloads with source metadata.
    """
    rows = connection.execute(
        """
        SELECT
            entity_type_assertions.*,
            sources.path AS source_path,
            sources.source_type AS source_type,
            sources.title AS source_title
        FROM entity_type_assertions
        LEFT JOIN sources ON sources.id = entity_type_assertions.source_id
        WHERE entity_type_assertions.entity_id = ?
            AND entity_type_assertions.status != 'rejected'
        ORDER BY entity_type_assertions.confidence DESC, entity_type_assertions.id ASC
        """,
        (entity_id,),
    ).fetchall()
    return [dict(row) for row in rows]
