# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Outbound gateway that queues avatar replies for the native Codex host."""

from __future__ import annotations

import sqlite3

from brain.presentation.avatar.communication.contracts.models import ReplyRequestDTO, ReplyResultDTO
from brain.presentation.avatar.communication.outbox.message_store import AvatarMessageStore


class NativeOutboxGateway:
    """Accept a reply only after durable local persistence succeeds.

    Attributes:
        _message_store (AvatarMessageStore): Durable store used for native delivery.
    """

    def __init__(self, message_store: AvatarMessageStore) -> None:
        """Initialize the gateway with one durable message store.

        Args:
            message_store (AvatarMessageStore): Store used for native delivery.

        Returns:
            None: The gateway is ready to persist reply requests.
        """
        self._message_store = message_store

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Persist a reply and report whether native delivery can proceed.

        Args:
            request_dto (ReplyRequestDTO): Validated avatar reply request.

        Returns:
            ReplyResultDTO: Accepted persistence result or error detail.
        """

        # Exception safety: execute operation within protected error boundary
        try:
            self._message_store.enqueue(request_dto)

        # Validation handling: handle invalid input domain error
        except (OSError, ValueError, sqlite3.Error) as exc:
            return ReplyResultDTO(False, request_dto.target.thread_id, request_dto.mode, str(exc))
        return ReplyResultDTO(True, request_dto.target.thread_id, request_dto.mode)
