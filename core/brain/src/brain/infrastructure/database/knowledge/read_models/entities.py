"""Entity read models for the knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
from typing import TYPE_CHECKING, Any

# Application Modules Imports
from brain.infrastructure.database.knowledge.read_models.payloads import _type_assertions_for_entity

if TYPE_CHECKING:
    from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def get_entity_view(repository: "KnowledgeRepository", entity_ref: int | str) -> dict[str, Any] | None:
    """
    Return an entity with aliases and relations.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        entity_ref (int | str): Entity identifier, name, or alias.

    Returns:
        dict[str, Any] | None: Entity graph payload when found.
    """
    entity_row: dict[str, Any] | None = repository.find_entity_by_ref(entity_ref)
    if entity_row is None:
        return None
    entity_id: int = int(entity_row["id"])
    with repository.session() as connection:
        aliases = connection.execute("SELECT * FROM aliases WHERE entity_id = ?", (entity_id,)).fetchall()
        type_assertions = _type_assertions_for_entity(connection=connection, entity_id=entity_id)
        relations = connection.execute(
            """
            SELECT
                relations.*,
                object_entities.canonical_name AS object_name,
                sources.path AS source_path
            FROM relations
            LEFT JOIN entities AS object_entities ON object_entities.id = relations.object_entity_id
            LEFT JOIN sources ON sources.id = relations.source_id
            WHERE relations.subject_entity_id = ?
            ORDER BY relations.id DESC
            """,
            (entity_id,),
        ).fetchall()
    payload: dict[str, Any] = dict(entity_row)
    payload["aliases"] = [dict(row) for row in aliases]
    payload["type_assertions"] = type_assertions
    payload["relations"] = [dict(row) for row in relations]
    return payload


def list_entity_views(repository: "KnowledgeRepository") -> list[dict[str, Any]]:
    """
    Return all non-merged entities.

    Args:
        repository (KnowledgeRepository): Knowledge repository.

    Returns:
        list[dict[str, Any]]: Entity row payloads.
    """
    with repository.session() as connection:
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
            ORDER BY entities.entity_class, entities.canonical_name
            """,
        ).fetchall()
    entity_rows: list[dict[str, Any]] = []
    with repository.session() as connection:
        for row in rows:
            payload = dict(row)
            payload["type_assertions"] = _type_assertions_for_entity(
                connection=connection,
                entity_id=int(payload["id"]),
            )
            entity_rows.append(payload)
    return entity_rows
