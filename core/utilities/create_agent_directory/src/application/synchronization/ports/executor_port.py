"""Typed port for executing ordered synchronization change operations."""

from dataclasses import dataclass
from typing import Protocol

from ....domain.change_operation_dto import ChangeOperationDTO


@dataclass(frozen=True)
class OperationResult:
    """Describe the immutable outcome of one executed change operation.

    Attributes:
        target: Relative target path supplied by the operation DTO.
        strategy: Strategy name applied by the executor.
        changed: Whether destination content changed.
    """

    target: str
    strategy: str
    changed: bool


@dataclass(frozen=True)
class SynchronizationResult:
    """Aggregate immutable statistics and outcomes for one execution batch.

    Attributes:
        operation_count: Number of operation DTOs accepted for execution.
        changed_count: Number of operations that changed destination content.
        unchanged_count: Number of operations that left destination content unchanged.
        operations: Ordered immutable per-operation outcomes matching the input DTOs.
    """

    operation_count: int
    changed_count: int
    unchanged_count: int
    operations: tuple[OperationResult, ...]


class OperationExecutorPort(Protocol):
    """Define execution of injected, ordered synchronization operation DTOs."""

    def execute(
        self,
        operations: tuple[ChangeOperationDTO, ...],
    ) -> SynchronizationResult:
        """Execute an ordered batch and return immutable aggregate statistics.

        Args:
            operations: Ordered immutable operation DTOs with injected source and
                target paths.

        Returns:
            SynchronizationResult: Aggregate counts and ordered operation outcomes.

        Raises:
            OSError: If filesystem I/O fails.
            ValueError: If paths violate containment.
        """
        ...
