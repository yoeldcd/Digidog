# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Outbound gateway that queues avatar replies for the native Codex host."""

from __future__ import annotations

import sqlite3

from brain.presentation.avatar.communication.models import ReplyRequestDTO, ReplyResultDTO
from brain.presentation.avatar.communication.message_store import AvatarMessageStore


class NativeOutboxGateway:
    """Accept a reply only after durable local persistence succeeds."""

    def __init__(self, message_store: AvatarMessageStore) -> None:
        self._message_store = message_store

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        try:
            self._message_store.enqueue(request_dto)
        except (OSError, ValueError, sqlite3.Error) as exc:
            return ReplyResultDTO(False, request_dto.target.thread_id, request_dto.mode, str(exc))
        return ReplyResultDTO(True, request_dto.target.thread_id, request_dto.mode)
