# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Durable table DDL for the knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3


def create_tables(connection: sqlite3.Connection) -> None:
    """
    Create durable knowledge graph tables.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            quote TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL UNIQUE,
            confidence REAL NOT NULL DEFAULT 1,
            created_at REAL NOT NULL,
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS entity_classes (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            entity_class TEXT NOT NULL,
            canonical_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0.65,
            status TEXT NOT NULL DEFAULT 'active',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            merged_into_id INTEGER,
            UNIQUE(entity_class, normalized_name),
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE SET NULL,
            FOREIGN KEY(merged_into_id) REFERENCES entities(id) ON DELETE SET NULL
        );

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

        CREATE TABLE IF NOT EXISTS aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER NOT NULL,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(entity_id, normalized_alias),
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS relation_types (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            subject_entity_id INTEGER NOT NULL,
            predicate TEXT NOT NULL,
            object_entity_id INTEGER NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.65,
            UNIQUE(source_id, subject_entity_id, predicate, object_entity_id),
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE,
            FOREIGN KEY(subject_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(object_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(predicate) REFERENCES relation_types(name) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS ontology_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suggestion_type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0.65,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at REAL NOT NULL,
            UNIQUE(suggestion_type, name)
        );

        CREATE TABLE IF NOT EXISTS pending_deltas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            validation_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at REAL NOT NULL,
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS applied_deltas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS dream_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at REAL NOT NULL,
            finished_at REAL NOT NULL,
            status TEXT NOT NULL,
            dry_run INTEGER NOT NULL,
            sources_seen INTEGER NOT NULL DEFAULT 0,
            deltas_proposed INTEGER NOT NULL DEFAULT 0,
            deltas_applied INTEGER NOT NULL DEFAULT 0,
            errors_json TEXT NOT NULL DEFAULT '[]',
            summary TEXT NOT NULL DEFAULT ''
        );
        """
    )
