"""Application ports for avatar-to-Codex reply delivery."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any, Protocol

# Application Modules Imports
from brain.presentation.avatar.communication.models import ReplyRequestDTO, ReplyResultDTO


class CodexReplyGatewayPort(Protocol):
    """Deliver normalized avatar replies to one Codex conversation."""

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Send one reply using the requested delivery strategy."""
        ...


class CodexAppServerTransportPort(Protocol):
    """Exchange JSON-RPC requests and notifications with Codex App Server."""

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send one request and return its result payload."""
        ...

    def notify(self, method: str, params: dict[str, Any]) -> None:
        """Send one notification without waiting for a response."""
        ...
