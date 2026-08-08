"""Execute the typed, guarded Python patching vertical through Brain."""

from __future__ import annotations

import argparse
import sys

from brain.application.patching.models import FileEvidence, PatchResult
from brain.application.patching.specification import PatchSpecificationError, parse_patch_request
from brain.infrastructure.patching.filesystem_patch_engine import FileSystemPatchEngine, PatchExecutionError
from brain.infrastructure.runtime.paths import get_workspace_root
from brain.presentation.terminal import log_step


COMMAND_NAME = "apply-patch"


def handle(args: argparse.Namespace) -> int:
    """Validate and apply one stdin-provided exact-text patch specification.

    Args:
        args: Parsed check-only and output options.

    Returns:
        int: Zero when planning succeeds and, unless check-only, all commits complete.
    """
    specification = sys.stdin.read()
    try:
        request = parse_patch_request(specification)
        engine = FileSystemPatchEngine(root=get_workspace_root())
        log_step(args, "Planning confined exact patch anchors...")
        result = engine.execute(request=request, check=bool(args.check))
    except (PatchSpecificationError, PatchExecutionError) as exc:
        return _fail(
            args,
            str(exc),
            getattr(exc, "evidence", ()),
            getattr(exc, "rollback", "not-needed"),
            getattr(exc, "cleanup", "not-needed"),
            getattr(exc, "recovery_artifacts", ()),
        )
    payload = _result_payload(result)
    args.json_payload = payload
    if not getattr(args, "json", False):
        status = "CHECK PASSED" if result.check else "PATCH APPLIED"
        print(f"{status}: {len(result.files)} file(s).")
    return 0


def _result_payload(result: PatchResult) -> dict[str, object]:
    """Build the minimal semantic success payload.

    Args:
        result: Immutable engine result.

    Returns:
        dict[str, object]: Compact operation mode and affected-file facts.
    """
    return {
        "ok": True,
        "command": COMMAND_NAME,
        "mode": "check" if result.check else "apply",
        "files": tuple(_evidence_payload(item) for item in result.files),
    }


def _evidence_payload(evidence: FileEvidence) -> dict[str, object]:
    """Serialize only actionable facts for one affected file.

    Args:
        evidence: Immutable internal verification evidence.

    Returns:
        dict[str, object]: Path, operation, and edit count when applicable.
    """
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
    evidence: tuple[FileEvidence, ...],
    rollback: str,
    cleanup: str = "not-needed",
    recovery_artifacts: tuple[str, ...] = (),
) -> int:
    """Expose one source-redacted guarded patch failure consistently.

    Args:
        args: Parsed namespace receiving JSON output.
        message: Concrete failure explanation without source fragments.
        evidence: Prepared redacted evidence available before failure.
        rollback: Rollback state after a commit failure.
        cleanup: Status of post-commit artifact cleanup.
        recovery_artifacts: Retained recovery artifact identifiers.

    Returns:
        int: Stable non-zero command exit code.
    """
    payload: dict[str, object] = {
        "ok": False,
        "command": COMMAND_NAME,
        "error": message,
    }
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
