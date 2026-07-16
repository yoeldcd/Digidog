# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Payload-blind signal queue used by the native Codex bridge."""

from __future__ import annotations

import time
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

from brain.presentation.avatar.communication.database import (
    communication_database_path,
    connect_communication_database,
)


@dataclass(frozen=True, slots=True)
class BridgeSignal:
    """Opaque routing signal with no message body or semantic metadata."""

    message_id: str
    thread_id: str
    host_id: str
    created_at: float

    def as_mapping(self) -> dict[str, object]:
        return asdict(self)


class AvatarOutboxRepository:
    """Lease and acknowledge opaque references without access to message bodies."""

    def __init__(self, workspace_root: Path | None = None) -> None:
        self._workspace_root = workspace_root
        self.database_path = communication_database_path(workspace_root)

    def pending(self, limit: int = 20) -> list[BridgeSignal]:
        """Return payload-blind pending signals, including leased rows."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT message_id, thread_id, host_id, created_at
                FROM avatar_outbox WHERE status = 'pending'
                ORDER BY created_at, message_id LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
        return self._messages(rows)

    def claim(self, limit: int = 20, lease_seconds: int = 600) -> tuple[str, list[BridgeSignal]]:
        """Atomically lease references without selecting their message bodies."""
        claim_token = uuid.uuid4().hex
        now = time.time()
        expires_at = now + max(60, min(lease_seconds, 3600))
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT message_id, thread_id, host_id, created_at
                FROM avatar_outbox
                WHERE status = 'pending' AND (lease_until IS NULL OR lease_until <= ?)
                ORDER BY created_at, message_id LIMIT ?
                """,
                (now, max(1, min(limit, 100))),
            ).fetchall()
            connection.executemany(
                """
                UPDATE avatar_outbox SET lease_owner = ?, lease_until = ?
                WHERE message_id = ? AND status = 'pending'
                  AND (lease_until IS NULL OR lease_until <= ?)
                """,
                [(claim_token, expires_at, row[0], now) for row in rows],
            )
            connection.commit()
        return claim_token, self._messages(rows)

    def acknowledge(self, message_id: str, claim_token: str) -> bool:
        """Mark a message delivered only for the worker that owns its lease."""
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE avatar_outbox
                SET status = 'delivered', delivered_at = ?, lease_owner = NULL, lease_until = NULL
                WHERE message_id = ? AND status = 'pending' AND lease_owner = ?
                """,
                (time.time(), message_id, claim_token),
            )
            connection.commit()
        return cursor.rowcount == 1

    def release(self, message_id: str, claim_token: str) -> bool:
        """Release a lease when policy postpones delivery without losing the row."""
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE avatar_outbox SET lease_owner = NULL, lease_until = NULL
                WHERE message_id = ? AND status = 'pending' AND lease_owner = ?
                """,
                (message_id, claim_token),
            )
            connection.commit()
        return cursor.rowcount == 1

    def _connect(self):
        return connect_communication_database(self._workspace_root)

    @staticmethod
    def _messages(rows: list[tuple[object, ...]]) -> list[BridgeSignal]:
        return [
            BridgeSignal(
                message_id=str(row[0]),
                thread_id=str(row[1]),
                host_id=str(row[2]),
                created_at=float(row[3]),
            )
            for row in rows
        ]
