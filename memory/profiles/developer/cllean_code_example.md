# Clean Code Example

```python
"""
Description: Generic typed structure showing cohesive identities, grouped code,
             early returns, and immutable structured output.

File: application/management/dispatch/dispatcher.py

Author: @Yoi
Version: 1.0.5
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final


DEFAULT_IDENTIFIER: Final[str] = "component"
DISABLED_NOTE: Final[str] = "processing disabled"
COMPLETE_NOTE: Final[str] = "processing complete"


class Stage(Enum):
    """Represent the lifecycle state produced by the high-level routine.

    Members:
        READY: Processing is available but no value was accepted.
        SKIPPED: Processing was intentionally bypassed by the caller.
        COMPLETE: Processing accepted at least one normalized value.
    """

    READY = "ready"
    SKIPPED = "skipped"
    COMPLETE = "complete"


@dataclass(frozen=True)
class ExecutionState:
    """Represent the immutable, typed result returned by the high-level routine.

    Attributes:
        identifier: Stable identity of the component that produced the result.
        stage: Lifecycle state reached by the operation.
        requested_count: Number of values received before filtering.
        accepted_count: Number of values retained after processing.
        values: Immutable processed values exposed to the caller.
        note: Human-readable explanation of the resulting state.
    """

    identifier: str
    stage: Stage
    requested_count: int
    accepted_count: int
    values: tuple[str, ...]
    note: str


class Component:
    """Own one cohesive transformation identity and its local rules.

    Attributes:
        identifier: Stable name used in the returned state.
        stage: Initial lifecycle state selected by the caller.
        separator: Character used to trim each value before acceptance.
    """

    def __init__(self, identifier: str, stage: Stage, separator: str = " ") -> None:
        """Initialize a component with typed identity, state, and local rule.

        Args:
            identifier: Stable name assigned by the composition boundary.
            stage: Initial lifecycle state for this component.
            separator: Character used to trim surrounding input characters.
        """
        self._identifier = identifier
        self._stage = stage
        self._separator = separator

    def get_identifier(self) -> str:
        """Return the component identity without exposing mutable internals.

        Returns:
            str: Stable identifier assigned during construction.
        """
        return self._identifier

    def process(self, value: str) -> str:
        """Normalize one value according to the component's local rule.

        Args:
            value: Candidate text received by the high-level routine.

        Returns:
            str: Trimmed value, or an empty string when no content remains.
        """
        return value.strip(self._separator)


def build_execution_state(
    values: tuple[str, ...],
    enabled: bool,
) -> ExecutionState:
    """Instantiate, use, and return one immutable structured result.

    Args:
        values: Immutable input values supplied by the controller boundary.
        enabled: Whether processing is enabled for this invocation.

    Returns:
        ExecutionState: Typed result with documented properties.
    """
    requested_count = len(values)
    
    # Guard clause returns before the loop, keeping the main path vertical.
    if not enabled:
        return ExecutionState(
            identifier=DEFAULT_IDENTIFIER,
            stage=Stage.SKIPPED,
            requested_count=requested_count,
            accepted_count=0,
            values=(),
            note=DISABLED_NOTE,
        )
    
    # Compose the class once and prepare valid values outside the loop.
    component = Component(DEFAULT_IDENTIFIER, Stage.READY)
    normalized_values = filter(None, (component.process(value) for value in values))
    processed_values: list[str] = []
    
    # The loop is a standalone vertical block, not nested in a conditional.
    for normalized_value in normalized_values:
        processed_values.append(normalized_value)

    accepted_count = len(processed_values)

    # Select the final enum state in a separate, readable decision block.
    final_stage = Stage.COMPLETE if accepted_count else Stage.READY

    return ExecutionState(
        identifier=component.get_identifier(),
        stage=final_stage,
        requested_count=requested_count,
        accepted_count=accepted_count,
        values=tuple(processed_values),
        note=COMPLETE_NOTE,
    )
```
