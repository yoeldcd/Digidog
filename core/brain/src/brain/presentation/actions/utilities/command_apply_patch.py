"""Adapt Brain CLI input and output to the Core text-patch facade."""

from __future__ import annotations

import argparse
import sys
from typing import Protocol

from brain.infrastructure.runtime.paths import get_transient_dir, get_workspace_root
from utilities.apply_text_patch.src.facade import (
    NativePatchSpecificationError,
    PatchExecutionError,
    PatchInputFormat,
    PatchInputFormatError,
    PatchResult,
    PatchSpecificationError,
    apply_text_patch,
)


COMMAND_NAME = "apply-patch"


class _FileEvidence(Protocol):
    """Expose the redacted evidence fields rendered by Brain."""

    path: str
    operation: object
    replacement_count: int


def handle(args: argparse.Namespace) -> int:
    """Read stdin, delegate execution to Core, and preserve Brain payloads."""
    specification = sys.stdin.read()

    try:
        input_format = PatchInputFormat(getattr(args, "format", "json"))
    except ValueError:
        return _fail(args, "Unsupported patch input format.")

    try:
        result = apply_text_patch(
            serialized_specification=specification,
            workspace_root=get_workspace_root(),
            transient_dir=get_transient_dir(),
            check=bool(args.check),
            input_format=input_format,
        )
    except (
        PatchSpecificationError,
        NativePatchSpecificationError,
        PatchInputFormatError,
        PatchExecutionError,
    ) as exc:
        return _fail(
            args,
            str(exc),
            getattr(exc, "evidence", ()),
            getattr(exc, "rollback", "not-needed"),
            getattr(exc, "cleanup", "not-needed"),
            getattr(exc, "recovery_artifacts", ()),
        )

    args.json_payload = _result_payload(result)
    if not getattr(args, "json", False):
        status = "CHECK PASSED" if result.check else "PATCH APPLIED"
        print(f"{status}: {len(result.files)} file(s).")
    return 0


def _result_payload(result: PatchResult) -> dict[str, object]:
    """Build the compact semantic success payload."""
    return {
        "ok": True,
        "command": COMMAND_NAME,
        "mode": "check" if result.check else "apply",
        "files": tuple(_evidence_payload(item) for item in result.files),
    }


def _evidence_payload(evidence: _FileEvidence) -> dict[str, object]:
    """Serialize actionable facts for one affected file."""
    payload: dict[str, object] = {
        "path": evidence.path,
        "operation": evidence.operation.value,
    }
    if evidence.replacement_count:
        payload["replacements"] = evidence.replacement_count
    return payload


def _fail(
    args: argparse.Namespace,
    message: str,
    evidence: tuple[_FileEvidence, ...] = (),
    rollback: str = "not-needed",
    cleanup: str = "not-needed",
    recovery_artifacts: tuple[str, ...] = (),
) -> int:
    """Expose one source-redacted guarded patch failure consistently."""
    payload: dict[str, object] = {"ok": False, "command": COMMAND_NAME, "error": message}
    if evidence:
        payload["files"] = tuple(_evidence_payload(item) for item in evidence)
    if rollback != "not-needed":
        payload["rollback"] = rollback
    if cleanup not in {"not-needed", "completed"}:
        payload["cleanup"] = cleanup
    if recovery_artifacts:
        payload["recoveryArtifacts"] = recovery_artifacts
    args.json_payload = payload
    if not getattr(args, "json", False):
        print(f"Error: {message}", file=sys.stderr)
    return 1
