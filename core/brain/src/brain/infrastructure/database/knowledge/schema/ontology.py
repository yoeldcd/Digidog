"""Core ontology seeding and cache maintenance for knowledge graph storage."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
import time

# Application Modules Imports
from brain.application.knowledge.models.entity_classes import canonical_class_name
from brain.application.knowledge.models.ontology_definitions import (
    CORE_ENTITY_CLASS_DEFINITIONS,
    RELATION_TYPE_DEFINITIONS,
)


def seed_core_ontology(connection: sqlite3.Connection) -> None:
    """
    Seed minimal structural ontology primitives.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    created_at: float = time.time()
    relation_rows: list[tuple[str, str, str, float]] = [
        (name, description, "active", created_at)
        for name, description in RELATION_TYPE_DEFINITIONS.items()
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO relation_types(name, description, status, created_at)
        VALUES(?, ?, ?, ?)
        """,
        relation_rows,
    )

    entity_rows: list[tuple[str, str, str, float]] = [
        (name, description, "active", created_at)
        for name, description in CORE_ENTITY_CLASS_DEFINITIONS.items()
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO entity_classes(name, description, status, created_at)
        VALUES(?, ?, ?, ?)
        """,
        entity_rows,
    )


def sync_entity_class_cache_from_cls(connection: sqlite3.Connection) -> None:
    """
    Materialize discovered `CLS` entities into the entity class cache.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    cls_rows = connection.execute(
        """
        SELECT canonical_name, description
        FROM entities
        WHERE entity_class = 'CLS' AND status != 'merged'
        """,
    ).fetchall()
    if not cls_rows:
        return

    created_at: float = time.time()
    class_rows: list[tuple[str, str, str, float]] = [
        (
            canonical_class_name(str(row["canonical_name"])),
            str(row["description"] or "Discovered class defined by a CLS entity."),
            "active",
            created_at,
        )
        for row in cls_rows
    ]
    connection.executemany(
        """
        INSERT INTO entity_classes(name, description, status, created_at)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            description = CASE
                WHEN length(excluded.description) > length(entity_classes.description)
                THEN excluded.description
                ELSE entity_classes.description
            END,
            status = excluded.status
        """,
        class_rows,
    )


def prune_unbacked_non_core_ontology(connection: sqlite3.Connection) -> None:
    """
    Remove unused ontology rows that are neither core nor model-suggested.

    Existing rows with entities, relations, or schema suggestions are preserved
    because they are data-backed discovered ontology terms.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    cls_rows = connection.execute(
        """
        SELECT canonical_name
        FROM entities
        WHERE entity_class = 'CLS' AND status != 'merged'
        """,
    ).fetchall()
    cached_class_names: tuple[str, ...] = tuple(
        sorted(
            set(CORE_ENTITY_CLASS_DEFINITIONS)
            | {
                canonical_class_name(str(row["canonical_name"]))
                for row in cls_rows
            },
        ),
    )
    core_relation_names: tuple[str, ...] = tuple(RELATION_TYPE_DEFINITIONS)
    class_placeholders: str = ",".join("?" for _ in cached_class_names)
    relation_placeholders: str = ",".join("?" for _ in core_relation_names)
    connection.execute(
        f"""
        DELETE FROM entity_classes
        WHERE name NOT IN ({class_placeholders})
        """,
        cached_class_names,
    )
    connection.execute(
        f"""
        DELETE FROM relation_types
        WHERE name NOT IN ({relation_placeholders})
            AND NOT EXISTS (
                SELECT 1 FROM relations
                WHERE relations.predicate = relation_types.name
            )
            AND NOT EXISTS (
                SELECT 1 FROM ontology_suggestions
                WHERE ontology_suggestions.suggestion_type = 'relation_type'
                    AND ontology_suggestions.name = relation_types.name
            )
        """,
        core_relation_names,
    )
