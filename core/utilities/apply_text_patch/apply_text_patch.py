"""Command-line launcher for the guarded text patch utility.

This module acts as the standalone CLI entrypoint for `apply_text_patch`,
parsing arguments, reading standard input, invoking the in-process Core
facade, and outputting formatted results or errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol


UTILITY_ROOT: Final[Path] = Path(__file__).resolve().parent
"""Physical root directory containing this utility."""

COMMAND_NAME: Final[str] = "apply-patch"
"""Canonical command name used in help strings and output payloads."""


class _PatchResult(Protocol):
    """Describe the result fields consumed by the launcher."""

    check: bool
    files: Sequence[_PatchEvidence]


class _Operation(Protocol):
    """Describe the operation enum value consumed by the launcher."""

    value: str


class _PatchEvidence(Protocol):
    """Describe file evidence fields consumed by the launcher."""

    path: str
    operation: _Operation
    replacement_count: int


class _InputFormat(Protocol):
    """Describe one input-format enum member consumed by the facade."""

    value: str


class _InputFormatType(Protocol):
    """Describe the runtime input-format enum loaded with the facade."""

    JSON: _InputFormat
    NATIVE: _InputFormat
    AUTO: _InputFormat

    def __call__(self, value: str) -> _InputFormat:
        """Resolve an enum member from its command-line value.

        Args:
            value: Raw format name from CLI arguments.

        Returns:
            _InputFormat: Resolved format enum instance.
        """


class _ApplyTextPatch(Protocol):
    """Describe the facade callable loaded at runtime."""

    def __call__(
        self,
        *,
        serialized_specification: str,
        workspace_root: Path,
        check: bool,
        input_format: _InputFormat,
    ) -> _PatchResult:
        """Execute a serialized patch request.

        Args:
            serialized_specification: Complete patch content from stdin.
            workspace_root: Physical root confining all mutations.
            check: Whether to plan without filesystem writes.
            input_format: Input format enum instance.

        Returns:
            _PatchResult: Immutable execution evidence.
        """


@dataclass(frozen=True, slots=True)
class _FacadeBindings:
    """Hold immutable runtime bindings imported from the relocatable facade.

    Attributes:
        apply_text_patch: Facade callable that executes a patch specification.
        input_format_type: Enum type used to resolve the selected input format.
        recognized_errors: Exception types rendered as normal CLI failures.
    """

    apply_text_patch: _ApplyTextPatch
    input_format_type: _InputFormatType
    recognized_errors: tuple[type[Exception], ...]


def _load_facade() -> _FacadeBindings:
    """Load the facade after bootstrapping the relocatable utility root.

    Returns:
        _FacadeBindings: Immutable execution and error bindings.
    """
    
    root_text = str(UTILITY_ROOT)

    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    from src.facade import (
        NativePatchSpecificationError,
        PatchExecutionError,
        PatchInputFormat,
        PatchInputFormatError,
        PatchSpecificationError,
        apply_text_patch,
    )

    recognized_errors = (
        PatchExecutionError,
        PatchSpecificationError,
        NativePatchSpecificationError,
        PatchInputFormatError,
    )

    return _FacadeBindings(
        apply_text_patch=apply_text_patch,
        input_format_type=PatchInputFormat,
        recognized_errors=recognized_errors,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for supported launcher flags.

    Returns:
        argparse.ArgumentParser: Configured argument parser instance.
    """
    
    parser = argparse.ArgumentParser(prog=COMMAND_NAME)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate and plan operations without writing files to disk.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON payload to stdout.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "native", "auto"),
        default="json",
        help="Input specification format (json, native, or auto; default: json).",
    )

    return parser


def _file_payload(evidence: _PatchEvidence) -> dict[str, object]:
    """Convert one facade evidence object into the compact output shape.

    Args:
        evidence: Immutable file evidence from the execution result.

    Returns:
        dict[str, object]: Compact path, operation, and replacement count dict.
    """
    
    payload: dict[str, object] = {
        "path": evidence.path,
        "operation": evidence.operation.value,
    }

    if evidence.replacement_count:
        payload["replacements"] = evidence.replacement_count

    return payload


def _result_payload(result: _PatchResult) -> dict[str, object]:
    """Build the successful JSON payload without exposing source material.

    Args:
        result: Immutable execution evidence returned by the facade.

    Returns:
        dict[str, object]: Complete structured success response dict.
    """
    
    files = [_file_payload(evidence) for evidence in result.files]

    return {
        "ok": True,
        "command": COMMAND_NAME,
        "mode": "check" if result.check else "apply",
        "files": files,
    }


def _error_payload(error: Exception) -> dict[str, object]:
    """Build a compact failure payload without exposing internal patch details.

    Args:
        error: Exception raised during execution.

    Returns:
        dict[str, object]: Structured failure response dict.
    """
    
    payload: dict[str, object] = {
        "ok": False,
        "command": COMMAND_NAME,
        "error": str(error),
    }
    evidence = getattr(error, "evidence", ())

    if evidence:
        payload["files"] = [_file_payload(item) for item in evidence]

    rollback = getattr(error, "rollback", None)

    if rollback not in (None, "not-needed"):
        payload["rollback"] = rollback

    cleanup = getattr(error, "cleanup", None)

    if cleanup not in (None, "not-needed", "completed"):
        payload["cleanup"] = cleanup

    recovery_artifacts = getattr(error, "recovery_artifacts", ())

    if recovery_artifacts:
        payload["recoveryArtifacts"] = list(recovery_artifacts)

    return payload


def _render_failure(error: Exception, as_json: bool) -> None:
    """Render one failure to JSON stdout or human-readable stderr.

    Args:
        error: Exception instance representing the failure.
        as_json: Whether JSON output format was requested.
    """
    
    if as_json:
        print(json.dumps(_error_payload(error), separators=(",", ":")))

        return

    print(f"Error: {error}", file=sys.stderr)


def _render_success(result: _PatchResult, as_json: bool) -> None:
    """Render one successful result to JSON stdout or human-readable stdout.

    Args:
        result: Execution result instance.
        as_json: Whether JSON output format was requested.
    """

    if as_json:
        print(json.dumps(_result_payload(result), separators=(",", ":")))

        return

    file_count = len(result.files)
    label = "CHECK PASSED" if result.check else "PATCH APPLIED"
    print(f"{label}: {file_count} file(s).")


def main(argv: Sequence[str] | None = None) -> int:
    """Execute stdin specification and emit the launcher output contract.

    Args:
        argv: Optional command-line arguments; defaults to process arguments.

    Returns:
        int: Zero for success, one for a recognized patch failure.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    serialized = sys.stdin.read()
    facade = _load_facade()
    from src.runtime.transient_paths import resolve_transient_dir
    input_format = facade.input_format_type(args.format)

    try:
        result = facade.apply_text_patch(
            serialized_specification=serialized,
            workspace_root=Path.cwd(),
            check=args.check,
            input_format=input_format,
            transient_dir=resolve_transient_dir(Path.cwd(), UTILITY_ROOT.parents[1]),
        )
    except facade.recognized_errors as error:
        _render_failure(error, args.json)

        return 1

    _render_success(result, args.json)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
