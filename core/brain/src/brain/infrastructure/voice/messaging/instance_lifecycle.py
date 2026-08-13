"""Coordinate bounded, synchronous lifecycle results for speak instances.

Provides atomic tracking and synchronization for daemon-created voice instances.
Allows synchronous CLI processes to wait for per-instance terminal states
without blocking or disturbing FIFO queue order or Qt event loops.
"""

from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass
from typing import Final

from brain.infrastructure.voice.contracts.instance_results import (
    InstanceEnqueueResult,
    InstanceTerminalResult,
    InstanceTerminalState,
)


DEFAULT_INSTANCE_RETENTION: Final[int] = 256
"""Maximum number of completed instances retained for later observation."""

MAX_INSTANCE_WAIT_SECONDS: Final[float] = 30.0
"""Maximum duration accepted by one instance wait operation."""


@dataclass(slots=True)
class _InstanceEntry:
    """Hold one instance event and its first terminal result.

    Attributes:
        event: Event released when the instance becomes terminal.
        terminal: Immutable result, or ``None`` while the instance is live.
    """

    event: threading.Event
    terminal: InstanceTerminalResult | None = None


class InstanceLifecycleRegistry:
    """Own atomic per-instance terminalization without advancing the FIFO.

    A waiter captures the private entry before waiting.  Retention may remove
    that entry from the lookup map after completion, but the captured entry
    remains valid and lets an already-running waiter observe its result.
    """

    def __init__(self, retention: int = DEFAULT_INSTANCE_RETENTION) -> None:
        """Initialize an empty registry with bounded terminal retention.

        Args:
            retention: Positive number of terminal results kept for new lookups.

        Raises:
            ValueError: If ``retention`` is not a positive integer.
        """

        # Retention validation: check positive integer retention limit
        if (
            isinstance(retention, bool)
            or not isinstance(retention, int)
            or retention < 1
        ):
            raise ValueError("Instance retention must be a positive integer.")

        # State initialization: prepare entries lookup map, order queue, and reentrant lock
        self._retention = retention
        self._entries: dict[str, _InstanceEntry] = {}
        self._terminal_order: deque[str] = deque()
        self._lock = threading.RLock()

    @staticmethod
    def _validate_instance_id(instance_id: str) -> str:
        """Validate and return one exact canonical instance identifier.

        Args:
            instance_id: Daemon-created ``speakId`` supplied by the caller.

        Returns:
            str: Unchanged canonical identifier.

        Raises:
            ValueError: If the identifier is not a non-blank exact string.
        """

        # Format validation: check non-empty string and whitespace invariants
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise ValueError("Instance ID is required.")

        # Format validation: ensure instance ID has no surrounding whitespace
        if instance_id != instance_id.strip():
            raise ValueError("Instance ID must not have surrounding whitespace.")

        return instance_id

    @staticmethod
    def _bounded_timeout(timeout: float) -> float:
        """Validate and cap one public wait duration.

        Args:
            timeout: Requested wait duration in seconds.

        Returns:
            float: Finite non-negative duration bounded by the registry limit.

        Raises:
            ValueError: If the duration is negative, non-finite, or non-numeric.
        """

        # Type validation: ensure candidate timeout is numeric
        if isinstance(timeout, bool):
            raise ValueError("Wait timeout must be numeric.")

        # Exception safety: execute block with error handling
        try:
            bounded_timeout = float(timeout)

        # Failure recovery: handle execution failure or mapping error
        except (TypeError, ValueError) as exc:
            raise ValueError("Wait timeout must be numeric.") from exc

        # Bounds calculation: constrain timeout within non-negative registry cap
        if not math.isfinite(bounded_timeout) or bounded_timeout < 0:
            raise ValueError("Wait timeout must be finite and non-negative.")

        return min(bounded_timeout, MAX_INSTANCE_WAIT_SECONDS)

    def register(self, instance_id: str) -> InstanceEnqueueResult:
        """Register one exact instance before its request enters the FIFO.

        Creates a new entry with a private synchronization event in the registry.
        Validates the instance ID and guarantees that duplicate registrations are
        rejected before queue entry.

        Args:
            instance_id: Canonical daemon-created ``speakId`` to register.

        Returns:
            InstanceEnqueueResult: Immutable identity of the accepted instance.

        Raises:
            ValueError: If the identifier is invalid or already registered.
        """
        # Identity resolution and duplicate check: register new entry
        canonical_id = self._validate_instance_id(instance_id)

        # Concurrency control: acquire lock for thread-safe state mutation
        with self._lock:
            # Conditional branch: verify domain preconditions and invariants
            if canonical_id in self._entries:
                raise ValueError(f"Instance already registered: {canonical_id}")

            self._entries[canonical_id] = _InstanceEntry(event=threading.Event())

        return InstanceEnqueueResult(instance_id=canonical_id)

    def wait(self, instance_id: str, timeout: float) -> InstanceTerminalResult | None:
        """Wait a bounded duration for the exact instance terminal result.

        Blocks the calling thread until the specified instance reaches a terminal state
        or until the bounded timeout elapses. Returns the immutable terminal result
        without interfering with other concurrent waiters.

        Args:
            instance_id: Exact canonical ``speakId`` to observe.
            timeout: Maximum wait duration in seconds, capped by the registry.

        Returns:
            InstanceTerminalResult | None: Matching result, or ``None`` on timeout.

        Raises:
            KeyError: If the identifier is unknown or no longer retained.
            ValueError: If the timeout or identifier is invalid.
        """
        canonical_id = self._validate_instance_id(instance_id)
        bounded_timeout = self._bounded_timeout(timeout)

        # Atomic transition: publish first terminal result and release waiters
        with self._lock:
            entry = self._entries.get(canonical_id)

        # Lookup and wait: observe private event up to bounded timeout
        if entry is None:
            raise KeyError(canonical_id)

        # Event synchronization: block until terminal event or timeout
        if not entry.event.wait(timeout=bounded_timeout):
            return None

        # Concurrency control: acquire lock for thread-safe state mutation
        with self._lock:
            return entry.terminal

    def terminalize(
        self,
        instance_id: str,
        state: InstanceTerminalState,
        response: str = "",
    ) -> InstanceTerminalResult | None:
        """Publish the first terminal outcome and reject later races.

        Atomically transitions an instance to its final state (SPEAKED, RESPONSED,
        or CANCELED) and signals waiting threads. Preserves first-winner invariants so
        subsequent terminal requests for the same instance are ignored.

        Args:
            instance_id: Exact canonical ``speakId`` to transition.
            state: One of the three closed terminal states.
            response: Exact response text required only for ``RESPONSED``.

        Returns:
            InstanceTerminalResult | None: Winning result, or ``None`` when a
            previous terminal state already won.

        Raises:
            KeyError: If the identifier is unknown or no longer retained.
            ValueError: If the state or response payload is invalid.
        """
        # Domain validation: check canonical ID, state enum, and response text rules
        canonical_id = self._validate_instance_id(instance_id)

        # Conditional branch: verify domain preconditions and invariants
        if not isinstance(state, InstanceTerminalState):
            raise ValueError("Instance terminal state is invalid.")

        # Response validation: enforce response text rules for terminal state
        if not isinstance(response, str):
            raise ValueError("Instance response must be text.")

        # Response validation: enforce response text rules for terminal state
        if state is InstanceTerminalState.RESPONSED and not response.strip():
            raise ValueError("A responded instance requires response text.")

        # Response validation: enforce response text rules for terminal state
        if state is not InstanceTerminalState.RESPONSED and response:
            raise ValueError("Only a responded instance may contain response text.")

        # Concurrency control: acquire lock for thread-safe state mutation
        with self._lock:
            entry = self._entries.get(canonical_id)

            # Conditional branch: verify domain preconditions and invariants
            if entry is None:
                raise KeyError(canonical_id)

            # Conditional branch: verify domain preconditions and invariants
            if entry.terminal is not None:
                return None

            terminal_result = InstanceTerminalResult(canonical_id, state, response)
            entry.terminal = terminal_result
            self._terminal_order.append(canonical_id)
            entry.event.set()
            self._prune_locked()

            return terminal_result

    def cancel(self, instance_id: str) -> InstanceTerminalResult | None:
        """Cancel one exact instance using the first-winner transition rule.

        Args:
            instance_id: Exact canonical ``speakId`` to cancel.

        Returns:
            InstanceTerminalResult | None: Winning cancellation, or ``None``
            when another terminal state already won.

        Raises:
            KeyError: If the identifier is unknown or no longer retained.
            ValueError: If the identifier is invalid.
        """

        return self.terminalize(instance_id, InstanceTerminalState.CANCELED)

    def cancel_all(self) -> tuple[InstanceTerminalResult, ...]:
        """Cancel every live instance and release all matching waiters.

        Iterates through all registered live instances that have not yet reached a
        terminal state, setting their state to CANCELED and waking waiting threads.
        Used during daemon shutdown or bulk reset operations.

        Args:
            No external arguments are accepted; all registered live instances
            are transitioned.

        Returns:
            tuple[InstanceTerminalResult, ...]: Cancellations won in registry
            insertion order.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self._lock:
            results: list[InstanceTerminalResult] = []

            # Format validation: ensure instance ID has no surrounding whitespace
            for instance_id, entry in tuple(self._entries.items()):
                # Conditional branch: verify domain preconditions and invariants
                if entry.terminal is not None:
                    continue

                terminal_result = InstanceTerminalResult(
                    instance_id, InstanceTerminalState.CANCELED
                )
                entry.terminal = terminal_result
                self._terminal_order.append(instance_id)
                entry.event.set()
                results.append(terminal_result)

            self._prune_locked()

            return tuple(results)

    def result(self, instance_id: str) -> InstanceTerminalResult | None:
        """Return the current terminal result without waiting.

        Args:
            instance_id: Exact canonical ``speakId`` to inspect.

        Returns:
            InstanceTerminalResult | None: Current result, or ``None`` while live.

        Raises:
            KeyError: If the identifier is unknown or no longer retained.
            ValueError: If the identifier is invalid.
        """
        canonical_id = self._validate_instance_id(instance_id)

        # Concurrency control: acquire lock for thread-safe state mutation
        with self._lock:
            entry = self._entries.get(canonical_id)

            # Conditional branch: verify domain preconditions and invariants
            if entry is None:
                raise KeyError(canonical_id)

            return entry.terminal

    def _prune_locked(self) -> None:
        """Discard oldest terminal entries while preserving live entries.

        Args:
            No external arguments are accepted; the helper uses registry state.

        Returns:
            None: The registry is pruned in place.

        This helper requires ``self._lock`` to be held by its caller.
        """

        # Memory management: evict oldest terminal entries beyond retention cap
        while len(self._terminal_order) > self._retention:
            expired_id = self._terminal_order.popleft()
            self._entries.pop(expired_id, None)
