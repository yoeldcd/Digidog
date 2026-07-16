# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Typed data contracts for replies sent from the avatar to Codex."""

from __future__ import annotations

# Standard Libraries Imports
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4


class DeliveryMode(StrEnum):
    """Supported delivery strategies for one avatar reply."""

    QUEUE = "queue"
    STEER = "steer"
    INTERRUPT = "interrupt"


@dataclass(frozen=True, slots=True)
class CodexThreadTargetDTO:
    """Stable destination metadata inherited from one spoken message."""

    thread_id: str
    host_id: str = "local"
    source_message_id: str = ""

    def __post_init__(self) -> None:
        """Validate the target identifier before it crosses an adapter boundary."""
        try:
            UUID(self.thread_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Codex thread id must be a valid UUID.") from exc
        if not self.host_id.strip():
            raise ValueError("Codex host id cannot be empty.")


@dataclass(frozen=True, slots=True)
class ReplyRequestDTO:
    """Normalized user reply ready for application delivery."""

    target: CodexThreadTargetDTO
    text: str
    mode: DeliveryMode
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        """Reject blank replies and malformed idempotency identifiers."""
        if not self.text.strip():
            raise ValueError("Reply text cannot be empty.")
        try:
            UUID(self.idempotency_key)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Idempotency key must be a valid UUID.") from exc


@dataclass(frozen=True, slots=True)
class ReplyResultDTO:
    """Transport-independent outcome returned to the avatar controller."""

    accepted: bool
    thread_id: str
    mode: DeliveryMode
    error: str = ""
