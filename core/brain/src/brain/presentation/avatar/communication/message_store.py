"""Producer and consumer access to avatar message bodies."""

from __future__ import annotations

import time
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

from brain.presentation.avatar.communication.database import connect_communication_database
from brain.presentation.avatar.communication.models import DeliveryMode, ReplyRequestDTO


@dataclass(frozen=True, slots=True)
class ConsumerMessage:
    """A message body resolved exclusively by the destination consumer."""

    message_id: str
    text: str
    mode: DeliveryMode
    source_message_id: str
    created_at: float

    def as_mapping(self) -> dict[str, object]:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        return payload


class AvatarMessageStore:
    """Persist producer payloads and resolve them for authorized consumers."""

    def __init__(self, workspace_root: Path | None = None) -> None:
        self._workspace_root = workspace_root

    def enqueue(self, request_dto: ReplyRequestDTO) -> str:
        """Store one idempotent message and return only its opaque reference."""
        with closing(connect_communication_database(self._workspace_root)) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO avatar_outbox(
                    message_id, thread_id, host_id, source_message_id, text, mode, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    request_dto.idempotency_key,
                    request_dto.target.thread_id,
                    request_dto.target.host_id,
                    request_dto.target.source_message_id,
                    request_dto.text.strip(),
                    request_dto.mode.value,
                    time.time(),
                ),
            )
            connection.commit()
        return request_dto.idempotency_key

    def read(self, message_id: str) -> ConsumerMessage | None:
        """Resolve one opaque message reference without changing its state."""
        normalized_id = _validated_message_id(message_id)
        with closing(connect_communication_database(self._workspace_root)) as connection:
            row = connection.execute(
                """
                SELECT message_id, text, mode, source_message_id, created_at
                FROM avatar_outbox WHERE message_id = ?
                """,
                (normalized_id,),
            ).fetchone()
        if row is None:
            return None
        return ConsumerMessage(
            message_id=str(row[0]),
            text=str(row[1]),
            mode=DeliveryMode(str(row[2])),
            source_message_id=str(row[3]),
            created_at=float(row[4]),
        )

    def acknowledge_consumed(self, message_id: str) -> bool:
        """Record that the destination consumer resolved and handled a message."""
        normalized_id = _validated_message_id(message_id)
        with closing(connect_communication_database(self._workspace_root)) as connection:
            cursor = connection.execute(
                """
                UPDATE avatar_outbox SET consumed_at = COALESCE(consumed_at, ?)
                WHERE message_id = ?
                """,
                (time.time(), normalized_id),
            )
            connection.commit()
        return cursor.rowcount == 1


def _validated_message_id(message_id: str) -> str:
    normalized_id = str(message_id).strip()
    try:
        UUID(normalized_id)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Avatar message id must be a valid UUID.") from exc
    return normalized_id
