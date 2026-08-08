# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Non-blocking Qt controller for replies sent from the avatar."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from brain.presentation.avatar.communication.models import CodexThreadTargetDTO, DeliveryMode, ReplyRequestDTO
from brain.presentation.avatar.communication.service import AvatarReplyService


class AvatarReplyController(QObject):
    """Run outbound delivery away from the Qt event loop.

    Attributes:
        deliveryFinished (Signal): Qt signal carrying one ReplyResultDTO.
        _service (AvatarReplyService): Application service for delivery.
    """

    deliveryFinished = Signal(object)

    def __init__(self, service: AvatarReplyService) -> None:
        """Initialize the controller with one reply delivery service.

        Args:
            service (AvatarReplyService): Application service to invoke off-thread.

        Returns:
            None: The Qt controller is ready for submissions.
        """
        super().__init__()
        self._service = service

    def submit(self, target: CodexThreadTargetDTO, text: str, mode: DeliveryMode) -> None:
        """Validate synchronously and deliver asynchronously.

        Args:
            target (CodexThreadTargetDTO): Destination Codex conversation.
            text (str): Reply content.
            mode (DeliveryMode): Requested delivery strategy.

        Raises:
            ValueError: If reply content or destination identifiers are invalid.
        Returns:
            None: The validated request is scheduled on a daemon thread.
        """
        request_dto = ReplyRequestDTO(target=target, text=text, mode=mode)

        def worker() -> None:
            """Deliver one validated reply off the Qt event loop.

            Returns:
                None: The result is emitted through deliveryFinished.
            """
            self.deliveryFinished.emit(self._service.send(request_dto=request_dto))

        threading.Thread(target=worker, daemon=True, name="avatar-codex-reply").start()
