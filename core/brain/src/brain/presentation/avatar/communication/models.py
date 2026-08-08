# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Typed data contracts for replies sent from the avatar to Codex."""

from __future__ import annotations

# Standard Libraries Imports
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4


class DeliveryMode(StrEnum):
    """Supported delivery strategies for one avatar reply.

    Attributes:
        QUEUE (str): Wait for the active turn before delivering.
        STEER (str): Append input to the active turn when possible.
        INTERRUPT (str): Interrupt the active turn before delivering.
    """

    QUEUE = "queue"
    STEER = "steer"
    INTERRUPT = "interrupt"


@dataclass(frozen=True, slots=True)
class CodexThreadTargetDTO:
    """Stable destination metadata inherited from one spoken message.

    Attributes:
        thread_id (str): UUID identifying the Codex conversation.
        host_id (str): Host identity that owns the conversation.
        source_message_id (str): Source avatar-message identifier.
    """

    thread_id: str
    host_id: str = "local"
    source_message_id: str = ""

    def __post_init__(self) -> None:
        """Validate the target identifier before it crosses an adapter boundary.

        Returns:
            None: Validation completes before construction returns.
        """
        try:
            UUID(self.thread_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Codex thread id must be a valid UUID.") from exc
        if not self.host_id.strip():
            raise ValueError("Codex host id cannot be empty.")


@dataclass(frozen=True, slots=True)
class ReplyRequestDTO:
    """Normalized user reply ready for application delivery.

    Attributes:
        target (CodexThreadTargetDTO): Conversation destination.
        text (str): Non-empty reply content.
        mode (DeliveryMode): Requested delivery strategy.
        idempotency_key (str): UUID used to deduplicate retries.
    """

    target: CodexThreadTargetDTO
    text: str
    mode: DeliveryMode
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        """Reject blank replies and malformed idempotency identifiers.

        Returns:
            None: Validation completes before construction returns.
        """
        if not self.text.strip():
            raise ValueError("Reply text cannot be empty.")
        try:
            UUID(self.idempotency_key)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Idempotency key must be a valid UUID.") from exc


@dataclass(frozen=True, slots=True)
class ReplyResultDTO:
    """Transport-independent outcome returned to the avatar controller.

    Attributes:
        accepted (bool): Whether Codex accepted the reply.
        thread_id (str): Target conversation identifier.
        mode (DeliveryMode): Applied delivery strategy.
        error (str): Transport failure detail when rejected.
    """

    accepted: bool
    thread_id: str
    mode: DeliveryMode
    error: str = ""
