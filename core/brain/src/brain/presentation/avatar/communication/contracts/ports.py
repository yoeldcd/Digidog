# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application ports for avatar-to-Codex reply delivery."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Protocol

from brain.presentation.avatar.communication.contracts.payloads import AppServerResultPayload

# Application Modules Imports
from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    ReplyRequestDTO,
    ReplyResultDTO,
)


class CodexReplyGatewayPort(Protocol):
    """Deliver normalized avatar replies to one Codex conversation."""

    def open(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Open a hold for one exact daemon instance.

        Args:
            target: Immutable message target captured by the composer.

        Returns:
            ReplyResultDTO: Hold acknowledgement or failure detail.
        """
        ...

    def hold(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Alias for opening a hold on one exact daemon instance.

        Args:
            target: Immutable message target captured by the composer.

        Returns:
            ReplyResultDTO: Hold acknowledgement or failure detail.
        """
        ...

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Send one reply using the requested delivery strategy.

        Args:
            request_dto (ReplyRequestDTO): Validated reply request.

        Returns:
            ReplyResultDTO: Transport-independent delivery outcome.
        """
        ...

    def cancel(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Cancel the exact daemon instance bound to one target.

        Args:
            target (CodexThreadTargetDTO): Immutable instance-bound target.

        Returns:
            ReplyResultDTO: Transport-independent cancellation outcome.
        """
        ...

    def close(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Close the exact composer, releasing it while speaking when possible.

        Sends a close request for the specified conversation target, releasing
        any active composer hold and closing the UI window.

        Args:
            target (CodexThreadTargetDTO): Target conversation identifier.

        Returns:
            ReplyResultDTO: Delivery result describing the close operation outcome.
        """
        ...


class CodexAppServerTransportPort(Protocol):
    """Exchange JSON-RPC requests and notifications with Codex App Server."""

    def request(self, method: str, params: dict[str, object]) -> AppServerResultPayload:
        """Send a request and return its named result payload.

        Args:
            method (str): JSON-RPC method name.
            params (dict[str, object]): JSON-RPC parameter object.

        Returns:
            AppServerResultPayload: Stable result contract for the operation.
        """
        ...

    def notify(self, method: str, params: dict[str, object]) -> None:
        """Send a notification without waiting for a response.

        Args:
            method (str): JSON-RPC method name.
            params (dict[str, object]): JSON-RPC parameter object.

        Returns:
            None: Notifications do not wait for a response.
        """
        ...
