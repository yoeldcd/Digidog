# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""SQLite connection helpers for source registries."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Application Modules Imports
from brain.infrastructure.sources.registry.schema import initialize_registry_schema


@contextmanager
def registry_session(registry_path: Path) -> Iterator[sqlite3.Connection]:
    """
    Open and always close a source registry connection.

    Args:
        registry_path: Source registry SQLite path.

    Yields:
        Configured registry connection.
    """
    connection: sqlite3.Connection = connect_registry(registry_path=registry_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def connect_registry(registry_path: Path) -> sqlite3.Connection:
    """
    Open a source registry SQLite connection.

    Args:
        registry_path: Source registry SQLite path.

    Returns:
        Configured connection.
    """
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(registry_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    initialize_registry_schema(connection=connection)
    return connection
