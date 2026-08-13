"""Safe subprocess execution over in-memory input."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import ClassVar

from ..domain.models import CommandResult, CommandSpec, EvaluationStatus, Evidence


@dataclass(frozen=True, slots=True)
class _Capture:
    """Hold immutable subprocess output captured entirely in memory.

    Attributes:
        stdout: Raw standard-output bytes returned by the child process.
        stderr: Raw standard-error bytes returned by the child process.
        exit_code: Process exit code, or ``-1`` for a timeout.
    """

    stdout: bytes
    stderr: bytes
    exit_code: int


class InMemoryCommandRunner:
    """Run allowlisted commands without filesystem, cwd, or environment overrides."""

    _ALLOWED: ClassVar[frozenset[str]] = frozenset({"ruff", "node", "py"})

    def run(
        self,
        spec: CommandSpec,
        *,
        stdin: str = "",
        expected_exit_code: int | None = None,
        evidence_path: str = "<memory>",
    ) -> CommandResult:
        """Run one allowlisted command with stdin and redacted output metadata.

        Args:
            spec: Immutable command identity, arguments, timeout, and retry policy.
            stdin: Complete input text sent through standard input.
            expected_exit_code: Optional exit-code override for this invocation.
            evidence_path: Relative logical path attached to redacted evidence.

        Returns:
            CommandResult: Immutable status, digest, length, and evidence metadata.

        Raises:
            AssertionError: If an internal retry path completes without capture.
        """

        command = tuple(spec.argv)
        accepted_exit_code = (
            spec.expected_exit_code
            if expected_exit_code is None
            else expected_exit_code
        )

        if not command or command[0].lower() not in self._ALLOWED:
            return self._blocked(command, evidence_path, "unsupported executable")

        if any(token in {"/c", "-c", "--command", "--shell"} for token in command[1:]):
            return self._blocked(command, evidence_path, "shell execution is forbidden")

        if shutil.which(command[0]) is None:
            return self._blocked(command, evidence_path, "executable not found")

        attempts = max(1, spec.retry.max_attempts)
        capture: _Capture | None = None
        status = EvaluationStatus.ERROR

        for attempt in range(attempts):
            try:
                completed = subprocess.run(
                    command,
                    input=stdin,
                    text=True,
                    capture_output=True,
                    shell=False,
                    timeout=spec.timeout,
                    check=False,
                )
                capture = _Capture(
                    completed.stdout.encode(),
                    completed.stderr.encode(),
                    completed.returncode,
                )
                status = (
                    EvaluationStatus.PASS
                    if completed.returncode == accepted_exit_code
                    else EvaluationStatus.FAIL
                )

            except subprocess.TimeoutExpired as error:
                stdout = error.stdout or b""
                stderr = error.stderr or b""
                capture = _Capture(
                    stdout.encode() if isinstance(stdout, str) else stdout,
                    stderr.encode() if isinstance(stderr, str) else stderr,
                    -1,
                )
                status = EvaluationStatus.ERROR

            except OSError:
                if attempt == attempts - 1:
                    return self._blocked(command, evidence_path, "execution failed")

                status = EvaluationStatus.ERROR
                continue

            if (
                status in {EvaluationStatus.PASS, EvaluationStatus.FAIL}
                or attempt == attempts - 1
            ):
                break

            if spec.retry.backoff_seconds > 0:
                time.sleep(spec.retry.backoff_seconds)

        assert capture is not None

        return CommandResult(
            command_id=spec.id,
            status=status,
            exit_code=capture.exit_code,
            stdout_length=len(capture.stdout),
            stdout_digest=hashlib.sha256(capture.stdout).hexdigest(),
            stderr_length=len(capture.stderr),
            stderr_digest=hashlib.sha256(capture.stderr).hexdigest(),
            evidence=(
                Evidence(
                    path=evidence_path,
                    line_start=None,
                    line_end=None,
                    kind="command",
                    summary=status.value,
                ),
            ),
        )

    @staticmethod
    def _blocked(command: tuple[str, ...], path: str, summary: str) -> CommandResult:
        """Return a redacted blocked result for an unavailable command.

        Args:
            command: Immutable executable argument vector that was rejected.
            path: Relative logical path attached to the evidence record.
            summary: Redacted reason explaining why execution was blocked.

        Returns:
            CommandResult: Immutable blocked status with no process output.
        """

        command_id = command[0] if command else "blocked-command"

        return CommandResult(
            command_id=command_id,
            status=EvaluationStatus.BLOCKED,
            evidence=(
                Evidence(
                    path=path,
                    line_start=None,
                    line_end=None,
                    kind="command",
                    summary=summary,
                ),
            ),
        )
