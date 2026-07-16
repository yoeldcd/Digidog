# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""SQLite connection factory for the knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
from pathlib import Path


def connect_database(db_path: Path) -> sqlite3.Connection:
    """
    Open a configured SQLite connection.

    Args:
        db_path (Path): SQLite database path.

    Returns:
        sqlite3.Connection: Configured connection with row access and foreign keys.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection: sqlite3.Connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection
