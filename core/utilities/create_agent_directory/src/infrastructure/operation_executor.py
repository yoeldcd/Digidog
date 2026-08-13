"""Filesystem operation executor with containment and atomic writes."""

from __future__ import annotations

# Standard library imports
import json
import os
import tempfile
from pathlib import Path
from typing import Callable

# Project imports
from ..application.synchronization.ports.executor_port import OperationResult, SynchronizationResult
from ..domain.change_operation_dto import ChangeOperationDTO, ChangeOperationStrategy
from .json_normalizer import normalize_missing_keys


class FilesystemOperationExecutor:
    """Execute ordered synchronization operations against injected roots.

    Attributes:
        _source: Resolved source containment root.
        _target: Resolved target containment root.
        _renderer: Optional template renderer.
    """

    def __init__(self, source_root: Path, target_root: Path, renderer: Callable[[str], str] | None = None) -> None:
        """Initialize the executor.

        Args:
            source_root: Root containing source resources.
            target_root: Root receiving generated resources.
            renderer: Optional template-to-text callable.
        """

        self._source = source_root.resolve()
        self._target = target_root.resolve()
        self._renderer = renderer

    def execute(self, operations: tuple[ChangeOperationDTO, ...]) -> SynchronizationResult:
        """Execute operations and return one result per executable DTO.

        Args:
            operations: Immutable ordered operation DTOs.
        Returns:
            SynchronizationResult: Aggregate immutable execution statistics.
        Raises:
            ValueError: If EXCLUDE metadata is malformed or paths are unsafe.
            OSError: If filesystem I/O fails.
        """
        executable: list[tuple[ChangeOperationDTO, tuple[ChangeOperationDTO, ...]]] = []
        index = 0

        while index < len(operations):
            operation = operations[index]
            if operation.strategy is ChangeOperationStrategy.EXCLUDE:
                raise ValueError("EXCLUDE must immediately follow a COPY operation")
            exclusions: list[ChangeOperationDTO] = []
            index += 1

            while index < len(operations) and operations[index].strategy is ChangeOperationStrategy.EXCLUDE:
                exclusions.append(operations[index])
                index += 1

            if exclusions and operation.strategy is not ChangeOperationStrategy.COPY:
                raise ValueError("EXCLUDE metadata must follow COPY")
            executable.append((operation, tuple(exclusions)))

        results = tuple(self._execute_operation(operation, exclusions) for operation, exclusions in executable)
        changed_count = sum(result.changed for result in results)
        return SynchronizationResult(len(results), changed_count, len(results) - changed_count, results)

    def _execute_operation(
        self, operation: ChangeOperationDTO, exclusions: tuple[ChangeOperationDTO, ...]
    ) -> OperationResult:
        """Execute one DTO and return one aggregate result.

        Args:
            operation: Operation DTO to execute.
            exclusions: Contiguous EXCLUDE metadata following a COPY.
        Returns:
            OperationResult: Changed state for the operation.
        Raises:
            ValueError: If exclusion or containment rules are violated.
        """

        destination = self._safe(self._target, operation.target)

        if operation.strategy is ChangeOperationStrategy.RENDER:
            if exclusions or self._renderer is None or operation.template is None:
                raise ValueError("renderer required and EXCLUDE is invalid")
            return OperationResult(str(operation.target), operation.strategy.value, self._atomic_write(destination, self._renderer(operation.template).encode("utf-8")))
        source = self._safe(self._source, operation.source)

        if exclusions:
            self._validate_exclusions(operation, exclusions)

        if operation.strategy is ChangeOperationStrategy.COPY and source.is_dir():
            changed = self._copy_directory(source, destination, operation, exclusions)
            return OperationResult(str(operation.target), operation.strategy.value, changed)

        if exclusions:
            raise ValueError("file COPY cannot have EXCLUDE children")

        if operation.strategy is ChangeOperationStrategy.MERGE:
            source_data = json.loads(source.read_text(encoding="utf-8"))

            if destination.exists():
                target_data = json.loads(destination.read_text(encoding="utf-8"))
                if isinstance(source_data, dict) and isinstance(target_data, dict):
                    merged = normalize_missing_keys(source_data, target_data)
                else:
                    merged = target_data
            else:
                merged = source_data

            content = json.dumps(merged, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            changed = self._atomic_write(destination, content.encode("utf-8"))
        else:
            changed = self._atomic_write(destination, source.read_bytes())

        return OperationResult(str(operation.target), operation.strategy.value, changed)

    def _copy_directory(self, source: Path, destination: Path, operation: ChangeOperationDTO, exclusions: tuple[ChangeOperationDTO, ...]) -> bool:
        """Copy directory contents atomically and optionally remove stale files.

        Args:
            source: Contained source directory.
            destination: Contained destination directory.
            operation: Parent COPY DTO.
            exclusions: Validated exclusion DTOs.
        Returns:
            bool: Whether any file changed or stale entry was removed.
        """

        excluded = tuple((item.source, item.target) for item in exclusions)
        destination_created = not destination.exists()
        destination.mkdir(parents=True, exist_ok=True)
        changed = destination_created
        copied: set[Path] = set()

        for root, _, files in os.walk(source):
            for filename in files:
                source_file = Path(root) / filename
                relative = source_file.relative_to(source)
                if any(self._is_excluded(relative, src.relative_to(operation.source)) for src, _ in excluded):
                    continue
                target_file = destination / relative
                if self._atomic_write(target_file, source_file.read_bytes()):
                    changed = True
                copied.add(relative)

        if operation.remove_stale and destination.exists():
            for root, dirs, files in os.walk(destination, topdown=False):
                root_path = Path(root)

                for filename in files:
                    relative = (root_path / filename).relative_to(destination)
                    if relative in copied or any(self._is_excluded(relative, tgt.relative_to(operation.target)) for _, tgt in excluded):
                        continue
                    (root_path / filename).unlink()
                    changed = True

                for dirname in dirs:
                    directory = root_path / dirname
                    try:
                        directory.rmdir()
                        changed = True
                    except OSError:
                        pass

        return changed

    def _validate_exclusions(self, operation: ChangeOperationDTO, exclusions: tuple[ChangeOperationDTO, ...]) -> None:
        """Validate EXCLUDE source and target nesting under a COPY parent.

        Args:
            operation: Parent COPY DTO.
            exclusions: EXCLUDE metadata to validate.
        Raises:
            ValueError: If metadata is not nested under both parent paths.
        """

        for metadata in exclusions:
            if not self._is_nested(metadata.source, operation.source) or not self._is_nested(metadata.target, operation.target):
                raise ValueError("EXCLUDE paths must be nested under COPY")

    @staticmethod
    def _is_nested(candidate: Path, parent: Path) -> bool:
        """Return whether candidate is equal to or nested under parent."""

        return candidate == parent or parent in candidate.parents

    @staticmethod
    def _is_excluded(relative: Path, excluded: Path) -> bool:
        """Return whether relative identifies an excluded path or descendant."""

        return relative == excluded or excluded in relative.parents

    @staticmethod
    def _safe(root: Path, relative: Path) -> Path:
        """Resolve a relative path and enforce root containment.

        Args:
            root: Trusted containment root.
            relative: Relative candidate path.
        Returns:
            Path: Resolved contained path.
        Raises:
            ValueError: If the resolved path escapes root.
        """
        path = (root / relative).resolve()

        if root not in path.parents and path != root:
            raise ValueError("path escapes root")
        return path

    @staticmethod
    def _atomic_write(destination: Path, content: bytes) -> bool:
        """Atomically replace destination when bytes differ.

        Args:
            destination: Final destination path.
            content: Complete bytes to write.
        Returns:
            bool: Whether destination content changed.
        Raises:
            OSError: If staging or replacement fails.
        """

        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists() and destination.read_bytes() == content:
            return False

        descriptor, temporary = tempfile.mkstemp(dir=destination.parent, prefix=".tmp-")

        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True
