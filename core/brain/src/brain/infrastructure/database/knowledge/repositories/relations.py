"""KnowledgeRelationRepositoryMixin for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
import time
from typing import Any

# Application Modules Imports
from brain.application.knowledge.models.dtos.graph import RelationDTO


class KnowledgeRelationRepositoryMixin:
    def upsert_relation(self, relation_dto: RelationDTO) -> int:
        """
        Insert or update a relation.

        Args:
            relation_dto (RelationDTO): Relation DTO.

        Returns:
            int: Relation database identifier.
        """
        if relation_dto.source_id is None:
            raise ValueError("Relation source_id is required.")
        if relation_dto.subject_id is None:
            raise ValueError("Relation subject_id is required.")
        if relation_dto.object_id is None:
            raise ValueError("Relation object_id is required.")

        self.ensure_relation_type(
            name=relation_dto.predicate,
            description=f"Discovered relation type `{relation_dto.predicate}`.",
        )
        subject_row: dict[str, Any] | None = self.find_entity_by_ref(relation_dto.subject_id)
        if subject_row is None:
            raise ValueError(f"Unknown relation subject: {relation_dto.subject_id}")

        object_row: dict[str, Any] | None = self.find_entity_by_ref(relation_dto.object_id)
        if object_row is None:
            raise ValueError(f"Unknown relation object: {relation_dto.object_id}")

        subject_id: int = int(subject_row["id"])
        object_id: int = int(object_row["id"])
        relation_values_by_column: dict[str, Any] = {
            "source_id": relation_dto.source_id,
            "subject_entity_id": subject_id,
            "predicate": relation_dto.predicate,
            "object_entity_id": object_id,
            "confidence": relation_dto.confidence,
        }
        legacy_column_values: dict[str, Any] = {
            "status": "active",
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        with self.session() as connection:
            existing_row = connection.execute(
                """
                SELECT id FROM relations
                WHERE source_id = ?
                    AND subject_entity_id = ?
                    AND predicate = ?
                    AND object_entity_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    relation_dto.source_id,
                    subject_id,
                    relation_dto.predicate,
                    object_id,
                ),
            ).fetchone()
            if existing_row is not None:
                return int(existing_row["id"])

            relation_columns: set[str] = self._table_columns(connection=connection, table_name="relations")
            for column_name, column_value in legacy_column_values.items():
                if column_name in relation_columns:
                    relation_values_by_column[column_name] = column_value
            insert_columns: list[str] = [
                column_name
                for column_name in (
                    "source_id",
                    "subject_entity_id",
                    "predicate",
                    "object_entity_id",
                    "confidence",
                    "status",
                    "created_at",
                    "updated_at",
                )
                if column_name in relation_values_by_column
            ]
            placeholders: str = ", ".join("?" for _ in insert_columns)
            column_sql: str = ", ".join(insert_columns)
            insert_values: tuple[Any, ...] = tuple(
                relation_values_by_column[column_name]
                for column_name in insert_columns
            )
            connection.execute(
                f"INSERT INTO relations({column_sql}) VALUES({placeholders})",
                insert_values,
            )
            row = connection.execute(
                """
                SELECT id FROM relations
                WHERE source_id = ?
                    AND subject_entity_id = ?
                    AND predicate = ?
                    AND object_entity_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    relation_dto.source_id,
                    subject_id,
                    relation_dto.predicate,
                    object_id,
                ),
            ).fetchone()
            connection.commit()
        return int(row["id"])

    def list_relations(self) -> list[dict[str, Any]]:
        """
        Return all stored relations.

        Returns:
            list[dict[str, Any]]: Relation row payloads.
        """
        from brain.infrastructure.database.knowledge.read_models.relations import list_relation_views

        return list_relation_views(repository=self)

    def recurrent_literal_relations(self, min_sources: int = 2) -> list[dict[str, Any]]:
        """
        Return repeated graph relations supported by multiple sources.

        Args:
            min_sources (int): Required distinct source count.

        Returns:
            list[dict[str, Any]]: Recurrent relation groups.
        """
        from brain.infrastructure.database.knowledge.read_models.relations import recurrent_literal_relation_views

        return recurrent_literal_relation_views(repository=self, min_sources=min_sources)

    @staticmethod
    def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
        """
        Return column names for one SQLite table.

        Args:
            connection (sqlite3.Connection): Open SQLite connection.
            table_name (str): SQLite table name.

        Returns:
            set[str]: Available column names.
        """
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}
