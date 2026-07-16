# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Entity type assertion migrations for knowledge schema upgrades."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
import time


def create_entity_type_assertion_contract(connection: sqlite3.Connection) -> None:
    """
    Ensure source-scoped entity type assertions exist in migrated databases.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS entity_type_assertions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER NOT NULL,
            source_id INTEGER,
            entity_class TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0.65,
            status TEXT NOT NULL DEFAULT 'active',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            UNIQUE(entity_id, source_id, entity_class),
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_entity_type_assertions_entity
        ON entity_type_assertions(entity_id);

        CREATE INDEX IF NOT EXISTS idx_entity_type_assertions_class
        ON entity_type_assertions(entity_class);

        CREATE INDEX IF NOT EXISTS idx_entity_type_assertions_source
        ON entity_type_assertions(source_id);
        """,
    )


def seed_entity_type_assertions_from_entities(connection: sqlite3.Connection) -> None:
    """
    Preserve existing entity classes as source-scoped type assertions.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    now_timestamp: float = time.time()
    rows = connection.execute(
        """
        SELECT id, source_id, entity_class, description, confidence, status
        FROM entities
        WHERE status != 'merged'
        """,
    ).fetchall()
    for row in rows:
        upsert_entity_type_assertion(
            connection=connection,
            entity_id=int(row["id"]),
            source_id=int(row["source_id"]) if row["source_id"] is not None else None,
            entity_class=str(row["entity_class"]),
            description=str(row["description"] or ""),
            confidence=float(row["confidence"] or 0.65),
            status=str(row["status"] or "active"),
            timestamp=now_timestamp,
        )


def upsert_entity_type_assertion(
    connection: sqlite3.Connection,
    entity_id: int,
    source_id: int | None,
    entity_class: str,
    description: str,
    confidence: float,
    status: str,
    timestamp: float,
) -> None:
    """
    Insert or update one entity type assertion.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
        entity_id (int): Stable entity identifier.
        source_id (int | None): Source that supports the type assertion.
        entity_class (str): Asserted class key.
        description (str): Source-scoped description.
        confidence (float): Assertion confidence.
        status (str): Assertion lifecycle status.
        timestamp (float): Creation or update timestamp.
    """
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
        (entity_id, source_id, entity_class, description, confidence, status, timestamp, timestamp),
    )
