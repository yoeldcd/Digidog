# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Full-text search table setup for the knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3


def create_fts_tables(connection: sqlite3.Connection) -> None:
    """
    Create full-text search tables.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    connection.executescript(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS entity_fts
        USING fts5(entity_id UNINDEXED, canonical_name, description, entity_class);

        CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts
        USING fts5(evidence_id UNINDEXED, quote, location);
        """
    )
