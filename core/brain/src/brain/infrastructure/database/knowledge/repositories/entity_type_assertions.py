# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Entity type assertion persistence for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
import time
from typing import Any


class KnowledgeEntityTypeAssertionRepositoryMixin:
    """Persist and query source-scoped entity type assertions."""

    def list_entity_type_assertions(self, entity_id: int | None = None) -> list[dict[str, Any]]:
        """
        Return source-scoped type assertions.

        Args:
            entity_id (int | None): Optional entity filter.

        Returns:
            list[dict[str, Any]]: Type assertion rows with source metadata.
        """
        query_text: str = """
            SELECT
                entity_type_assertions.*,
                sources.path AS source_path,
                sources.source_type AS source_type,
                sources.title AS source_title
            FROM entity_type_assertions
            LEFT JOIN sources ON sources.id = entity_type_assertions.source_id
        """
        params: tuple[Any, ...] = ()
        if entity_id is not None:
            query_text += " WHERE entity_type_assertions.entity_id = ?"
            params = (entity_id,)
        query_text += " ORDER BY entity_type_assertions.confidence DESC, entity_type_assertions.id ASC"
        with self.session() as connection:
            rows = connection.execute(query_text, params).fetchall()
        return [dict(row) for row in rows]

    def _upsert_entity_type_assertion(
        self,
        connection: sqlite3.Connection,
        entity_id: int,
        source_id: int | None,
        entity_class: str,
        description: str,
        confidence: float,
        status: str,
    ) -> None:
        """
        Insert or update one source-scoped type assertion.

        Args:
            connection (sqlite3.Connection): Open SQLite connection.
            entity_id (int): Stable entity identifier.
            source_id (int | None): Source that supports the assertion.
            entity_class (str): Asserted entity class.
            description (str): Source-scoped description.
            confidence (float): Assertion confidence.
            status (str): Assertion status.
        """
        now_timestamp: float = time.time()
        connection.execute(
            """
            INSERT INTO entity_type_assertions(
                entity_id,
                source_id,
                entity_class,
                description,
                confidence,
                status,
                created_at,
                updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_id, source_id, entity_class) DO UPDATE SET
                description = CASE
                    WHEN length(excluded.description) > length(entity_type_assertions.description)
                    THEN excluded.description
                    ELSE entity_type_assertions.description
                END,
                confidence = max(entity_type_assertions.confidence, excluded.confidence),
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                entity_id,
                source_id,
                entity_class,
                description,
                confidence,
                status,
                now_timestamp,
                now_timestamp,
            ),
        )
