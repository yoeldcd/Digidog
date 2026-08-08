# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Codex App Server gateway for avatar reply delivery."""

from __future__ import annotations

# Standard Libraries Imports
import time
# Application Modules Imports
from brain.presentation.avatar.communication.app_server_transport import CodexAppServerError
from brain.presentation.avatar.communication.models import DeliveryMode, ReplyRequestDTO, ReplyResultDTO
from brain.presentation.avatar.communication.ports import CodexAppServerTransportPort


class CodexAppServerGateway:
    """Translate avatar reply intents into Codex thread and turn operations.

    Attributes:
        _transport (CodexAppServerTransportPort): Transport used for App Server calls.
        _queue_timeout_seconds (float): Maximum time spent retrying queued turns.
        _retry_interval_seconds (float): Delay between retries while a turn is active.
    """

    def __init__(
        self,
        transport: CodexAppServerTransportPort,
        queue_timeout_seconds: float = 120.0,
        retry_interval_seconds: float = 0.5,
    ) -> None:
        """Configure transport and bounded queue retry behavior.

        Args:
            transport (CodexAppServerTransportPort): App Server transport port.
            queue_timeout_seconds (float): Maximum queue retry duration.
            retry_interval_seconds (float): Delay between active-turn retries.

        Returns:
            None: The gateway is ready to deliver reply requests.
        """
        self._transport = transport
        self._queue_timeout_seconds = max(0.0, queue_timeout_seconds)
        self._retry_interval_seconds = max(0.01, retry_interval_seconds)

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Deliver a reply using queue, steer, or interrupt semantics.

        Args:
            request_dto (ReplyRequestDTO): Validated avatar reply request.

        Returns:
            ReplyResultDTO: Accepted or rejected delivery outcome.
        """
        try:
            expected_turn_id = self._resume_thread(thread_id=request_dto.target.thread_id)

            if request_dto.mode is DeliveryMode.STEER:
                if expected_turn_id:
                    self._steer(request_dto=request_dto, expected_turn_id=expected_turn_id)
                else:
                    self._start(request_dto=request_dto)
            elif request_dto.mode is DeliveryMode.INTERRUPT:
                self._transport.request(
                    method="turn/interrupt",
                    params={"threadId": request_dto.target.thread_id},
                )
                self._start(request_dto=request_dto)
            else:
                self._enqueue(request_dto=request_dto)

        except (CodexAppServerError, OSError, ValueError) as exc:
            return ReplyResultDTO(
                accepted=False,
                thread_id=request_dto.target.thread_id,
                mode=request_dto.mode,
                error=str(exc),
            )

        return ReplyResultDTO(
            accepted=True,
            thread_id=request_dto.target.thread_id,
            mode=request_dto.mode,
        )

    def _resume_thread(self, thread_id: str) -> str:
        """Load the target conversation and return its active turn precondition.

        Args:
            thread_id (str): Target Codex conversation identifier.

        Returns:
            str: Active turn identifier, or an empty string when idle.
        """
        response = self._transport.request(method="thread/resume", params={"threadId": thread_id})
        thread = response.get("thread", {})
        turns = thread.get("turns", []) if isinstance(thread, dict) else []

        for turn in reversed(turns if isinstance(turns, list) else []):
            if isinstance(turn, dict) and turn.get("status") == "inProgress":
                return str(turn.get("id", ""))

        return ""

    def _enqueue(self, request_dto: ReplyRequestDTO) -> None:
        """Retry a new turn until the active turn completes or timeout expires.

        Args:
            request_dto (ReplyRequestDTO): Validated reply request.

        Returns:
            None: Delivery succeeds or the transport raises the final error.
        """
        deadline = time.monotonic() + self._queue_timeout_seconds
        while True:
            try:
                self._start(request_dto=request_dto)
                return
            except CodexAppServerError as exc:
                if time.monotonic() >= deadline or not self._is_active_turn_error(exc):
                    raise
                time.sleep(self._retry_interval_seconds)

    def _start(self, request_dto: ReplyRequestDTO) -> None:
        """Start one new user turn in the target conversation.

        Args:
            request_dto (ReplyRequestDTO): Validated reply request.

        Returns:
            None: The transport result is intentionally consumed as a side effect.
        """
        params = {
            "threadId": request_dto.target.thread_id,
            "input": [{"type": "text", "text": request_dto.text}],
        }
        self._transport.request(method="turn/start", params=params)

    def _steer(self, request_dto: ReplyRequestDTO, expected_turn_id: str) -> None:
        """Append user input to the currently active turn.

        Args:
            request_dto (ReplyRequestDTO): Validated reply request.
            expected_turn_id (str): Active turn precondition from the resume call.

        Returns:
            None: The transport result is intentionally consumed as a side effect.
        """
        params = {
            "threadId": request_dto.target.thread_id,
            "expectedTurnId": expected_turn_id,
            "input": [{"type": "text", "text": request_dto.text}],
        }
        self._transport.request(method="turn/steer", params=params)

    @staticmethod
    def _is_active_turn_error(exc: CodexAppServerError) -> bool:
        """Recognize version-tolerant active-turn rejection messages.

        Args:
            exc (CodexAppServerError): Transport rejection to classify.

        Returns:
            bool: Whether the rejection indicates an active turn.
        """
        message = str(exc).casefold()
        return "active turn" in message or "turn already" in message or "in progress" in message
