"""Application service for avatar reply submission."""

from __future__ import annotations

# Application Modules Imports
from brain.presentation.avatar.communication.models import ReplyRequestDTO, ReplyResultDTO
from brain.presentation.avatar.communication.ports import CodexReplyGatewayPort


class AvatarReplyService:
    """Coordinate reply delivery without depending on Qt or Codex transports."""

    def __init__(self, gateway: CodexReplyGatewayPort) -> None:
        """Initialize the service with one outbound Codex gateway."""
        self._gateway = gateway

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Delegate a validated reply to the configured outbound gateway."""
        return self._gateway.send(request_dto=request_dto)
