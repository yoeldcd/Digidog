"""Immutable contracts shared by the guarded patching vertical."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MutationKind(StrEnum):
    """Describe the filesystem operation represented by a planned mutation."""

    CREATE = "create"
    EDIT = "edit"
    MOVE = "move"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class ReplacementSpec:
    """Represent one ordered exact or contextual text replacement.

    Attributes:
        old: Required non-empty source anchor.
        new: Replacement text, which may be empty.
        expected_occurrences: Exact required source occurrence count.
        contextual: Whether native line-context matching is allowed.
        end_of_file: Whether a contextual match must end at the file boundary.
    """

    old: str
    new: str
    expected_occurrences: int
    contextual: bool = False
    end_of_file: bool = False


@dataclass(frozen=True, slots=True)
class EditSpec:
    """Represent replacements to apply to one existing relative file.

    Attributes:
        path: Workspace-relative target path.
        replacements: Ordered immutable replacements for the target.
        allow_empty_result: Whether a fully empty transformed file is intentional.
    """

    path: str
    replacements: tuple[ReplacementSpec, ...]
    allow_empty_result: bool
    destination_path: str | None = None


@dataclass(frozen=True, slots=True)
class CreateSpec:
    """Represent one new workspace-relative UTF-8 file.

    Attributes:
        path: Workspace-relative absent target path.
        content: UTF-8 text to write to the new file.
        allow_empty_result: Whether an empty new file is intentional.
    """

    path: str
    content: str
    allow_empty_result: bool


@dataclass(frozen=True, slots=True)
class MoveSpec:
    """Represent a safe workspace-relative file relocation.

    Attributes:
        from_path: Workspace-relative existing source path.
        to_path: Workspace-relative absent target path.
    """

    from_path: str
    to_path: str


@dataclass(frozen=True, slots=True)
class DeleteSpec:
    """Represent a safe workspace-relative file deletion.

    Attributes:
        path: Workspace-relative existing file path to remove.
    """

    path: str


@dataclass(frozen=True, slots=True)
class PatchRequest:
    """Represent one validated patch request without mutable boundary values.

    Attributes:
        edits: Immutable edit declarations.
        creates: Immutable create declarations.
        moves: Immutable move declarations.
        deletes: Immutable delete declarations.
    """

    edits: tuple[EditSpec, ...] = ()
    creates: tuple[CreateSpec, ...] = ()
    moves: tuple[MoveSpec, ...] = ()
    deletes: tuple[DeleteSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class FileEvidence:
    """Expose redacted verification facts for one planned or committed file.

    Attributes:
        path: Workspace-relative target path.
        operation: Planned filesystem operation.
        replacement_count: Number of ordered replacements.
        before_length: Byte count before mutation, or zero for a create.
        after_length: Byte count after mutation.
        before_sha256: SHA-256 before mutation, or an empty string for a create.
        after_sha256: SHA-256 after mutation.
    """

    path: str
    operation: MutationKind
    replacement_count: int
    before_length: int
    after_length: int
    before_sha256: str
    after_sha256: str


@dataclass(frozen=True, slots=True)
class PatchResult:
    """Expose immutable, source-redacted patch execution evidence.

    Attributes:
        check: Whether the request was validated without writes.
        files: Per-file hash, byte-length, and replacement-count evidence.
        rollback: Rollback state for an attempted execution.
        cleanup: Status of post-commit artifact cleanup.
        recovery_artifacts: Source-redacted retained recovery artifact identifiers.
    """

    check: bool
    files: tuple[FileEvidence, ...]
    rollback: str
    cleanup: str
    recovery_artifacts: tuple[str, ...]
