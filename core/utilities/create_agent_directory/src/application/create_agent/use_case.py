"""Application boundary for creating an agent directory structure.

Provides high-level application orchestration for instantiating new agent
directories from canonical templates. Resolves target paths and delegates
file synchronization operations to domain executors.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Callable, Mapping, Protocol

from ...domain.change_operation_dto import ChangeOperationDTO, ChangeOperationStrategy
from ..synchronization.ports.executor_port import SynchronizationResult


class OperationExecutor(Protocol):
    """Execute immutable directory operations.

    Methods:
        execute: Apply the supplied operation catalog and return its result.
    """

    def execute(self, operations: tuple[ChangeOperationDTO, ...]) -> SynchronizationResult:
        """Execute operations in their declared order.

        Args:
            operations: Immutable operation catalog to apply.

        Returns:
            SynchronizationResult: Outcome of the synchronization.
        """
        ...


@dataclass(frozen=True)
class CreateAgentDirectoryInput:
    """Input required to create an agent directory.

    Attributes:
        parent_path: Directory under which the agent directory is created.
        agent_name: Requested agent identity, optionally prefixed with ``@``.
        user_name: User identity written into generated files.
    """

    parent_path: Path
    agent_name: str
    user_name: str


@dataclass(frozen=True)
class CreateAgentDirectoryResult:
    """Immutable result of a successful creation.

    Attributes:
        agent_name: Normalized agent identity.
        user_name: Trimmed user identity.
        agent_root: Published agent directory.
        staging_root: Temporary staging directory used during execution.
        operations: Immutable operation catalog that was executed.
        execution: Synchronization outcome returned by the executor.
    """

    agent_name: str
    user_name: str
    agent_root: Path
    staging_root: Path
    operations: tuple[ChangeOperationDTO, ...]
    execution: SynchronizationResult


def normalize_agent_name(agent_name: str) -> str:
    """Validate and normalize an optionally-prefixed agent identity.

    Args:
        agent_name: Candidate identity to validate.

    Returns:
        str: Identity with exactly one leading ``@``.

    Raises:
        ValueError: If the identity is empty, multiline, or has invalid characters.
    """

    invalid_characters = ("\x00", "\n", "\r")

    # Conditional check: evaluate domain preconditions and invariants

    if any(char in agent_name for char in invalid_characters):
        raise ValueError("agent_name must be non-empty single-line")

    value = agent_name.strip()
    candidate = value[1:] if value.startswith("@") else value

    # Conditional check: evaluate domain preconditions and invariants

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", candidate):
        raise ValueError("agent_name has invalid format")

    return f"@{candidate}"


def _user(value: str) -> str:
    """Validate and trim a user name.

    Args:
        value: Candidate user identity.

    Returns:
        str: Trimmed user identity.

    Raises:
        ValueError: If the identity is empty or contains control line characters.
    """

    invalid_characters = ("\x00", "\n", "\r")

    # Conditional check: evaluate domain preconditions and invariants

    if any(char in value for char in invalid_characters):
        raise ValueError("user_name must be non-empty single-line")

    normalized_value = value.strip()

    # Conditional check: evaluate domain preconditions and invariants

    if not normalized_value:
        raise ValueError("user_name must be non-empty single-line")

    return normalized_value


class CreateAgentDirectoryUseCase:
    """Coordinate validation, execution, publication, and rollback.

    Args:
        source_root: Root containing source assets and templates.
        exists_reader: Predicate checking whether a path already exists.
        staging_path_factory: Builds the staging path for an agent root.
        render_values_factory: Builds template values for the requested agent.
        executor_factory: Creates an operation executor for source and staging roots.
        lifecycle_bootstrap: Initializes lifecycle state in the staging directory.
        publisher: Publishes staging content at the final agent root.
        rollback: Removes staging content after a failed operation.
    """

    def __init__(
        self,
        source_root: Path,
        exists_reader: Callable[[Path], bool],
        staging_path_factory: Callable[[Path], Path],
        render_values_factory: Callable[[Path, str, str], Mapping[str, object]],
        executor_factory: Callable[[Path, Path, Mapping[str, object]], OperationExecutor],
        lifecycle_bootstrap: Callable[[Path], None],
        publisher: Callable[[Path, Path], None],
        rollback: Callable[[Path], None],
    ) -> None:
        """Initialize dependencies for directory creation.

        Args:
            source_root: Root containing source assets and templates.
            exists_reader: Predicate checking whether a path already exists.
            staging_path_factory: Builds the staging path for an agent root.
            render_values_factory: Builds template values for the requested agent.
            executor_factory: Creates an operation executor for source and staging roots.
            lifecycle_bootstrap: Initializes lifecycle state in the staging directory.
            publisher: Publishes staging content at the final agent root.
            rollback: Removes staging content after a failed operation.
        """

        self._source_root = Path(source_root)
        self._exists = exists_reader
        self._staging = staging_path_factory
        self._render_values = render_values_factory
        self._executor = executor_factory
        self._lifecycle = lifecycle_bootstrap
        self._publisher = publisher
        self._rollback = rollback

    def build_operations(self) -> tuple[ChangeOperationDTO, ...]:
        """Build the definitive immutable operation catalog.

        Args:
            None

        Returns:
            tuple[ChangeOperationDTO, ...]: Operations in execution order.
        """

        operations: list[ChangeOperationDTO] = []
        directories = (

            # Direct cloned brain core infrastructure
            ("core/brain", "core/brain"),
            ("core/brain_explorer", "core/brain_explorer"),
            
            # Direct cloned public utilities registration
            ("core/utilities/apply_text_patch", "core/utilities/apply_text_patch"),
            ("core/utilities/code_quality_evaluator", "core/utilities/code_quality_evaluator"),
            ("core/utilities/documentation_utils", "core/utilities/documentation_utils"),
            ("core/utilities/propagate_agent_prompt", "core/utilities/propagate_agent_prompt"),
            
            # Direct cloned memory
            ("memory/cli", "memory/cli"),
            ("memory/engineering", "memory/engineering"),
            ("memory/planning", "memory/planning"),
            ("memory/workers", "memory/workers"),
            ("memory/profiles/software_engineer", "memory/profiles/software_engineer"),
        
            # Direct cloned assets
            ("core/assets/screens", "core/assets/screens"),
            ("core/assets/avatar", "core/assets/avatar"),
            
        )
        exclusions = ("__pycache__", ".pytest_cache", "node_modules", "tests", "documentation/wiki")

        # Iteration: loop over collection elements

        for source, target in directories:
            operations.append(ChangeOperationDTO(Path(source), Path(target), ChangeOperationStrategy.COPY))

            # Iteration: loop over collection elements

            for exclusion in exclusions:
                source_exclusion_path = Path(source) / exclusion
                target_exclusion_path = Path(target) / exclusion
                operations.append(
                    ChangeOperationDTO(source_exclusion_path, target_exclusion_path, ChangeOperationStrategy.EXCLUDE)
                )

        copy_operations = (
            ("core/requirements.txt", "core/requirements.txt"),
            (
                "core/utilities/create_agent_directory/create_agent_directory.py",
                "core/utilities/create_agent_directory/create_agent_directory.py",
            ),
            ("core/utilities/create_agent_directory/src", "core/utilities/create_agent_directory/src"),
            ("core/utilities/create_agent_directory/files", "core/utilities/create_agent_directory/files"),
            (
                "core/utilities/create_agent_directory/templates",
                "core/utilities/create_agent_directory/templates",
            ),
            (
                "core/utilities/create_agent_directory/documentation",
                "core/utilities/create_agent_directory/documentation",
            ),
        )

        # Iteration: process sequence items

        for source, target in copy_operations:
            operations.append(ChangeOperationDTO(Path(source), Path(target), ChangeOperationStrategy.COPY))

        replace_operations = (
            ("core/README.md", "README.md"),
            ("core/utilities/create_agent_directory/files/LICENSE", "LICENSE"),
        )

        # Iteration: process sequence items

        for source, target in replace_operations:
            operations.append(ChangeOperationDTO(Path(source), Path(target), ChangeOperationStrategy.REPLACE))

        render_operations = (
            ("core/utilities/create_agent_directory/templates/AGENTS.md", "core/AGENTS.md"),
            ("core/utilities/create_agent_directory/templates/brain_configs.json", "core/configs/brain_configs.json"),
            (
                "core/utilities/create_agent_directory/templates/brain_avatar_config.json",
                "core/configs/brain_avatar_config.json",
            ),
            ("core/utilities/create_agent_directory/templates/brain_mirrors.json", "core/configs/brain_mirrors.json"),
        )

        # Iteration: process sequence items

        for template, target in render_operations:
            operations.append(
                ChangeOperationDTO(Path(), Path(target), ChangeOperationStrategy.RENDER, template=template)
            )

        return tuple(operations)

    def execute(self, request: CreateAgentDirectoryInput) -> CreateAgentDirectoryResult:
        """Create an agent directory and roll back failed staging.

        Args:
            request: Validated creation request containing paths and identities.

        Returns:
            CreateAgentDirectoryResult: Published directory and execution details.

        Raises:
            FileExistsError: If destination or staging already exists.
            Exception: Any execution, lifecycle, or publication failure is re-raised after rollback.
        """

        agent_name = normalize_agent_name(request.agent_name)
        user_name = _user(request.user_name)
        agent_root = Path(request.parent_path) / agent_name
        staging_root = self._staging(agent_root)

        # Conditional check: evaluate domain preconditions and invariants

        if self._exists(agent_root) or self._exists(staging_root):
            raise FileExistsError("destination or staging exists")

        operations = self.build_operations()

        # Exception safety: execute operation within error boundary

        try:
            values = self._render_values(agent_root, agent_name, user_name)
            executor = self._executor(self._source_root, staging_root, values)
            execution = executor.execute(operations)
            self._lifecycle(staging_root)
            self._publisher(staging_root, agent_root)

            return CreateAgentDirectoryResult(
                agent_name,
                user_name,
                agent_root,
                staging_root,
                operations,
                execution,
            )

        # Failure recovery: handle execution or transport exception

        except Exception:
            self._rollback(staging_root)

            raise
