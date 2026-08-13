"""Typed immutable results for daemon-owned voice instances.

Provides standardized data contracts and parsing helpers for representing
voice emission outcomes across boundaries. Exposes typed structures for
enqueue acknowledgements and terminal lifecycle states.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from typing import Final


INSTANCE_ID_FIELDS: Final[tuple[str, str]] = ("instanceId", "speakId")
"""Wire fields accepted for the daemon-created logical instance identity."""


@unique
class InstanceTerminalState(str, Enum):
    """Enumerate the terminal outcomes visible to a synchronous emitter.

    Defines the closed set of final lifecycle states that a voice emission
    can reach within the daemon runtime. Emitters block on these states until
    speaking completes, a user reply is submitted, or cancellation occurs.

    Members:
        CANCELED: The owning instance was canceled before speaking completed.
        SPEAKED: The owning instance completed speech successfully.
        RESPONSED: The owning instance completed with response text.
    """

    CANCELED = "CANCELED"
    SPEAKED = "SPEAKED"
    RESPONSED = "RESPONSED"


COMPOSER_RELEASED_STATE: Final[str] = "RELEASED"
"""Non-terminal result returned when a composer hold is released."""


@dataclass(frozen=True, slots=True)
class InstanceEnqueueResult:
    """Identify one accepted logical voice emission.

    Wraps the canonical instance identifier returned by the daemon upon
    accepting a speech request into the FIFO queue. Preserves the speak ID for
    correlation and provides validation for queued status.

    Attributes:
        instance_id: Canonical daemon-created identity returned by ``/speak``.
        queued: Whether the daemon accepted the logical emission.
    """

    instance_id: str
    queued: bool = True

    def __post_init__(self) -> None:
        """Reject an empty or non-canonical instance identity.

        Args:
            None.

        Returns:
            None.

        Raises:
            ValueError: If the identity is empty or has surrounding whitespace.
        """

        # Domain validation: identity format and whitespace verification
        if not isinstance(self.instance_id, str) or not self.instance_id.strip():
            raise ValueError("Instance ID is required.")

        # Format validation: ensure instance ID has no surrounding whitespace
        if self.instance_id != self.instance_id.strip():
            raise ValueError("Instance ID must not have surrounding whitespace.")

        # Flag validation: boolean queued status verification
        if not isinstance(self.queued, bool):
            raise ValueError("Queued status must be boolean.")

    @property
    def speak_id(self) -> str:
        """Return the same identity using the legacy voice vocabulary.

        Args:
            None.

        Returns:
            str: Canonical daemon-created speak identifier.
        """

        return self.instance_id


@dataclass(frozen=True, slots=True)
class InstanceTerminalResult:
    """Carry one immutable terminal result for its owning voice instance.

    Represents the final outcome of a voice message emission after it reaches a
    terminal lifecycle state. Stores the canonical instance identifier, final state,
    and optional user response text when the state is RESPONSED.

    Attributes:
        instance_id: Canonical daemon-created identity that was awaited.
        state: Explicit terminal outcome won by this instance.
        response: Exact response text when the state is ``RESPONSED``.
    """

    instance_id: str
    state: InstanceTerminalState
    response: str = ""

    def __post_init__(self) -> None:
        """Validate identity, closed state, and response ownership.

        Args:
            None.

        Returns:
            None.

        Raises:
            ValueError: If a public result contains invalid terminal data.
        """

        # Format validation: ensure instance ID has no surrounding whitespace
        if not isinstance(self.instance_id, str) or not self.instance_id.strip():
            raise ValueError("Instance ID is required.")

        # Format validation: ensure instance ID has no surrounding whitespace
        if self.instance_id != self.instance_id.strip():
            raise ValueError("Instance ID must not have surrounding whitespace.")

        # Conditional branch: verify domain preconditions and invariants
        if not isinstance(self.state, InstanceTerminalState):
            raise ValueError("Instance terminal state is invalid.")

        # Response validation: enforce response text rules for terminal state
        if not isinstance(self.response, str):
            raise ValueError("Instance response must be text.")

        # Response validation: enforce response text rules for terminal state
        if self.state is InstanceTerminalState.RESPONSED and not self.response.strip():
            raise ValueError("A responded instance requires response text.")

        # Response validation: enforce response text rules for terminal state
        if self.state is not InstanceTerminalState.RESPONSED and self.response:
            raise ValueError("Only a responded instance may contain response text.")

    @property
    def speak_id(self) -> str:
        """Return the same identity using the legacy voice vocabulary.

        Args:
            None.

        Returns:
            str: Canonical daemon-created speak identifier.
        """

        return self.instance_id

    def to_payload(self) -> dict[str, object]:
        """Serialize the terminal result without changing its response text.

        Args:
            None.

        Returns:
            dict[str, object]: JSON-compatible terminal payload.
        """

        # Serialization: build JSON-compatible dictionary payload
        payload: dict[str, object] = {
            "instanceId": self.instance_id,
            "state": self.state.value,
        }

        # Conditional branch: verify domain preconditions and invariants
        if self.state is InstanceTerminalState.RESPONSED:
            payload["response"] = self.response

        return payload


@dataclass(frozen=True, slots=True)
class ComposerCloseResult:
    """Describe one exact composer-close transition."""

    instance_id: str
    state: str
    terminal_result: InstanceTerminalResult | None = None

    def __post_init__(self) -> None:
        """Validate exact identity and close-state invariants."""

        if not isinstance(self.instance_id, str) or not self.instance_id.strip():
            raise ValueError("Instance ID is required.")
        if self.instance_id != self.instance_id.strip():
            raise ValueError("Instance ID must not have surrounding whitespace.")
        if self.state not in {
            COMPOSER_RELEASED_STATE,
            *(state.value for state in InstanceTerminalState),
        }:
            raise ValueError("Composer close state is invalid.")
        if self.terminal_result is not None:
            if self.terminal_result.instance_id != self.instance_id:
                raise ValueError("Composer close result belongs to a different instance.")
            if self.state != self.terminal_result.state.value:
                raise ValueError("Composer close state does not match its terminal result.")

    @property
    def speak_id(self) -> str:
        """Return the exact daemon identity using legacy vocabulary."""

        return self.instance_id

    @property
    def is_terminal(self) -> bool:
        """Return whether this close result describes a terminal state."""

        return self.state != COMPOSER_RELEASED_STATE

    def to_payload(self) -> dict[str, object]:
        """Serialize the close result for the daemon HTTP boundary."""

        payload: dict[str, object] = {
            "instanceId": self.instance_id,
            "speakId": self.instance_id,
            "state": self.state,
            "held": False,
        }
        if self.terminal_result is not None and self.terminal_result.state is InstanceTerminalState.RESPONSED:
            payload["response"] = self.terminal_result.response
        return payload


def instance_id_from_payload(payload: Mapping[str, object]) -> str:
    """Resolve one canonical identity from a daemon wire payload.

    Inspects payload mappings for standard instanceId or legacy speakId keys,
    validating that a non-empty string is present without whitespace corruption.
    Ensures consistent identity resolution across client-daemon transport routes.

    Args:
        payload: JSON object returned by the daemon.

    Returns:
        str: Canonical identity from ``instanceId`` or legacy ``speakId``.

    Raises:
        ValueError: If the identity is absent, malformed, or contradictory.
    """

    # Field resolution: extract canonical instance identity or legacy speakId
    identity_values = tuple(
        payload[field] for field in INSTANCE_ID_FIELDS if field in payload
    )

    # Conditional branch: verify domain preconditions and invariants
    if not identity_values:
        raise ValueError("Daemon response did not include an instance ID.")

    # Conditional branch: verify domain preconditions and invariants
    if any(
        not isinstance(value, str) or not value.strip() for value in identity_values
    ):
        raise ValueError("Daemon instance ID must be non-empty text.")

    # Conditional branch: verify domain preconditions and invariants
    if len(set(identity_values)) != 1:
        raise ValueError("Daemon returned contradictory instance IDs.")

    instance_id = identity_values[0]

    # Format validation: ensure instance ID has no surrounding whitespace
    if instance_id != instance_id.strip():
        raise ValueError("Daemon instance ID must not have surrounding whitespace.")

    return instance_id


def terminal_result_from_payload(
    payload: Mapping[str, object],
    expected_instance_id: str,
) -> InstanceTerminalResult:
    """Parse and bind one daemon terminal payload to its requested identity.

    Deserializes wire JSON payloads into typed InstanceTerminalResult DTOs.
    Verifies that the returned instance identifier matches the expected target ID
    and enforces terminal state enum invariants.

    Args:
        payload: JSON object returned by an instance wait or cancel route.
        expected_instance_id: Exact identity that the caller owns.

    Returns:
        InstanceTerminalResult: Typed terminal state bound to the requested ID.

    Raises:
        ValueError: If the state, identity, or response shape is invalid.
    """

    # Domain correlation: ensure response matches requested instance identity
    returned_instance_id = instance_id_from_payload(payload)

    # Format validation: ensure instance ID has no surrounding whitespace
    if returned_instance_id != expected_instance_id:
        raise ValueError("Daemon terminal result belongs to a different instance.")

    raw_state = payload.get("state")

    # Exception safety: execute block with error handling
    try:
        state = InstanceTerminalState(str(raw_state))

    # Failure recovery: handle execution failure or mapping error
    except ValueError as exc:
        raise ValueError(
            f"Unsupported instance terminal state: {raw_state!r}."
        ) from exc

    response = payload.get("response", "")

    # Response validation: enforce response text rules for terminal state
    if not isinstance(response, str):
        raise ValueError("Daemon instance response must be text.")

    return InstanceTerminalResult(
        instance_id=returned_instance_id,
        state=state,
        response=response,
    )


VoiceEnqueueResult = InstanceEnqueueResult
"""Readable alias for callers that use the voice-domain vocabulary."""

VoiceTerminalResult = InstanceTerminalResult
"""Readable alias for callers that use the voice-domain vocabulary."""

VoiceTerminalState = InstanceTerminalState
"""Readable alias for callers that use the voice-domain vocabulary."""


__all__ = [
    "COMPOSER_RELEASED_STATE",
    "ComposerCloseResult",
    "INSTANCE_ID_FIELDS",
    "InstanceEnqueueResult",
    "InstanceTerminalResult",
    "InstanceTerminalState",
    "VoiceEnqueueResult",
    "VoiceTerminalResult",
    "VoiceTerminalState",
    "instance_id_from_payload",
    "terminal_result_from_payload",
]
