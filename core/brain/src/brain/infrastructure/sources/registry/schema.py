"""SQLite schema for source registries."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3


def initialize_registry_schema(connection: sqlite3.Connection) -> None:
    """
    Ensure source registry tables exist.

    Args:
        connection: Open SQLite connection.
    """
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            source_type TEXT NOT NULL,
            path TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            mtime REAL NOT NULL DEFAULT 0,
            size_label TEXT NOT NULL DEFAULT '0KB',
            line_count_label TEXT NOT NULL DEFAULT '0',
            entry_count INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            updated_at REAL NOT NULL DEFAULT 0,
            UNIQUE(scope, path)
        );

        CREATE TABLE IF NOT EXISTS source_consumers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            consumer TEXT NOT NULL,
            processed_mtime REAL NOT NULL DEFAULT 0,
            processed_at REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'processed',
            UNIQUE(source_id, consumer)
        );

        CREATE INDEX IF NOT EXISTS idx_sources_scope_active
            ON sources(scope, active);
        CREATE INDEX IF NOT EXISTS idx_sources_scope_path
            ON sources(scope, path);
        CREATE INDEX IF NOT EXISTS idx_source_consumers_consumer
            ON source_consumers(consumer);
        """,
    )
    ensure_registry_column(
        connection=connection,
        table_name="sources",
        column_name="size_label",
        column_sql="size_label TEXT NOT NULL DEFAULT '0KB'",
    )
    ensure_registry_column(
        connection=connection,
        table_name="sources",
        column_name="line_count_label",
        column_sql="line_count_label TEXT NOT NULL DEFAULT '0'",
    )
    ensure_registry_column(
        connection=connection,
        table_name="sources",
        column_name="entry_count",
        column_sql="entry_count INTEGER NOT NULL DEFAULT 0",
    )
    connection.commit()


def ensure_registry_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    """
    Add a registry table column when an existing database predates it.

    Args:
        connection: Open SQLite connection.
        table_name: Table to inspect.
        column_name: Column that must exist.
        column_sql: SQL fragment for `ALTER TABLE ... ADD COLUMN`.
    """
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    if column_name in {str(row["name"]) for row in rows}:
        return
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
