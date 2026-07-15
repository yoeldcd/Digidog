"""Non-blocking Qt controller for replies sent from the avatar."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from brain.presentation.avatar.communication.models import CodexThreadTargetDTO, DeliveryMode, ReplyRequestDTO
from brain.presentation.avatar.communication.service import AvatarReplyService


class AvatarReplyController(QObject):
    """Run outbound delivery away from the Qt event loop."""

    deliveryFinished = Signal(object)

    def __init__(self, service: AvatarReplyService) -> None:
        super().__init__()
        self._service = service

    def submit(self, target: CodexThreadTargetDTO, text: str, mode: DeliveryMode) -> None:
        """Validate synchronously and deliver asynchronously."""
        request_dto = ReplyRequestDTO(target=target, text=text, mode=mode)

        def worker() -> None:
            self.deliveryFinished.emit(self._service.send(request_dto=request_dto))

        threading.Thread(target=worker, daemon=True, name="avatar-codex-reply").start()
