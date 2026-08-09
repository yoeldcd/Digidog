"""Coordinate synchronization of a target agent directory from canonical sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol

from ...domain.change_operation_dto import ChangeOperationDTO, ChangeOperationStrategy
from ..synchronization.ports.executor_port import SynchronizationResult


class OperationExecutor(Protocol):
    """Execute a tuple of directory synchronization operations."""

    def execute(
        self,
        operations: tuple[ChangeOperationDTO, ...],
    ) -> SynchronizationResult:
        """Execute operations and return their synchronization result.

        Args:
            operations: Immutable, ordered operations to execute.

        Returns:
            SynchronizationResult: Result reported by the synchronization adapter.
        """
        ...


@dataclass(frozen=True)
class UpdateAgentInput:
    """Describe the optional target directory supplied to the use case.

    Attributes:
        target_root: Directory to update when it differs from the configured target.
    """

    target_root: Path


@dataclass(frozen=True)
class UpdateAgentResult:
    """Report the immutable result of updating an agent directory.

    Attributes:
        source_root: Canonical source directory used for synchronization.
        target_root: Resolved target directory that was updated.
        operations: Operations submitted to the executor.
        execution: Executor result describing applied operations.
        updated_paths: Target paths for non-excluded operations.
    """

    source_root: Path
    target_root: Path
    operations: tuple[ChangeOperationDTO, ...]
    execution: SynchronizationResult
    updated_paths: tuple[Path, ...]


IdentityReader = Callable[[Path], tuple[str, str]]
RenderValuesFactory = Callable[[Path, str, str], Mapping[str, object]]
ExecutorFactory = Callable[[Path, Path, Mapping[str, object]], OperationExecutor]


class UpdateAgentUseCase:
    """Validate an agent target, build operations, and execute synchronization."""

    def __init__(
        self,
        source_root: Path,
        target_root: Path,
        exists_reader: Callable[[Path], bool],
        file_reader: Callable[[Path], bool],
        identity_reader: IdentityReader,
        executor_factory: ExecutorFactory,
        render_values_factory: RenderValuesFactory,
        lifecycle_runner: Callable[[Path], None],
    ) -> None:
        """Initialize synchronization dependencies.

        Args:
            source_root: Canonical directory containing source material.
            target_root: Default directory to update when no request is supplied.
            exists_reader: Predicate checking whether the target directory exists.
            file_reader: Predicate checking whether a required file exists.
            identity_reader: Reader returning the target agent and user identities.
            executor_factory: Factory creating an operation executor.
            render_values_factory: Factory creating template values for an identity.
            lifecycle_runner: Callback run after synchronization completes.
        """

        self._source_root = Path(source_root)
        self._target_root = Path(target_root)
        self._exists_reader = exists_reader
        self._file_reader = file_reader
        self._identity_reader = identity_reader
        self._executor_factory = executor_factory
        self._render_values_factory = render_values_factory
        self._lifecycle_runner = lifecycle_runner

    def build_operations(self) -> tuple[ChangeOperationDTO, ...]:
        """Build the ordered operation list for an agent update.

        Returns:
            tuple[ChangeOperationDTO, ...]: Ordered synchronization operations.
        """
        directory_specs = (
            ("core/brain", True),
            ("core/brain_explorer", True),
            ("core/assets/screens", True),
            ("core/utilities/create_agent_directory/src", False),
            ("core/utilities/create_agent_directory/files", False),
            ("core/utilities/create_agent_directory/templates", False),
            ("core/utilities/create_agent_directory/documentation", False),
            ("core/utilities/propagate_agent_prompt", False),
            ("core/utilities/apply_text_patch", False),
            ("memory/profiles/developer", True),
            ("memory/profiles/worker", True),
        )
        exclusions = ("__pycache__", ".pytest_cache", "node_modules", "tests", "documentation/wiki")
        operations: list[ChangeOperationDTO] = []

        for root, remove_stale in directory_specs:
            root_path = Path(root)
            operations.append(
                ChangeOperationDTO(
                    root_path,
                    root_path,
                    ChangeOperationStrategy.COPY,
                    remove_stale=remove_stale,
                )
            )

            for excluded in exclusions:
                excluded_path = root_path / excluded
                operations.append(
                    ChangeOperationDTO(
                        excluded_path,
                        excluded_path,
                        ChangeOperationStrategy.EXCLUDE,
                    )
                )

        operations.extend(
            (
                ChangeOperationDTO(Path("core/README.md"), Path("README.md"), ChangeOperationStrategy.REPLACE),
                ChangeOperationDTO(
                    Path("core/utilities/create_agent_directory/files/LICENSE"),
                    Path("LICENSE"),
                    ChangeOperationStrategy.REPLACE,
                ),
                ChangeOperationDTO(
                    Path("core/utilities/create_agent_directory/create_agent_directory.py"),
                    Path("core/utilities/create_agent_directory/create_agent_directory.py"),
                    ChangeOperationStrategy.COPY,
                ),
                ChangeOperationDTO(
                    Path(),
                    Path("core/AGENTS.md"),
                    ChangeOperationStrategy.RENDER,
                    template="core/utilities/create_agent_directory/templates/AGENTS.md",
                ),
                ChangeOperationDTO(
                    Path("core/utilities/create_agent_directory/templates/brain_configs.json"),
                    Path("core/configs/brain_configs.json"),
                    ChangeOperationStrategy.MERGE,
                ),
                ChangeOperationDTO(
                    Path("core/utilities/create_agent_directory/templates/brain_avatar_config.json"),
                    Path("core/configs/brain_avatar_config.json"),
                    ChangeOperationStrategy.MERGE,
                ),
                ChangeOperationDTO(
                    Path("core/utilities/create_agent_directory/templates/brain_mirrors.json"),
                    Path("core/configs/brain_mirrors.json"),
                    ChangeOperationStrategy.MERGE,
                ),
            )
        )

        return tuple(operations)

    def execute(self, request: UpdateAgentInput | None = None) -> UpdateAgentResult:
        """Validate, synchronize, and finalize an agent directory update.

        Args:
            request: Optional request overriding the configured target directory.

        Returns:
            UpdateAgentResult: Immutable synchronization outcome.

        Raises:
            ValueError: If source and target match or target identity is incomplete.
            FileNotFoundError: If the target or required brain script is missing.
        """

        requested_target = self._target_root if request is None else Path(request.target_root)
        source = self._source_root.resolve()
        target = requested_target.resolve()

        if source == target:
            raise ValueError("source and target roots must differ")

        if not self._exists_reader(target):
            raise FileNotFoundError(target)

        brain = target / "$agent/scripts/brain.py"

        if not self._file_reader(brain):
            raise FileNotFoundError(brain)

        agent, user = self._identity_reader(target)

        if not agent or not user:
            raise ValueError("target identity is required")

        values = self._render_values_factory(target, agent, user)
        operations = self.build_operations()
        executor = self._executor_factory(source, target, values)
        execution = executor.execute(operations)
        self._lifecycle_runner(target)
        updated_paths = tuple(
            operation.target
            for operation in operations
            if operation.strategy is not ChangeOperationStrategy.EXCLUDE
        )

        return UpdateAgentResult(
            source,
            target,
            operations,
            execution,
            updated_paths,
        )