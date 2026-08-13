"""Run the PowerShell language parser against source held in memory."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Final

from ..domain.models import EvaluationStatus


@dataclass(frozen=True, slots=True)
class PowerShellSyntaxError:
    """Describe one parser error without retaining source text.

    Attributes:
        line: One-based source line containing the parser error.
        column: One-based source column containing the parser error.
    """

    line: int
    column: int


@dataclass(frozen=True, slots=True)
class PowerShellParseSummary:
    """Capture bounded PowerShell parser and layout facts.

    Attributes:
        syntax_errors: Parser errors reduced to line and column coordinates.
        token_count: Number of tokens produced by ``Parser.ParseInput``.
        token_kinds: Token kind names, bounded to avoid untrusted growth.
        token_lines: One-based lines for the retained token kinds.
        statement_lines: Lines containing statement AST nodes.
        pipeline_lines: Lines containing pipeline AST nodes.
        semicolon_lines: Lines containing semicolon tokens.
        clause_kinds: Native clause AST type names and their source lines.
        clause_lines: One-based start lines for native clause AST nodes.
        clause_end_lines: End lines for native clause AST nodes.
        function_lines: Lines where function declarations begin.
        class_lines: Lines where class declarations begin.
        comment_help_lines: Lines containing comment-based help markers.
    """

    syntax_errors: tuple[PowerShellSyntaxError, ...]
    token_count: int
    token_kinds: tuple[str, ...]
    token_lines: tuple[int, ...]
    statement_lines: tuple[int, ...]
    pipeline_lines: tuple[int, ...]
    semicolon_lines: tuple[int, ...]
    clause_kinds: tuple[str, ...]
    clause_lines: tuple[int, ...]
    clause_end_lines: tuple[int, ...]
    function_lines: tuple[int, ...]
    class_lines: tuple[int, ...]
    comment_help_lines: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PowerShellRunnerResult:
    """Return parser execution status and an optional redacted summary.

    Attributes:
        status: PASS when the parser returned a valid JSON summary, otherwise BLOCKED.
        summary: Bounded parse facts, or ``None`` when execution was unavailable.
        stdout_length: UTF-8 byte length of captured parser output.
        stdout_digest: Digest of captured parser output for diagnostics only.
        stderr_length: UTF-8 byte length of captured parser error output.
        stderr_digest: Digest of captured parser error output for diagnostics only.
        message: Non-sensitive execution classification.
    """

    status: EvaluationStatus
    summary: PowerShellParseSummary | None
    stdout_length: int
    stdout_digest: str | None
    stderr_length: int
    stderr_digest: str | None
    message: str


_MAX_OUTPUT_BYTES: Final[int] = 65536
_PARSER_SCRIPT: Final[str] = r"""
$source = [Console]::In.ReadToEnd()
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput(
    $source,
    [ref]$tokens,
    [ref]$errors
)
$tokenValues = @($tokens)
$errorValues = @($errors)
$statementValues = @($ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.StatementAst]
}, $true))
$pipelineValues = @($ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.PipelineAst]
}, $true))
$clauseValues = @($ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.IfStatementAst] -or
    $node -is [System.Management.Automation.Language.ForStatementAst] -or
    $node -is [System.Management.Automation.Language.ForeachStatementAst] -or
    $node -is [System.Management.Automation.Language.WhileStatementAst] -or
    $node -is [System.Management.Automation.Language.DoWhileStatementAst] -or
    $node -is [System.Management.Automation.Language.DoUntilStatementAst] -or
    $node -is [System.Management.Automation.Language.TryStatementAst] -or
    $node -is [System.Management.Automation.Language.SwitchStatementAst]
}, $true))
$functionValues = @($ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst]
}, $true))
$classValues = @($ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.TypeDefinitionAst]
}, $true))
$helpValues = @($tokenValues | Where-Object {
    $_.Kind.ToString() -eq 'Comment' -and (
        $_.Extent.Text -match '^\s*#\.' -or
        $_.Extent.Text -match '^\s*<#'
    )
})
$summary = [pscustomobject]@{
    syntax_errors = @($errorValues | ForEach-Object {
        [pscustomobject]@{
            line = $_.Extent.StartLineNumber
            column = $_.Extent.StartColumnNumber
        }
    })
    token_count = $tokenValues.Count
    token_kinds = @($tokenValues | Select-Object -First 2048 | ForEach-Object { $_.Kind.ToString() })
    token_lines = @($tokenValues | Select-Object -First 2048 | ForEach-Object { $_.Extent.StartLineNumber })
    statement_lines = @($statementValues | Select-Object -First 2048 | ForEach-Object { $_.Extent.StartLineNumber })
    pipeline_lines = @($pipelineValues | Select-Object -First 2048 | ForEach-Object { $_.Extent.StartLineNumber })
    semicolon_lines = @(
        $tokenValues |
        Where-Object { $_.Kind.ToString() -eq 'Semi' } |
        Select-Object -First 2048 |
        ForEach-Object { $_.Extent.StartLineNumber }
    )
    clause_kinds = @($clauseValues | Select-Object -First 512 | ForEach-Object { $_.GetType().Name })
    clause_lines = @($clauseValues | Select-Object -First 512 | ForEach-Object { $_.Extent.StartLineNumber })
    clause_end_lines = @($clauseValues | Select-Object -First 512 | ForEach-Object { $_.Extent.EndLineNumber })
    function_lines = @($functionValues | Select-Object -First 512 | ForEach-Object { $_.Extent.StartLineNumber })
    class_lines = @($classValues | Select-Object -First 512 | ForEach-Object { $_.Extent.StartLineNumber })
    comment_help_lines = @($helpValues | Select-Object -First 512 | ForEach-Object { $_.Extent.StartLineNumber })
}
$summary | ConvertTo-Json -Compress -Depth 8
"""


class PowerShellParserRunner:
    """Invoke a fixed ``Parser.ParseInput`` command through standard input."""

    def __init__(
        self,
        executable: str = "pwsh",
        timeout_seconds: float = 10.0,
        max_output_bytes: int = _MAX_OUTPUT_BYTES,
    ) -> None:
        """Configure executable lookup and bounded execution limits.

        Args:
            executable: PowerShell executable name or absolute path.
            timeout_seconds: Maximum parser process duration.
            max_output_bytes: Maximum accepted JSON summary size.
        """
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max(1024, max_output_bytes)

    def run(self, source: str) -> PowerShellRunnerResult:
        """Parse source through stdin without writing files or exposing source text.

        Args:
            source: Complete PowerShell source held in memory.

        Returns:
            PowerShellRunnerResult: Redacted parser outcome and bounded summary.
        """

        if shutil.which(self._executable) is None:
            return self._blocked("PowerShell executable unavailable")

        command = (
            self._executable,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _PARSER_SCRIPT,
        )

        try:
            completed = subprocess.run(
                command,
                input=source,
                text=True,
                capture_output=True,
                shell=False,
                timeout=self._timeout_seconds,
                check=False,
            )

        except subprocess.TimeoutExpired:
            return self._blocked("PowerShell parser timed out")

        except OSError:
            return self._blocked("PowerShell parser execution unavailable")

        stdout_bytes = completed.stdout.encode("utf-8", errors="replace")
        stderr_bytes = completed.stderr.encode("utf-8", errors="replace")
        metadata = {
            "stdout_length": len(stdout_bytes),
            "stdout_digest": hashlib.sha256(stdout_bytes).hexdigest(),
            "stderr_length": len(stderr_bytes),
            "stderr_digest": hashlib.sha256(stderr_bytes).hexdigest(),
        }

        if len(stdout_bytes) > self._max_output_bytes:
            return PowerShellRunnerResult(
                status=EvaluationStatus.BLOCKED,
                summary=None,
                message="PowerShell parser summary exceeded output limit",
                **metadata,
            )

        try:
            payload = json.loads(completed.stdout)
            summary = _summary_from_payload(payload)

        except (TypeError, ValueError, json.JSONDecodeError):
            return PowerShellRunnerResult(
                status=EvaluationStatus.BLOCKED,
                summary=None,
                message="PowerShell parser returned an invalid summary",
                **metadata,
            )

        if completed.returncode != 0:
            return PowerShellRunnerResult(
                status=EvaluationStatus.BLOCKED,
                summary=None,
                message="PowerShell parser process failed",
                **metadata,
            )

        return PowerShellRunnerResult(
            status=EvaluationStatus.PASS,
            summary=summary,
            message="PowerShell parser completed",
            **metadata,
        )

    def _blocked(self, message: str) -> PowerShellRunnerResult:
        """Build a bounded blocked result without process or source details.

        Args:
            message: Safe execution classification.

        Returns:
            PowerShellRunnerResult: Blocked result with no parse payload.
        """

        return PowerShellRunnerResult(
            status=EvaluationStatus.BLOCKED,
            summary=None,
            stdout_length=0,
            stdout_digest=None,
            stderr_length=0,
            stderr_digest=None,
            message=message,
        )


def _bounded_ints(value: object, limit: int = 2048) -> tuple[int, ...]:
    """Normalize a JSON array of line numbers to bounded integers.

    Args:
        value: Untrusted JSON value expected to contain integer line numbers.
        limit: Maximum number of integers retained.

    Returns:
        tuple[int, ...]: Non-negative bounded one-based line numbers.
    """

    if not isinstance(value, list):
        return ()

    return tuple(item for item in value[:limit] if isinstance(item, int) and item >= 1)


def _bounded_strings(value: object, limit: int = 2048) -> tuple[str, ...]:
    """Normalize a JSON array of strings to bounded values.

    Args:
        value: Untrusted JSON value expected to contain strings.
        limit: Maximum number of strings retained.

    Returns:
        tuple[str, ...]: Bounded strings no longer than 128 characters.
    """

    if not isinstance(value, list):
        return ()

    return tuple(
        item for item in value[:limit] if isinstance(item, str) and len(item) <= 128
    )


def _summary_from_payload(payload: object) -> PowerShellParseSummary:
    """Convert untrusted runner JSON into an immutable bounded summary.

    Args:
        payload: Parsed JSON object emitted by the fixed PowerShell script.

    Returns:
        PowerShellParseSummary: Validated, source-redacted parser facts.

    Raises:
        TypeError: If the parser payload is not a JSON object.
    """

    if not isinstance(payload, dict):
        raise TypeError("parser summary must be an object")

    raw_errors = payload.get("syntax_errors", [])
    errors: list[PowerShellSyntaxError] = []

    if isinstance(raw_errors, list):
        for item in raw_errors[:512]:
            if not isinstance(item, dict):
                continue
            line = item.get("line")
            column = item.get("column")

            if (
                isinstance(line, int)
                and isinstance(column, int)
                and line >= 1
                and column >= 1
            ):
                errors.append(PowerShellSyntaxError(line=line, column=column))

    token_kinds = _bounded_strings(payload.get("token_kinds"))
    token_lines = _bounded_ints(payload.get("token_lines"), len(token_kinds))

    return PowerShellParseSummary(
        syntax_errors=tuple(errors),
        token_count=max(0, int(payload.get("token_count", 0)))
        if isinstance(payload.get("token_count", 0), int)
        else 0,
        token_kinds=token_kinds,
        token_lines=token_lines,
        statement_lines=_bounded_ints(payload.get("statement_lines")),
        pipeline_lines=_bounded_ints(payload.get("pipeline_lines")),
        semicolon_lines=_bounded_ints(payload.get("semicolon_lines")),
        clause_kinds=_bounded_strings(payload.get("clause_kinds"), 512),
        clause_lines=_bounded_ints(payload.get("clause_lines"), 512),
        clause_end_lines=_bounded_ints(payload.get("clause_end_lines"), 512),
        function_lines=_bounded_ints(payload.get("function_lines"), 512),
        class_lines=_bounded_ints(payload.get("class_lines"), 512),
        comment_help_lines=_bounded_ints(payload.get("comment_help_lines"), 512),
    )


__all__ = [
    "PowerShellParseSummary",
    "PowerShellParserRunner",
    "PowerShellRunnerResult",
    "PowerShellSyntaxError",
]
