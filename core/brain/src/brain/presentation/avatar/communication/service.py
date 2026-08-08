# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application service for avatar reply submission."""

from __future__ import annotations

# Application Modules Imports
from brain.presentation.avatar.communication.models import ReplyRequestDTO, ReplyResultDTO
from brain.presentation.avatar.communication.ports import CodexReplyGatewayPort


class AvatarReplyService:
    """Coordinate reply delivery without depending on Qt or Codex transports.

    Attributes:
        _gateway (CodexReplyGatewayPort): Outbound port that accepts validated replies.
    """

    def __init__(self, gateway: CodexReplyGatewayPort) -> None:
        """Initialize the service with one outbound Codex gateway.

        Args:
            gateway (CodexReplyGatewayPort): Outbound delivery port.

        Returns:
            None: The service is ready to delegate replies.
        """
        self._gateway = gateway

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Delegate a validated reply to the configured outbound gateway.

        Args:
            request_dto (ReplyRequestDTO): Reply to deliver.

        Returns:
            ReplyResultDTO: Gateway delivery outcome.
        """
        return self._gateway.send(request_dto=request_dto)
