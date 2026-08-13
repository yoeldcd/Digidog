"""PowerShell parser facade over the fixed Parser.ParseInput runner."""

from __future__ import annotations

from dataclasses import dataclass

from src.infrastructure.powershell_parser_runner import (
    PowerShellParserRunner,
    PowerShellParseSummary,
)


@dataclass(frozen=True, slots=True)
class LineSummary:
    """Describe one PowerShell source line without retaining its text.

    Attributes:
        line: One-based source line number.
        blank: Whether the line contains no non-whitespace characters.
    """

    line: int
    blank: bool


@dataclass(frozen=True, slots=True)
class PowerShellParseResult:
    """Represent one immutable PowerShell parse attempt.

    Attributes:
        available: Whether the parser process returned a usable summary.
        summary: Bounded parser facts, or ``None`` when execution was unavailable.
        message: Redacted execution classification.
        lines: Immutable blank-line facts derived from in-memory source.
    """

    available: bool
    summary: PowerShellParseSummary | None
    message: str
    lines: tuple[LineSummary, ...] = ()

    @property
    def syntax_valid(self) -> bool:
        """Return whether parsing succeeded and produced no syntax errors.

        Args:
            No arguments are accepted beyond the parse result instance.

        Returns:
            bool: ``True`` when a summary exists and contains no parser errors.
        """

        return (
            self.available
            and self.summary is not None
            and not self.summary.syntax_errors
        )


class PowerShellParser:
    """Parse PowerShell source through stdin without temporary files."""

    def __init__(self, runner: PowerShellParserRunner | None = None) -> None:
        """Initialize the parser with an injectable process runner.

        Args:
            runner: Optional fixed parser runner used for tests or custom timeouts.
        """
        self._runner = runner or PowerShellParserRunner()

    def parse(self, content: str) -> PowerShellParseResult:
        """Parse complete PowerShell source held in memory.

        Args:
            content: Complete PowerShell source text.

        Returns:
            PowerShellParseResult: Redacted parser outcome and layout facts.
        """

        result = self._runner.run(content)

        return PowerShellParseResult(
            available=result.summary is not None,
            summary=result.summary,
            message=result.message,
            lines=tuple(
                LineSummary(line=index, blank=not value.strip())
                for index, value in enumerate(content.splitlines(), start=1)
            ),
        )


__all__ = ["LineSummary", "PowerShellParseResult", "PowerShellParser"]
