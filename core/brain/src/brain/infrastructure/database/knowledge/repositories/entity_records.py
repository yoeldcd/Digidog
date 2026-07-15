"""Entity record mutations for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
import time

# Application Modules Imports
from brain.application.knowledge.models.dtos.graph import EntityDTO
from brain.application.knowledge.models.ontology_keys import normalize_label


class KnowledgeEntityRecordsRepositoryMixin:
    """Persist canonical entity rows and refresh entity search projections."""

    def upsert_entity(self, entity_dto: EntityDTO) -> int:
        """
        Insert or update a stable entity by normalized name.

        Args:
            entity_dto (EntityDTO): Entity DTO.

        Returns:
            int: Entity database identifier.
        """
        from brain.application.knowledge.models.entity_classes import is_class_definition_entity
        from brain.application.knowledge.models.ontology_definitions import CORE_ENTITY_CLASS_DEFINITIONS

        if is_class_definition_entity(entity_class=entity_dto.entity_class):
            self.ensure_entity_class(
                name=entity_dto.canonical_name,
                description=entity_dto.description,
            )
        elif entity_dto.entity_class in CORE_ENTITY_CLASS_DEFINITIONS:
            self.ensure_entity_class(
                name=entity_dto.entity_class,
                description=f"Core entity class `{entity_dto.entity_class}`.",
            )
        normalized_name: str = normalize_label(entity_dto.canonical_name)
        now_timestamp: float = time.time()
        with self.session() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM entities
                WHERE normalized_name = ? AND status != 'merged'
                ORDER BY confidence DESC, id ASC
                LIMIT 1
                """,
                (normalized_name,),
            ).fetchone()
            if row is None:
                cursor = connection.execute(
                    """
                    INSERT INTO entities(
                        source_id,
                        entity_class,
                        canonical_name,
                        normalized_name,
                        description,
                        confidence,
                        status,
                        created_at,
                        updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity_dto.source_id,
                        entity_dto.entity_class,
                        entity_dto.canonical_name,
                        normalized_name,
                        entity_dto.description,
                        entity_dto.confidence,
                        "active",
                        now_timestamp,
                        now_timestamp,
                    ),
                )
                entity_id = int(cursor.lastrowid)
            else:
                entity_id = int(row["id"])
                connection.execute(
                    """
                    UPDATE entities
                    SET source_id = COALESCE(source_id, ?),
                        description = CASE
                            WHEN length(?) > length(description)
                            THEN ?
                            ELSE description
                        END,
                        confidence = max(confidence, ?),
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        entity_dto.source_id,
                        entity_dto.description,
                        entity_dto.description,
                        entity_dto.confidence,
                        now_timestamp,
                        entity_id,
                    ),
                )
            self._upsert_entity_type_assertion(
                connection=connection,
                entity_id=entity_id,
                source_id=entity_dto.source_id,
                entity_class=entity_dto.entity_class,
                description=entity_dto.description,
                confidence=entity_dto.confidence,
                status="active",
            )
            self._refresh_entity_fts(connection=connection, entity_id=entity_id)
            connection.commit()
        return entity_id

    def _refresh_entity_fts(self, connection: sqlite3.Connection, entity_id: int) -> None:
        """
        Refresh one entity FTS row.

        Args:
            connection (sqlite3.Connection): Open SQLite connection.
            entity_id (int): Entity identifier.
        """
        row = connection.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
        if row is None:
            return
        connection.execute("DELETE FROM entity_fts WHERE entity_id = ?", (entity_id,))
        connection.execute(
            """
            INSERT INTO entity_fts(entity_id, canonical_name, description, entity_class)
            VALUES(?, ?, ?, ?)
            """,
            (entity_id, row["canonical_name"], row["description"], row["entity_class"]),
        )
