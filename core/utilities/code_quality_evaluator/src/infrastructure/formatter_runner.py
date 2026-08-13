"""Run trusted formatters over source held only in memory."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar

from ..domain.models import (
    CommandResult,
    EvaluationStatus,
    Evidence,
    FormatterSpec,
    Language,
)


@dataclass(frozen=True, slots=True)
class FormattedCandidate:
    """Represent one immutable in-memory formatter outcome.

    Attributes:
        status: Outcome of the formatter invocation.
        candidate: Formatted source, retained only in process memory.
        candidate_length: UTF-8 byte length of the formatted source.
        candidate_digest: SHA-256 digest of the formatted source.
        command_result: Source-redacted command execution metadata.
    """

    status: EvaluationStatus
    candidate: str | None
    candidate_length: int
    candidate_digest: str | None
    command_result: CommandResult


class InMemoryFormatterRunner:
    """Execute allowlisted Ruff and Prettier commands through standard input."""

    _PRETTIER_PARSERS: ClassVar[Mapping[Language, str]] = MappingProxyType(
        {
            Language.JAVASCRIPT: "babel",
            Language.TYPESCRIPT: "typescript",
            Language.JSON: "json",
            Language.MARKDOWN: "markdown",
        }
    )
    _UTILITY_ROOT: ClassVar[Path] = Path(__file__).resolve().parents[2]
    _PRETTIER_ENTRYPOINT: ClassVar[Path] = (
        _UTILITY_ROOT / "node_modules" / "prettier" / "bin" / "prettier.cjs"
    )

    def run(
        self,
        spec: FormatterSpec,
        *,
        source: str,
        path: str = "<memory>",
    ) -> FormattedCandidate:
        """Format source through stdin without creating or changing a file.

        Args:
            spec: Immutable formatter identity, language, timeout, and retry policy.
            source: Complete source text held in memory.
            path: Logical relative path used only for language-aware parsing.

        Returns:
            FormattedCandidate: Immutable candidate and redacted execution metadata.
        """

        command = self._build_command(spec, path)

        if command is None:
            return self._blocked(spec, path, "unsupported formatter")

        if shutil.which(command[0]) is None:
            return self._blocked(spec, path, "formatter executable unavailable")

        attempts = spec.command.retry.max_attempts
        completed: subprocess.CompletedProcess[str] | None = None

        for attempt_index in range(attempts):
            try:
                completed = subprocess.run(
                    command,
                    input=source,
                    text=True,
                    capture_output=True,
                    shell=False,
                    timeout=spec.command.timeout,
                    check=False,
                )

            except (OSError, subprocess.TimeoutExpired):
                if attempt_index + 1 == attempts:
                    return self._blocked(spec, path, "formatter execution unavailable")

                continue

            break

        if completed is None:
            return self._blocked(spec, path, "formatter execution unavailable")

        status = (
            EvaluationStatus.PASS
            if completed.returncode == spec.command.expected_exit_code
            else EvaluationStatus.FAIL
        )
        candidate = completed.stdout if status is EvaluationStatus.PASS else None

        return self._candidate(
            spec=spec,
            path=path,
            status=status,
            candidate=candidate,
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )

    def _build_command(
        self,
        spec: FormatterSpec,
        path: str,
    ) -> tuple[str, ...] | None:
        """Build a fixed formatter command for one supported language.

        Args:
            spec: Immutable formatter selection.
            path: Logical path supplied to the formatter parser.

        Returns:
            tuple[str, ...] | None: Safe argv tuple, or none when unsupported.
        """

        requested = spec.command.argv[0] if spec.command.argv else ""

        if spec.language is Language.PYTHON and requested == "ruff":
            return (
                "py",
                "-m",
                "ruff",
                "format",
                "--stdin-filename",
                path,
                "--isolated",
                "--no-cache",
                "-",
            )

        parser = self._PRETTIER_PARSERS.get(spec.language)

        if (
            parser is None
            or requested != "node"
            or not self._PRETTIER_ENTRYPOINT.is_file()
        ):
            return None

        return (
            "node",
            str(self._PRETTIER_ENTRYPOINT),
            "--stdin-filepath",
            path,
            "--parser",
            parser,
            "--no-config",
            "--no-editorconfig",
        )

    @staticmethod
    def _candidate(
        *,
        spec: FormatterSpec,
        path: str,
        status: EvaluationStatus,
        candidate: str | None,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> FormattedCandidate:
        """Build candidate and digest-only command evidence.

        Args:
            spec: Formatter specification that owns the command identity.
            path: Logical source path.
            status: Formatter execution status.
            candidate: Formatted text when execution passed.
            stdout: Captured standard output used only for metadata.
            stderr: Captured standard error used only for metadata.
            exit_code: Process exit code.

        Returns:
            FormattedCandidate: Immutable in-memory formatter outcome.
        """

        stdout_bytes = stdout.encode("utf-8")
        stderr_bytes = stderr.encode("utf-8")
        candidate_bytes = candidate.encode("utf-8") if candidate is not None else b""
        command_result = CommandResult(
            command_id=spec.command.id,
            status=status,
            exit_code=exit_code,
            stdout_length=len(stdout_bytes),
            stdout_digest=hashlib.sha256(stdout_bytes).hexdigest(),
            stderr_length=len(stderr_bytes),
            stderr_digest=hashlib.sha256(stderr_bytes).hexdigest(),
            evidence=(
                Evidence(
                    path=path,
                    kind="formatter",
                    summary=status.value,
                ),
            ),
        )

        return FormattedCandidate(
            status=status,
            candidate=candidate,
            candidate_length=len(candidate_bytes),
            candidate_digest=(
                hashlib.sha256(candidate_bytes).hexdigest()
                if candidate is not None
                else None
            ),
            command_result=command_result,
        )

    @staticmethod
    def _blocked(
        spec: FormatterSpec,
        path: str,
        summary: str,
    ) -> FormattedCandidate:
        """Build a blocked result without exposing command or source content.

        Args:
            spec: Formatter specification that owns the command identity.
            path: Logical source path.
            summary: Bounded non-sensitive failure classification.

        Returns:
            FormattedCandidate: Blocked result without a candidate.
        """

        command_result = CommandResult(
            command_id=spec.command.id,
            status=EvaluationStatus.BLOCKED,
            evidence=(
                Evidence(
                    path=path,
                    kind="formatter",
                    summary=summary,
                ),
            ),
        )

        return FormattedCandidate(
            status=EvaluationStatus.BLOCKED,
            candidate=None,
            candidate_length=0,
            candidate_digest=None,
            command_result=command_result,
        )
