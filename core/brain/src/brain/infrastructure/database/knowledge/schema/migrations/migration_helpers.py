# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Shared SQLite migration helpers for knowledge schema upgrades."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    """
    Return whether a SQLite table exists.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
        table_name (str): Table name.

    Returns:
        bool: True when the table exists.
    """
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table') AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    """
    Add a column when it is missing from an existing SQLite table.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
        table_name (str): Existing table name.
        column_name (str): Expected column name.
        column_sql (str): SQLite column definition without `ADD COLUMN`.
    """
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_names: set[str] = {str(row["name"]) for row in columns}
    if column_name in existing_names:
        return
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
