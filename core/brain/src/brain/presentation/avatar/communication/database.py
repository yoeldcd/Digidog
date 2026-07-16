# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Shared SQLite setup for avatar communication persistence."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def communication_database_path(workspace_root: Path | None = None) -> Path:
    """Return the canonical communication database for every process."""
    root = workspace_root or Path(os.environ.get("WORKSPACE_ROOT", "."))
    return root.resolve() / "$agent" / "database" / "avatar_communication.db"


def connect_communication_database(workspace_root: Path | None = None) -> sqlite3.Connection:
    """Open the communication database and apply its forward-only schema migrations."""
    database_path = communication_database_path(workspace_root)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS avatar_outbox(
            message_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            host_id TEXT NOT NULL,
            source_message_id TEXT NOT NULL DEFAULT '',
            text TEXT NOT NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending', 'delivered')),
            created_at REAL NOT NULL,
            delivered_at REAL
        )
        """
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(avatar_outbox)")}
    if "lease_owner" not in columns:
        connection.execute("ALTER TABLE avatar_outbox ADD COLUMN lease_owner TEXT")
    if "lease_until" not in columns:
        connection.execute("ALTER TABLE avatar_outbox ADD COLUMN lease_until REAL")
    if "consumed_at" not in columns:
        connection.execute("ALTER TABLE avatar_outbox ADD COLUMN consumed_at REAL")
    connection.commit()
    return connection
