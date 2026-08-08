# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application ports for avatar-to-Codex reply delivery."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Protocol

from brain.presentation.avatar.communication.payloads import AppServerResultPayload
# Application Modules Imports
from brain.presentation.avatar.communication.models import ReplyRequestDTO, ReplyResultDTO


class CodexReplyGatewayPort(Protocol):
    """Deliver normalized avatar replies to one Codex conversation."""

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Send one reply using the requested delivery strategy.

        Args:
            request_dto (ReplyRequestDTO): Validated reply request.

        Returns:
            ReplyResultDTO: Transport-independent delivery outcome.
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
