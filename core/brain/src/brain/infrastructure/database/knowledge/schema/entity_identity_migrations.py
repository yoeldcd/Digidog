# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Entity identity migrations for knowledge schema upgrades."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
import time

# Application Modules Imports
from brain.infrastructure.database.knowledge.schema.migration_helpers import table_exists
from brain.infrastructure.database.knowledge.schema.type_assertion_migrations import upsert_entity_type_assertion


def merge_duplicate_entities_by_normalized_name(connection: sqlite3.Connection) -> None:
    """
    Collapse active duplicate entities that differ only by classification.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    groups = connection.execute(
        """
        SELECT normalized_name
        FROM entities
        WHERE status != 'merged'
        GROUP BY normalized_name
        HAVING COUNT(*) > 1
        """,
    ).fetchall()
    for group in groups:
        normalized_name: str = str(group["normalized_name"])
        rows = connection.execute(
            """
            SELECT *
            FROM entities
            WHERE normalized_name = ? AND status != 'merged'
            ORDER BY confidence DESC, id ASC
            """,
            (normalized_name,),
        ).fetchall()
        if len(rows) <= 1:
            continue

        canonical_row = rows[0]
        canonical_id: int = int(canonical_row["id"])
        longest_description: str = max(
            (str(row["description"] or "") for row in rows),
            key=len,
            default=str(canonical_row["description"] or ""),
        )
        highest_confidence: float = max(float(row["confidence"] or 0.65) for row in rows)
        now_timestamp = time.time()
        connection.execute(
            """
            UPDATE entities
            SET description = CASE
                    WHEN length(?) > length(description) THEN ? ELSE description
                END,
                confidence = max(confidence, ?),
                updated_at = ?
            WHERE id = ?
            """,
            (longest_description, longest_description, highest_confidence, now_timestamp, canonical_id),
        )

        for duplicate_row in rows[1:]:
            duplicate_id: int = int(duplicate_row["id"])
            upsert_entity_type_assertion(
                connection=connection,
                entity_id=canonical_id,
                source_id=int(duplicate_row["source_id"]) if duplicate_row["source_id"] is not None else None,
                entity_class=str(duplicate_row["entity_class"]),
                description=str(duplicate_row["description"] or ""),
                confidence=float(duplicate_row["confidence"] or 0.65),
                status="active",
                timestamp=now_timestamp,
            )
            _move_entity_type_assertions(
                connection=connection,
                duplicate_id=duplicate_id,
                canonical_id=canonical_id,
                timestamp=now_timestamp,
            )
            _move_entity_aliases(
                connection=connection,
                duplicate_id=duplicate_id,
                canonical_id=canonical_id,
            )
            _move_entity_relations(
                connection=connection,
                duplicate_id=duplicate_id,
                canonical_id=canonical_id,
            )
            connection.execute(
                """
                UPDATE entities
                SET status = 'merged',
                    merged_into_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (canonical_id, now_timestamp, duplicate_id),
            )
            if table_exists(connection=connection, table_name="entity_fts"):
                connection.execute("DELETE FROM entity_fts WHERE entity_id = ?", (duplicate_id,))


def _move_entity_type_assertions(
    connection: sqlite3.Connection,
    duplicate_id: int,
    canonical_id: int,
    timestamp: float,
) -> None:
    """
    Re-anchor type assertions from a merged entity to its canonical entity.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
        duplicate_id (int): Merged entity ID.
        canonical_id (int): Canonical entity ID.
        timestamp (float): Migration timestamp.
    """
    rows = connection.execute(
        """
        SELECT source_id, entity_class, description, confidence, status
        FROM entity_type_assertions
        WHERE entity_id = ?
        """,
        (duplicate_id,),
    ).fetchall()
    for row in rows:
        upsert_entity_type_assertion(
            connection=connection,
            entity_id=canonical_id,
            source_id=int(row["source_id"]) if row["source_id"] is not None else None,
            entity_class=str(row["entity_class"]),
            description=str(row["description"] or ""),
            confidence=float(row["confidence"] or 0.65),
            status=str(row["status"] or "active"),
            timestamp=timestamp,
        )
    connection.execute("DELETE FROM entity_type_assertions WHERE entity_id = ?", (duplicate_id,))


def _move_entity_aliases(connection: sqlite3.Connection, duplicate_id: int, canonical_id: int) -> None:
    """
    Re-anchor aliases from a merged entity to its canonical entity.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
        duplicate_id (int): Merged entity ID.
        canonical_id (int): Canonical entity ID.
    """
    alias_rows = connection.execute(
        "SELECT alias, normalized_alias, created_at FROM aliases WHERE entity_id = ?",
        (duplicate_id,),
    ).fetchall()
    for row in alias_rows:
        connection.execute(
            """
            INSERT OR IGNORE INTO aliases(entity_id, alias, normalized_alias, created_at)
            VALUES(?, ?, ?, ?)
            """,
            (canonical_id, row["alias"], row["normalized_alias"], row["created_at"]),
        )
    connection.execute("DELETE FROM aliases WHERE entity_id = ?", (duplicate_id,))


def _move_entity_relations(connection: sqlite3.Connection, duplicate_id: int, canonical_id: int) -> None:
    """
    Re-anchor relations from a merged entity to its canonical entity.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
        duplicate_id (int): Merged entity ID.
        canonical_id (int): Canonical entity ID.
    """
    relation_rows = connection.execute(
        """
        SELECT *
        FROM relations
        WHERE subject_entity_id = ? OR object_entity_id = ?
        """,
        (duplicate_id, duplicate_id),
    ).fetchall()
    for row in relation_rows:
        relation_id: int = int(row["id"])
        new_subject_id: int = canonical_id if int(row["subject_entity_id"]) == duplicate_id else int(row["subject_entity_id"])
        new_object_id: int = canonical_id if int(row["object_entity_id"]) == duplicate_id else int(row["object_entity_id"])
        existing_row = connection.execute(
            """
            SELECT id
            FROM relations
            WHERE source_id = ?
                AND subject_entity_id = ?
                AND predicate = ?
                AND object_entity_id = ?
                AND id != ?
            """,
            (row["source_id"], new_subject_id, row["predicate"], new_object_id, relation_id),
        ).fetchone()
        if existing_row is not None:
            connection.execute("DELETE FROM relations WHERE id = ?", (relation_id,))
            continue
        connection.execute(
            """
            UPDATE relations
            SET subject_entity_id = ?,
                object_entity_id = ?
            WHERE id = ?
            """,
            (new_subject_id, new_object_id, relation_id),
        )


def create_entity_identity_indexes(connection: sqlite3.Connection) -> None:
    """
    Ensure active entities are unique by stable normalized name.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_active_normalized_name
        ON entities(normalized_name)
        WHERE status != 'merged'
        """,
    )
