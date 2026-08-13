"""Parse Python source held in memory and expose redacted source spans."""

from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass

from src.domain.models import Evidence


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Represent one immutable Python parse attempt.

    Attributes:
        module: Parsed abstract syntax tree, or ``None`` when syntax is invalid.
        tokens: Immutable token stream used by token-aware quality rules.
        lines: Source lines retained only for in-memory span calculations.
        syntax_evidence: Redacted evidence for a syntax failure, if one occurred.
    """

    module: ast.Module | None
    tokens: tuple[tokenize.TokenInfo, ...]
    lines: tuple[str, ...]
    syntax_evidence: tuple[Evidence, ...]

    @property
    def syntax_valid(self) -> bool:
        """Return whether the source produced an abstract syntax tree.

        Args:
            No arguments are accepted beyond the parse result instance.

        Returns:
            bool: ``True`` when :attr:`module` is available.
        """

        return self.module is not None


def _safe_path(path: str) -> str:
    """Return a DTO-safe evidence path without reading from disk.

    Args:
        path: Candidate source path supplied by the caller.

    Returns:
        str: Candidate path when valid, otherwise a fixed redacted fallback.
    """

    try:
        Evidence(path=path, kind="python")

    except (TypeError, ValueError):
        return "artifact.py"

    return path


def _syntax_evidence(path: str, line: int) -> tuple[Evidence, ...]:
    """Build one fixed, redacted syntax evidence record.

    Args:
        path: Candidate source path used only after DTO validation.
        line: One-based syntax-error line.

    Returns:
        tuple[Evidence, ...]: A single immutable syntax evidence tuple.
    """

    safe_path = _safe_path(path)
    evidence = Evidence(
        path=safe_path,
        line_start=max(1, line),
        line_end=max(1, line),
        kind="python",
        summary="syntax invalid",
    )

    return (evidence,)


def _tokenize(content: str) -> tuple[tokenize.TokenInfo, ...]:
    """Tokenize complete source text while keeping all work in memory.

    Args:
        content: Complete Python source text.

    Returns:
        tuple[tokenize.TokenInfo, ...]: Source-ordered immutable token records.

    Raises:
        tokenize.TokenError: If tokenization cannot complete for otherwise invalid
            source. Syntax-invalid source is normally rejected before this helper.
    """

    return tuple(tokenize.generate_tokens(io.StringIO(content).readline))


def parse_python(content: str, path: str = "artifact.py") -> ParseResult:
    """Parse Python source and collect token spans without filesystem access.

    Args:
        content: Complete Python source text held in memory.
        path: Relative source path used only in redacted evidence.

    Returns:
        ParseResult: Parsed module and tokens, or syntax evidence on failure.
    """

    try:
        module = ast.parse(content)

    except SyntaxError as error:
        syntax_line = error.lineno or 1

        return ParseResult(
            module=None,
            tokens=(),
            lines=tuple(content.splitlines()),
            syntax_evidence=_syntax_evidence(path, syntax_line),
        )

    tokens = _tokenize(content)

    return ParseResult(
        module=module,
        tokens=tokens,
        lines=tuple(content.splitlines()),
        syntax_evidence=(),
    )


__all__ = ["ParseResult", "parse_python"]
