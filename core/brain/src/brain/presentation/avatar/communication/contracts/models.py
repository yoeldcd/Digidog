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


class ReplyTerminalState(StrEnum):
    """Terminal states returned by the daemon instance reply routes.

    Attributes:
        CANCELED (str): The captured daemon instance was canceled.
        SPEAKED (str): The captured daemon instance completed without a reply.
        RESPONSED (str): The captured daemon instance received a response.
    """

    CANCELED = "CANCELED"
    SPEAKED = "SPEAKED"
    RESPONSED = "RESPONSED"
    RELEASED = "RELEASED"


@dataclass(frozen=True, slots=True)
class CodexThreadTargetDTO:
    """Immutable message-instance identity with optional legacy metadata.

    Attributes:
        instance_id (str): Canonical daemon speak instance used for routing.
        thread_id (str): Optional Codex conversation metadata.
        host_id (str): Optional host metadata retained for compatibility.
        source_message_id (str): Optional source-message provenance metadata.
        session_id (str): Optional Codex session metadata.
    """

    instance_id: str
    thread_id: str = ""
    host_id: str = ""
    source_message_id: str = ""
    session_id: str = ""

    def __post_init__(self) -> None:
        """Validate the target identifier before it crosses an adapter boundary.

        Args:
            No external arguments are accepted; dataclass fields are read from the instance.

        Returns:
            None: Validation completes before construction returns.

        Raises:
            ValueError: If the message instance identity is missing or invalid.
        """

        # Target validation: check non-empty instance identity and whitespace
        if not isinstance(self.instance_id, str) or not self.instance_id.strip():
            raise ValueError("Message instance id is required.")

        # Identity check: verify instance ID invariants
        if self.instance_id != self.instance_id.strip():
            raise ValueError("Message instance id must not have surrounding whitespace.")

    @property
    def speak_id(self) -> str:
        """Return the daemon speak identifier using the daemon vocabulary.

        Args:
            No external arguments are accepted; the target supplies the instance.

        Returns:
            str: Exact immutable daemon instance identifier.
        """

        return self.instance_id


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

        Args:
            No external arguments are accepted; dataclass fields are read from the instance.

        Returns:
            None: Validation completes before construction returns.

        Raises:
            ValueError: If text is blank or the idempotency key is malformed.
        """

        # Content validation: check non-empty reply text
        if not self.text.strip():
            raise ValueError("Reply text cannot be empty.")

        # Idempotency validation: check valid UUID format
        try:
            UUID(self.idempotency_key)

        # Validation error handling: convert invalid input to domain exception
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Idempotency key must be a valid UUID.") from exc

    @property
    def instance_id(self) -> str:
        """Return the exact daemon instance bound to this reply.

        Args:
            No external arguments are accepted; the request supplies the target.

        Returns:
            str: Immutable instance identifier inherited from the target.
        """

        return self.target.instance_id


@dataclass(frozen=True, slots=True)
class ReplyResultDTO:
    """Transport-independent outcome returned to the avatar controller.

    Attributes:
        accepted (bool): Whether Codex accepted the reply.
        thread_id (str): Optional conversation metadata retained for display.
        mode (DeliveryMode): Applied delivery strategy.
        error (str): Transport failure detail when rejected.
        instance_id (str): Exact daemon instance addressed by the operation.
        state (str): Daemon terminal state returned by the operation.
        response (str): Response text echoed by a responded instance.
    """

    accepted: bool
    thread_id: str = ""
    mode: DeliveryMode = DeliveryMode.STEER
    error: str = ""
    instance_id: str = ""
    state: str = ""
    response: str = ""

    @property
    def terminal_state(self) -> str:
        """Return the daemon terminal state for callers using explicit wording.

        Args:
            No external arguments are accepted; the result supplies the state.

        Returns:
            str: ``CANCELED``, ``SPEAKED``, ``RESPONSED``, or an empty state.
        """

        return self.state

    @property
    def speak_id(self) -> str:
        """Return the exact daemon speak identifier from this result.

        Args:
            No external arguments are accepted; the result supplies the instance.

        Returns:
            str: Instance identifier, or an empty string for legacy gateways.
        """

        return self.instance_id
