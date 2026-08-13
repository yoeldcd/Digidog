# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Non-blocking Qt controller for replies sent from the avatar.

Coordinates user input from Qt presentation widgets with background reply gateways.
Ensures UI responsiveness by dispatching daemon hold, submit, and cancellation
requests asynchronously on separate background worker threads.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QObject, Signal

from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    DeliveryMode,
    ReplyRequestDTO,
    ReplyResultDTO,
)
from brain.presentation.avatar.communication.reply.service import AvatarReplyService


class AvatarReplyController(QObject):
    """Run outbound delivery away from the Qt event loop.

    Attributes:
        deliveryFinished (Signal): Qt signal carrying one ReplyResultDTO.
        _service (AvatarReplyService): Application service for delivery.
    """

    deliveryFinished = Signal(object)
    composerOpened = Signal(object)

    def __init__(self, service: AvatarReplyService) -> None:
        """Initialize the controller with one reply delivery service.

        Args:
            service (AvatarReplyService): Application service to invoke off-thread.

        Returns:
            None: The Qt controller is ready for submissions.
        """
        super().__init__()
        self._service = service

    def open(self, target: CodexThreadTargetDTO) -> None:
        """Open the exact daemon hold without blocking the Qt event loop.

        Args:
            target: Immutable message target captured by the composer.

        Returns:
            None: The hold result is emitted through the controller signals.
        """

        self._start_worker(
            operation=partial(self._service.open, target=target),
            target=target,
            mode=DeliveryMode.STEER,
            thread_name="avatar-codex-reply-open",
            completion=self.composerOpened.emit,
            emit_delivery=False,
        )

    def hold(self, target: CodexThreadTargetDTO) -> None:
        """Preserve a hold-oriented alias for opening the exact target.

        Args:
            target: Immutable message target captured by the composer.

        Returns:
            None: The hold request is scheduled asynchronously.
        """

        self.open(target=target)

    def submit(
        self, target: CodexThreadTargetDTO, text: str, mode: DeliveryMode
    ) -> None:
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
        self._start_worker(
            operation=partial(self._service.send, request_dto=request_dto),
            target=target,
            mode=mode,
            thread_name="avatar-codex-reply",
        )

    def cancel(self, target: CodexThreadTargetDTO) -> None:
        """Cancel the exact target asynchronously without blocking Qt.

        Args:
            target (CodexThreadTargetDTO): Target captured when the dialog opened.

        Returns:
            None: Cancellation is scheduled on a daemon thread.
        """
        self._start_worker(
            operation=partial(self._service.cancel, target=target),
            target=target,
            mode=DeliveryMode.STEER,
            thread_name="avatar-codex-reply-cancel",
        )

    def close(self, target: CodexThreadTargetDTO) -> None:
        """Close the exact composer without blocking the Qt event loop.

        Schedules an asynchronous close operation on a background worker thread
        for the specified conversation target.

        Args:
            target (CodexThreadTargetDTO): Target conversation identifier.

        Returns:
            None: The close operation is dispatched asynchronously.
        """

        self._start_worker(
            operation=partial(self._service.close, target=target),
            target=target,
            mode=DeliveryMode.STEER,
            thread_name="avatar-codex-reply-close",
        )

    def _start_worker(
        self,
        operation: Callable[[], ReplyResultDTO],
        target: CodexThreadTargetDTO,
        mode: DeliveryMode,
        thread_name: str,
        completion: Callable[[ReplyResultDTO], None] | None = None,
        emit_delivery: bool = True,
    ) -> None:
        """Run one gateway operation away from the Qt event loop.

        Args:
            operation (Callable[[], ReplyResultDTO]): Gateway operation to run.
            target (CodexThreadTargetDTO): Target used for deterministic failures.
            mode (DeliveryMode): Mode retained in the result on unexpected errors.
            thread_name (str): Diagnostic worker thread name.
            completion: Optional secondary signal callback for the operation.
            emit_delivery: Whether to emit the general delivery signal.

        Returns:
            None: The outcome is emitted through ``deliveryFinished``.
        """

        def worker() -> None:
            """Deliver one validated operation off the Qt event loop.

            Args:
                No external arguments are accepted; the closure captures the validated operation and target.

            Returns:
                None: The result is emitted through ``deliveryFinished``.
            """

            # Exception safety: execute operation within error boundary
            try:
                result = operation()

            # Failure recovery: handle execution or transport exception
            except Exception as exc:  # noqa: BLE001 - preserve UI input on gateway faults.
                result = ReplyResultDTO(
                    accepted=False,
                    thread_id=target.thread_id,
                    mode=mode,
                    error=str(exc),
                    instance_id=target.instance_id,
                )

            # Conditional check: evaluate domain preconditions and invariants
            if emit_delivery:
                self.deliveryFinished.emit(result)

            # Conditional check: evaluate domain preconditions and invariants
            if completion is not None:
                completion(result)

        threading.Thread(target=worker, daemon=True, name=thread_name).start()
