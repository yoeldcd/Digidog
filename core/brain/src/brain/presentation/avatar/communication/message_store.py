# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Producer and consumer access to avatar message bodies."""

from __future__ import annotations

import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from brain.presentation.avatar.communication.database import connect_communication_database
from brain.presentation.avatar.communication.models import DeliveryMode, ReplyRequestDTO
from brain.presentation.avatar.communication.payloads import ConsumerMessagePayload


@dataclass(frozen=True, slots=True)
class ConsumerMessage:
    """Message body resolved exclusively by the destination consumer.

    Attributes:
        message_id (str): Opaque message UUID.
        text (str): Reply content.
        mode (DeliveryMode): Requested delivery strategy.
        source_message_id (str): Avatar message that prompted the reply.
        created_at (float): Unix creation timestamp.
    """

    message_id: str
    text: str
    mode: DeliveryMode
    source_message_id: str
    created_at: float

    def as_mapping(self) -> ConsumerMessagePayload:
        """Serialize message data for native bridge delivery.

        Returns:
            ConsumerMessagePayload: Message fields with serialized delivery mode.
        """
        return {
            "message_id": self.message_id,
            "text": self.text,
            "mode": self.mode.value,
            "source_message_id": self.source_message_id,
            "created_at": self.created_at,
        }


class AvatarMessageStore:
    """Persist producer payloads and resolve them for authorized consumers.

    Attributes:
        _workspace_root (Path | None): Optional workspace database override.
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        """Initialize the store with an optional workspace database override.

        Args:
            workspace_root (Path | None): Workspace root containing the database.

        Returns:
            None: The store is ready for message persistence.
        """
        self._workspace_root = workspace_root

    def enqueue(self, request_dto: ReplyRequestDTO) -> str:
        """Store an idempotent message and return its opaque reference.

        Args:
            request_dto (ReplyRequestDTO): Validated reply to persist.

        Returns:
            str: Stable opaque message identifier.
        """
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
        """Resolve an opaque message reference without changing its state.

        Args:
            message_id (str): Opaque message UUID.

        Returns:
            ConsumerMessage | None: Resolved message, or ``None`` when absent.

        Raises:
            ValueError: If ``message_id`` is not a UUID.
        """
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
        """Record that destination consumer resolved and handled a message.

        Args:
            message_id (str): Opaque message UUID.

        Returns:
            bool: Whether an existing message was acknowledged.

        Raises:
            ValueError: If ``message_id`` is not a UUID.
        """
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
    """Validate and normalize one opaque avatar message identifier.

    Args:
        message_id (str): Candidate message UUID.

    Returns:
        str: Trimmed UUID string suitable for database access.

    Raises:
        ValueError: If message_id is not a valid UUID.
    """
    normalized_id = str(message_id).strip()
    try:
        UUID(normalized_id)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Avatar message id must be a valid UUID.") from exc
    return normalized_id
