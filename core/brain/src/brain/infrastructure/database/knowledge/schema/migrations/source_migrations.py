# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Source table migrations for knowledge schema upgrades."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3


def migrate_sources_identity_contract(connection: sqlite3.Connection) -> None:
    """
    Remove retired source update columns from existing SQLite databases.

    Source mtimes and processed state are JSON-owned contracts. SQLite keeps
    only the stable source identity needed to anchor graph objects.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    columns = connection.execute("PRAGMA table_info(sources)").fetchall()
    existing_names: set[str] = {str(row["name"]) for row in columns}
    retired_columns: set[str] = {"content_hash", "modified_at", "indexed_at"}
    if not retired_columns.intersection(existing_names):
        return

    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.executescript(
        """
        CREATE TABLE sources_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1
        );

        INSERT OR IGNORE INTO sources_new(id, source_type, path, title, active)
        SELECT
            id,
            source_type,
            path,
            COALESCE(title, ''),
            COALESCE(active, 1)
        FROM sources;

        DROP TABLE sources;
        ALTER TABLE sources_new RENAME TO sources;
        """
    )
    connection.commit()
    connection.execute("PRAGMA foreign_keys = ON")
