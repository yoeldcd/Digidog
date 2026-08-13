# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application service for avatar reply submission.

Provides application orchestration for opening composer holds, submitting user replies,
and cancelling active speaking instances. Connects presentation components to underlying
daemon reply gateways with clean domain error handling.
"""

from __future__ import annotations

# Application Modules Imports
from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    ReplyRequestDTO,
    ReplyResultDTO,
)
from brain.presentation.avatar.communication.contracts.ports import CodexReplyGatewayPort


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

    def open(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Open a hold for the exact target captured by the composer.

        Args:
            target: Immutable daemon message target captured on open.

        Returns:
            ReplyResultDTO: Gateway hold acknowledgement or failure detail.
        """

        return self._gateway.open(target=target)

    def hold(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Preserve a hold-oriented alias for the composer open operation.

        Args:
            target: Immutable daemon message target captured on open.

        Returns:
            ReplyResultDTO: Gateway hold acknowledgement or failure detail.
        """

        return self.open(target=target)

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Delegate a validated reply to the configured outbound gateway.

        Args:
            request_dto (ReplyRequestDTO): Reply to deliver.

        Returns:
            ReplyResultDTO: Gateway delivery outcome.
        """

        return self._gateway.send(request_dto=request_dto)

    def cancel(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Delegate cancellation of one immutable daemon instance.

        Args:
            target (CodexThreadTargetDTO): Target captured when the dialog opened.

        Returns:
            ReplyResultDTO: Gateway cancellation outcome.
        """

        return self._gateway.cancel(target=target)

    def close(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Close the exact composer through the configured gateway.

        Delegates the composer close request to the underlying daemon gateway
        for the given conversation target.

        Args:
            target (CodexThreadTargetDTO): Target conversation identifier.

        Returns:
            ReplyResultDTO: Delivery result describing the close operation outcome.
        """

        return self._gateway.close(target=target)
