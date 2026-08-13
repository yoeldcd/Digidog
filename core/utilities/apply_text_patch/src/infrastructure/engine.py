"""Confined, redacted, transactional filesystem patch execution."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from ..domain.models import (
    CreateSpec,
    DeleteSpec,
    EditSpec,
    FileEvidence,
    MoveSpec,
    MutationKind,
    PatchRequest,
    PatchResult,
)


class PatchExecutionError(RuntimeError):
    """Indicate a safe planning, write, or rollback failure.

    Attributes:
        evidence: Redacted facts prepared before the failure.
        rollback: Result of any required rollback operation.
        cleanup: Status of post-commit artifact cleanup.
        recovery_artifacts: Source-redacted retained recovery artifact identifiers.
    """

    def __init__(
        self,
        message: str,
        evidence: tuple[FileEvidence, ...] = (),
        rollback: str = "not-needed",
        cleanup: str = "not-needed",
        recovery_artifacts: tuple[str, ...] = (),
    ) -> None:
        """Initialize execution error with evidence and rollback state.

        Args:
            message: Human-readable failure explanation.
            evidence: Redacted facts prepared before failure.
            rollback: Status of batch rollback operation.
            cleanup: Status of temporary file cleanup operation.
            recovery_artifacts: Identifiers of retained recovery files.
        """
        super().__init__(message)
        self.evidence = evidence
        self.rollback = rollback
        self.cleanup = cleanup
        self.recovery_artifacts = recovery_artifacts


@dataclass(frozen=True, slots=True)
class _Encoding:
    """Retain supported original payload encoding and BOM.

    Attributes:
        codec: Python codec string (e.g. utf-8, utf-16-le).
        bom: Byte order mark prefix bytes.
    """

    codec: str
    bom: bytes


@dataclass(frozen=True, slots=True)
class _Mutation:
    """Retain private verified bytes required for one commit.

    Attributes:
        target: Physical target path on disk.
        relative_path: Workspace-relative path string.
        kind: Planned filesystem mutation type.
        original: Raw source bytes before mutation.
        final: Transformed target bytes to write.
        replacement_count: Number of replacements applied.
        source_target: Optional source path for move operations.
    """

    target: Path
    relative_path: str
    kind: MutationKind
    original: bytes
    final: bytes
    replacement_count: int
    source_target: Path | None = None


@dataclass(frozen=True, slots=True)
class _Committed:
    """Retain one committed mutation and its recovery backup.

    Attributes:
        mutation: Execution mutation details.
        backup: Physical backup file path in transient directory.
    """

    mutation: _Mutation
    backup: Path | None


class FileSystemPatchEngine:
    """Plan and apply exact text patches below one physical workspace root.

    Attributes:
        _root: Trusted physical workspace root directory.
        _replace: Replacement function seam used for file substitution.
        _transient_dir: Directory used for temporary rollback backups.
    """

    def __init__(
        self,
        root: Path,
        transient_dir: Path,
        replace_function: Callable[[Path, Path], None] | None = None,
    ) -> None:
        """Initialize the engine with its single trusted workspace boundary.

        Args:
            root: Trusted workspace root that confines every target.
            transient_dir: Existing physical directory for rollback backups.
            replace_function: Optional atomic replacement seam for testing.
        """
        self._root = root.absolute()
        self._replace = replace_function or os.replace
        self._transient_dir = transient_dir.absolute()


    def execute(self, request: PatchRequest, check: bool) -> PatchResult:
        """Plan a request and optionally commit its prepared files.

        Args:
            request: Strict immutable patch request.
            check: Whether to return the plan without filesystem writes.

        Returns:
            PatchResult: Redacted hash, byte-length, and count evidence.

        Raises:
            PatchExecutionError: A path, decoding, anchor, commit, or rollback guard fails.
        """
        mutations = self._plan(request)
        evidence = tuple(self._evidence(mutation) for mutation in mutations)

        if check:
            return PatchResult(
                check=True,
                files=evidence,
                rollback="not-needed",
                cleanup="not-needed",
                recovery_artifacts=(),
            )

        committed: list[_Committed] = []

        try:
            for mutation in mutations:
                committed.append(self._commit(mutation))
        except OSError as exc:
            rollback = self._rollback(committed)
            cleanup = self._cleanup(committed)
            raise PatchExecutionError(
                "Patch commit failed; prepared changes were rolled back where possible.",
                evidence,
                rollback=rollback,
                cleanup=cleanup,
                recovery_artifacts=(),
            ) from exc

        cleanup = self._cleanup(committed)

        return PatchResult(
            check=False,
            files=evidence,
            rollback="not-needed",
            cleanup=cleanup,
            recovery_artifacts=(),
        )


    def _plan(self, request: PatchRequest) -> tuple[_Mutation, ...]:
        """Prepare all requested changes before any write occurs.

        Args:
            request: Validated patch request.

        Returns:
            tuple[_Mutation, ...]: Prepared mutation objects ready for execution.
        """
        self._validate_root()
        self._validate_transient_dir()

        return (
            tuple(self._plan_edit(edit) for edit in request.edits)
            + tuple(self._plan_create(create) for create in request.creates)
            + tuple(self._plan_move(move) for move in request.moves)
            + tuple(self._plan_delete(delete) for delete in request.deletes)
        )


    def _plan_edit(self, edit: EditSpec) -> _Mutation:
        """Prepare a fully transformed existing file without writing it.

        Args:
            edit: Edit specification containing target path and replacements.

        Returns:
            _Mutation: Prepared edit mutation object.

        Raises:
            PatchExecutionError: If target file does not exist, is invalid, or fails anchors.
        """
        source_target = self._target(edit.path)
        if not source_target.exists() or not source_target.is_file():
            raise PatchExecutionError(f"Edit target does not exist as a regular file: {edit.path}")

        destination_target = self._target(edit.destination_path) if edit.destination_path is not None else None
        if destination_target is not None:
            if destination_target.exists():
                raise PatchExecutionError(f"Edit destination target already exists: {edit.destination_path}")
            if not destination_target.parent.is_dir():
                raise PatchExecutionError(f"Edit destination parent directory does not exist: {edit.destination_path}")

        try:
            original = source_target.read_bytes()
        except OSError as exc:
            raise PatchExecutionError(f"Unable to read edit target: {edit.path}") from exc

        text, encoding = self._decode(original, edit.path)
        transformed = text

        for replacement in edit.replacements:
            if replacement.contextual and not replacement.old:
                transformed = self._append_contextual_replacement(
                    transformed,
                    replacement.new,
                    replacement.end_of_file,
                    edit.path,
                )
                continue

            source_anchor, replacement_text = self._resolve_replacement_anchor(
                transformed,
                replacement.old,
                replacement.new,
                replacement.expected_occurrences,
                edit.path,
                contextual=replacement.contextual,
                end_of_file=replacement.end_of_file,
            )
            transformed = transformed.replace(source_anchor, replacement_text, replacement.expected_occurrences)

        if not transformed and not edit.allow_empty_result:
            raise PatchExecutionError(f"Edit result is empty for {edit.path}; set allowEmptyResult to true to permit it.")

        final = encoding.bom + transformed.encode(encoding.codec, errors="strict")
        if final == original:
            raise PatchExecutionError(f"Edit is a semantic no-op for target: {edit.path}")

        if destination_target is not None:
            return _Mutation(
                target=destination_target,
                relative_path=edit.destination_path or edit.path,
                kind=MutationKind.MOVE,
                original=original,
                final=final,
                replacement_count=len(edit.replacements),
                source_target=source_target,
            )

        return _Mutation(
            target=source_target,
            relative_path=edit.path,
            kind=MutationKind.EDIT,
            original=original,
            final=final,
            replacement_count=len(edit.replacements),
        )

    @staticmethod
    def _resolve_replacement_anchor(
        text: str,
        old: str,
        new: str,
        expected_occurrences: int,
        relative_path: str,
        contextual: bool = False,
        end_of_file: bool = False,
    ) -> tuple[str, str]:
        """Resolve an exact anchor or a newline-equivalent fallback.

        Args:
            text: Current decoded file content.
            old: Target text anchor to locate.
            new: Replacement text content.
            expected_occurrences: Expected exact occurrence count.
            relative_path: Relative path for error diagnostics.

        Returns:
            tuple[str, str]: Resolved matching text anchor and replacement.

        Raises:
            PatchExecutionError: If anchor occurrences do not match expected count.
        """
        if contextual:
            contextual_match = FileSystemPatchEngine._resolve_contextual_anchor(
                text,
                old,
                new,
                end_of_file,
                relative_path,
            )
            if contextual_match is not None:
                return contextual_match

        exact_count = text.count(old)
        if exact_count == expected_occurrences:
            return old, new

        normalized_old = old.replace("\r\n", "\n").replace("\r", "\n")
        if "\n" not in normalized_old:
            raise PatchExecutionError(
                f"Exact occurrence guard failed for edit target: {relative_path}",
            )

        escaped_anchor = re.escape(normalized_old)
        newline_tolerant_pattern = escaped_anchor.replace("\\\n", r"(?:\r\n|\r|\n)")
        matches = tuple(re.finditer(newline_tolerant_pattern, text))

        if len(matches) != expected_occurrences:
            raise PatchExecutionError(
                f"Exact occurrence guard failed for edit target: {relative_path}",
            )

        matched_anchor = matches[0].group(0)
        matched_newline = re.search(r"\r\n|\r|\n", matched_anchor)
        newline = matched_newline.group(0) if matched_newline is not None else "\n"
        normalized_new = new.replace("\r\n", "\n").replace("\r", "\n")
        replacement_text = normalized_new.replace("\n", newline)

        return matched_anchor, replacement_text

    @staticmethod
    def _append_contextual_replacement(
        text: str,
        new: str,
        end_of_file: bool,
        relative_path: str,
    ) -> str:
        """Apply an anchorless native insertion at the start or explicit EOF."""
        newline_match = re.search(r"\r\n|\r|\n", text)
        newline = newline_match.group(0) if newline_match is not None else "\n"
        normalized_new = new.replace("\r\n", "\n").replace("\r", "\n")
        insertion = normalized_new.replace("\n", newline)

        if end_of_file:
            separator = "" if not text or text.endswith(("\r", "\n")) else newline
            return f"{text}{separator}{insertion}"

        separator = "" if not text or insertion.endswith(("\r", "\n")) else newline

        return f"{insertion}{separator}{text}"

    @staticmethod
    def _resolve_contextual_anchor(
        text: str,
        old: str,
        new: str,
        end_of_file: bool,
        relative_path: str,
    ) -> tuple[str, str] | None:
        """Resolve native line context using exact, rstrip, then strip matching."""
        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
        source_lines = normalized_text.splitlines()
        old_lines = old.split("\n")
        new_lines = new.split("\n") if new else []
        window_size = len(old_lines)

        if not window_size:
            return None

        comparisons = (
            lambda source, expected: source == expected,
            lambda source, expected: source.rstrip() == expected.rstrip(),
            lambda source, expected: source.strip() == expected.strip(),
        )
        matches: tuple[int, ...] = ()

        for comparison in comparisons:
            candidate_matches = tuple(
                start
                for start in range(len(source_lines) - window_size + 1)
                if (not end_of_file or start + window_size == len(source_lines))
                and all(
                    comparison(source_lines[start + offset], expected_line)
                    for offset, expected_line in enumerate(old_lines)
                )
            )
            if candidate_matches:
                matches = candidate_matches
                break

        if not matches:
            raise PatchExecutionError(
                f"Exact occurrence guard failed for edit target: {relative_path}",
            )

        start = matches[0]
        source_parts = normalized_text.splitlines(keepends=True)
        matched_normalized = "".join(source_parts[start : start + window_size])
        matched_lines = source_lines[start : start + window_size]
        replacement_lines = list(new_lines)
        matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)

        for old_start, new_start, length in matcher.get_matching_blocks():
            for offset in range(length):
                replacement_lines[new_start + offset] = matched_lines[old_start + offset]

        replacement_normalized = "\n".join(replacement_lines)
        if matched_normalized.endswith("\n") and replacement_lines:
            replacement_normalized += "\n"

        original_parts = text.splitlines(keepends=True)
        matched_anchor = "".join(original_parts[start : start + window_size])
        matched_offset = sum(len(part) for part in original_parts[:start])
        preserved_prefix = text[:matched_offset]
        newline_match = re.search(r"\r\n|\r|\n", matched_anchor)
        newline = newline_match.group(0) if newline_match is not None else "\n"
        replacement_text = replacement_normalized.replace("\n", newline)

        return (
            f"{preserved_prefix}{matched_anchor}",
            f"{preserved_prefix}{replacement_text}",
        )

    def _plan_create(self, create: CreateSpec) -> _Mutation:
        """Prepare one absent UTF-8 no-BOM target without writing it.

        Args:
            create: Create specification object.

        Returns:
            _Mutation: Prepared create mutation object.

        Raises:
            PatchExecutionError: If target exists or parent directory is missing.
        """
        target = self._target(create.path)
        if target.exists():
            raise PatchExecutionError(f"Create target already exists: {create.path}")
        if not target.parent.is_dir():
            raise PatchExecutionError(f"Create target parent does not exist: {create.path}")

        return _Mutation(
            target=target,
            relative_path=create.path,
            kind=MutationKind.CREATE,
            original=b"",
            final=create.content.encode("utf-8"),
            replacement_count=0,
        )

    def _plan_move(self, move: MoveSpec) -> _Mutation:
        """Prepare one file move relocation without executing it.

        Args:
            move: Move specification object.

        Returns:
            _Mutation: Prepared move mutation object.

        Raises:
            PatchExecutionError: If source missing or destination exists/invalid.
        """
        source_target = self._target(move.from_path)
        destination_target = self._target(move.to_path)

        if not source_target.exists() or not source_target.is_file():
            raise PatchExecutionError(f"Move source target does not exist: {move.from_path}")
        if destination_target.exists():
            raise PatchExecutionError(f"Move destination target already exists: {move.to_path}")
        if not destination_target.parent.is_dir():
            raise PatchExecutionError(f"Move destination parent directory does not exist: {move.to_path}")

        try:
            original = source_target.read_bytes()
        except OSError as exc:
            raise PatchExecutionError(f"Unable to read move source target: {move.from_path}") from exc

        return _Mutation(
            target=destination_target,
            relative_path=move.to_path,
            kind=MutationKind.MOVE,
            original=original,
            final=original,
            replacement_count=0,
            source_target=source_target,
        )

    def _plan_delete(self, delete: DeleteSpec) -> _Mutation:
        """Prepare one target file deletion without unlinking it.

        Args:
            delete: Delete specification object.

        Returns:
            _Mutation: Prepared delete mutation object.

        Raises:
            PatchExecutionError: If target file does not exist or cannot be read.
        """
        target = self._target(delete.path)
        if not target.exists() or not target.is_file():
            raise PatchExecutionError(f"Delete target does not exist as a regular file: {delete.path}")

        try:
            original = target.read_bytes()
        except OSError as exc:
            raise PatchExecutionError(f"Unable to read delete target: {delete.path}") from exc

        return _Mutation(
            target=target,
            relative_path=delete.path,
            kind=MutationKind.DELETE,
            original=original,
            final=b"",
            replacement_count=0,
        )

    def _validate_root(self) -> None:
        """Verify the trusted workspace root is a physical directory.

        Raises:
            PatchExecutionError: If workspace root is invalid or a reparse point.
        """
        if not self._root.exists() or not self._root.is_dir():
            raise PatchExecutionError("Workspace root does not exist as a directory.")
        if self._is_reparse(self._root):
            raise PatchExecutionError("Workspace root must not be a reparse point.")

    def _validate_transient_dir(self) -> None:
        """Verify the supplied transient directory is an existing physical directory."""
        if not self._transient_dir.exists() or not self._transient_dir.is_dir():
            raise PatchExecutionError("Transient directory must exist as a directory.")
        if self._is_reparse(self._transient_dir):
            raise PatchExecutionError("Transient directory must not be a reparse point.")

    def _target(self, declared_path: str) -> Path:
        """Confine a lexical relative target and reject reparse traversal.

        Args:
            declared_path: Relative target path string.

        Returns:
            Path: Confined physical Path object under workspace root.

        Raises:
            PatchExecutionError: If path escapes root or crosses reparse points.
        """
        normalized = declared_path.replace(chr(92), "/")
        relative = Path(normalized)

        if relative.is_absolute() or not relative.parts or Path(declared_path).drive:
            raise PatchExecutionError("Patch target path must be workspace-relative.")
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise PatchExecutionError("Patch target path must not contain traversal segments.")

        target = self._root.joinpath(*relative.parts)

        try:
            target.relative_to(self._root)
        except ValueError as exc:
            raise PatchExecutionError("Patch target path escapes the workspace root.") from exc

        current = self._root
        for part in relative.parts:
            current = current / part
            if current.exists() or current.is_symlink():
                if self._is_reparse(current):
                    raise PatchExecutionError("Patch target path crosses a reparse point.")

        return target

    def _decode(self, raw: bytes, relative_path: str) -> tuple[str, _Encoding]:
        """Strictly decode supported UTF-8 or BOM-marked UTF-16 content.

        Args:
            raw: Raw byte array from file.
            relative_path: File path for diagnostics.

        Returns:
            tuple[str, _Encoding]: Decoded string and original encoding descriptor.

        Raises:
            PatchExecutionError: If encoding is unsupported or undecodable.
        """
        if raw.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
            raise PatchExecutionError(f"Unsupported UTF-32 encoding for edit target: {relative_path}")
        if raw.startswith(b"\xef\xbb\xbf"):
            return self._decode_payload(raw[3:], "utf-8", b"\xef\xbb\xbf", relative_path)
        if raw.startswith(b"\xff\xfe"):
            return self._decode_payload(raw[2:], "utf-16-le", b"\xff\xfe", relative_path)
        if raw.startswith(b"\xfe\xff"):
            return self._decode_payload(raw[2:], "utf-16-be", b"\xfe\xff", relative_path)

        return self._decode_payload(raw, "utf-8", b"", relative_path)

    def _decode_payload(
        self,
        payload: bytes,
        codec: str,
        bom: bytes,
        relative_path: str,
    ) -> tuple[str, _Encoding]:
        """Decode one recognized source payload without lossy fallback.

        Args:
            payload: Payload bytes excluding BOM.
            codec: Python codec string name.
            bom: Original BOM bytes.
            relative_path: Relative path for diagnostics.

        Returns:
            tuple[str, _Encoding]: Decoded string and encoding descriptor.

        Raises:
            PatchExecutionError: If decoding fails.
        """
        try:
            text = payload.decode(codec, errors="strict")
        except UnicodeDecodeError as exc:
            raise PatchExecutionError(f"Unsupported or undecodable text for edit target: {relative_path}") from exc

        return text, _Encoding(codec, bom)

    def _evidence(self, mutation: _Mutation) -> FileEvidence:
        """Return source-redacted immutable evidence for one mutation.

        Args:
            mutation: Prepared mutation object.

        Returns:
            FileEvidence: Redacted verification facts.
        """
        return FileEvidence(
            path=mutation.relative_path,
            operation=mutation.kind,
            replacement_count=mutation.replacement_count,
            before_length=len(mutation.original),
            after_length=len(mutation.final),
            before_sha256=self._hash(mutation.original) if mutation.original else "",
            after_sha256=self._hash(mutation.final) if mutation.final else "",
        )

    def _commit(self, mutation: _Mutation) -> _Committed:
        """Write, fsync, verify, and atomically replace target(s).

        Args:
            mutation: Mutation object to commit to disk.

        Returns:
            _Committed: Record of committed mutation and optional backup file.

        Raises:
            OSError: If file writing, verification, or replacement fails.
            PatchExecutionError: If mutation metadata is missing.
        """
        backup: Path | None = None


        if mutation.kind is MutationKind.DELETE:
            backup = self._prepared(self._transient_dir, mutation.original, ".brain-patch-backup-")
            self._verify(backup, mutation.original)
            try:
                self._remove(mutation.target)
                return _Committed(mutation, backup)
            except OSError:
                self._remove(backup)
                raise

        if mutation.kind is MutationKind.MOVE:
            if mutation.source_target is None:
                raise PatchExecutionError("Move mutation missing source target.")
            backup = self._prepared(self._transient_dir, mutation.original, ".brain-patch-backup-")
            self._verify(backup, mutation.original)
            temporary = self._prepared(mutation.target.parent, mutation.final, ".brain-patch-")
            try:
                self._verify(temporary, mutation.final)
                self._replace(temporary, mutation.target)
                source_removed = self._remove(mutation.source_target)
                if not source_removed:
                    raise OSError("Unable to remove move source target.")
                return _Committed(mutation, backup)
            except OSError:
                self._remove(temporary)
                if mutation.source_target is not None and mutation.target.exists():
                    try:
                        self._remove(mutation.target)
                    except OSError:
                        pass
                if backup is not None and mutation.source_target is not None:
                    try:
                        self._replace_file(backup, mutation.source_target)
                        backup = None
                    except OSError:
                        pass
                if backup is not None:
                    self._remove(backup)
                raise

        temporary = self._prepared(mutation.target.parent, mutation.final, ".brain-patch-")
        try:
            self._verify(temporary, mutation.final)
            if mutation.kind is MutationKind.EDIT:
                backup = self._prepared(self._transient_dir, mutation.original, ".brain-patch-backup-")
                self._verify(backup, mutation.original)
            self._replace(temporary, mutation.target)
            return _Committed(mutation, backup)
        except OSError:
            self._remove(temporary)
            self._remove(backup)
            raise

    def _prepared(self, parent: Path, content: bytes, prefix: str) -> Path:
        """Create an exclusive directory temp and persist exact bytes.

        Args:
            parent: Parent directory for the temp file.
            content: Raw bytes to write.
            prefix: Temporary file name prefix.

        Returns:
            Path: Path to written and fsynced temporary file.

        Raises:
            OSError: If temp creation or write fails.
        """
        descriptor, name = tempfile.mkstemp(prefix=prefix, dir=parent)
        path = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
        except OSError:
            self._remove(path)
            raise

        return path

    def _verify(self, path: Path, expected: bytes) -> None:
        """Verify prepared bytes and hash before atomic replacement.

        Args:
            path: File path to inspect.
            expected: Expected byte content.

        Raises:
            OSError: If byte length or hash mismatch occur.
        """
        observed = path.read_bytes()
        if len(observed) != len(expected) or self._hash(observed) != self._hash(expected):
            raise OSError("Prepared patch bytes failed verification.")

    def _rollback(self, committed: list[_Committed]) -> str:
        """Best-effort restore earlier commits after a later failure.

        Args:
            committed: List of committed mutations to revert.

        Returns:
            str: "completed" if all rollbacks succeed, else "failed".
        """
        failed = False
        for record in reversed(committed):
            try:
                if record.mutation.kind is MutationKind.CREATE:
                    if not self._remove(record.mutation.target):
                        failed = True
                elif record.mutation.kind is MutationKind.DELETE:
                    if record.backup is not None:
                        self._replace_file(record.backup, record.mutation.target)
                    else:
                        failed = True
                elif record.mutation.kind is MutationKind.MOVE:
                    if record.backup is not None and record.mutation.source_target is not None:
                        self._replace_file(record.backup, record.mutation.source_target)
                        self._remove(record.mutation.target)
                    else:
                        failed = True
                elif record.backup is not None:
                    self._replace_file(record.backup, record.mutation.target)
            except OSError:
                failed = True

        return "failed" if failed else "completed"

    def _replace_file(self, source: Path, destination: Path) -> None:
        """Execute file replacement using standard os.replace for rollbacks.

        Args:
            source: Source file path.
            destination: Destination file path.
        """
        os.replace(source, destination)

    def _cleanup(self, committed: list[_Committed]) -> str:
        """Remove retained backups after successful application or rollback.

        Args:
            committed: List of committed mutations containing backups.

        Returns:
            str: "completed" if all cleanups succeed, else "failed".
        """
        failed = False

        for record in committed:
            if record.backup is not None:
                if not self._remove(record.backup):
                    failed = True

        return "failed" if failed else "completed"

    @staticmethod
    def _is_reparse(path: Path) -> bool:
        """Return whether an existing path redirects physical traversal.

        Args:
            path: Path object to inspect.

        Returns:
            bool: True if symlink, junction, or reparse point.
        """
        try:
            metadata = path.lstat()
        except OSError:
            return True

        attributes = getattr(metadata, "st_file_attributes", 0)
        flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

        return stat.S_ISLNK(metadata.st_mode) or bool(attributes & flag)

    @staticmethod
    def _remove(path: Path | None) -> bool:
        """Remove one owned temporary, backup, or rollback create path.

        Args:
            path: Optional path to delete.

        Returns:
            bool: True if path was successfully deleted or was None.
        """
        if path is None:
            return True

        try:
            path.unlink(missing_ok=True)
        except OSError:
            return False

        return True

    @staticmethod
    def _hash(content: bytes) -> str:
        """Return the stable SHA-256 hex digest for bytes.

        Args:
            content: Raw byte string to hash.

        Returns:
            str: Hexadecimal SHA-256 digest string.
        """
        return hashlib.sha256(content).hexdigest()
