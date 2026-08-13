"""In-memory TypeScript/TSX parsing backed by the pinned ESTree subprocess."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re

from .....infrastructure.node_parser_runner import NodeParserOutcome, NodeParserRunner


@dataclass(frozen=True, slots=True)
class LineSummary:
    """Describe one source line without retaining its text.

    Attributes:
        line: One-based source line number.
        length: Number of characters on the line.
        blank: Whether the line contains no non-whitespace characters.
        indent: Leading whitespace character count.
    """

    line: int
    length: int
    blank: bool
    indent: int


@dataclass(frozen=True, slots=True)
class CommentSummary:
    """Describe one comment and its JSDoc section markers.

    Attributes:
        line: One-based first comment line.
        end_line: One-based final comment line.
        is_jsdoc: Whether the comment uses JSDoc block syntax.
        has_description: Whether non-tag descriptive text is present.
        sections: Immutable lower-case JSDoc tag names.
    """

    line: int
    end_line: int
    is_jsdoc: bool
    has_description: bool
    sections: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeclarationSummary:
    """Describe one TypeScript declaration, including TS-native declarations.

    Attributes:
        kind: ESTree declaration node type.
        name: Bounded declaration name when available.
        line: One-based declaration start line.
        end_line: One-based declaration end line.
        documented: Whether a nearby JSDoc comment was found.
        documentation_sections: JSDoc tags associated with the declaration.
        private: Whether the declaration name starts with an underscore.
    """

    kind: str
    name: str
    line: int
    end_line: int
    documented: bool
    documentation_sections: tuple[str, ...]
    private: bool


@dataclass(frozen=True, slots=True)
class LayoutNodeSummary:
    """Describe a TypeScript syntax node used by vertical-layout checks.

    Attributes:
        kind: ESTree node type.
        line: One-based node start line.
        end_line: One-based node end line.
        one_line_suite: Whether a control body starts on its header line.
    """

    kind: str
    line: int
    end_line: int
    one_line_suite: bool


@dataclass(frozen=True, slots=True)
class StatementSummary:
    """Describe one statement and its AST operation locations.

    Attributes:
        kind: ESTree statement node type.
        line: One-based statement start line.
        end_line: One-based statement end line.
        operation_count: Number of operation nodes in the statement.
        operation_lines: Immutable source lines containing those operations.
    """

    kind: str
    line: int
    end_line: int
    operation_count: int
    operation_lines: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TypeScriptParseResult:
    """Immutable TypeScript parse and source-structure summary.

    Attributes:
        syntax_valid: Whether the ESTree parser accepted the source.
        error_kind: Bounded syntax error classification, when invalid.
        error_line: One-based syntax error line, when available.
        error_column: One-based syntax error column, when available.
        node_types: Distinct ESTree node types observed.
        declarations: Immutable declaration summaries.
        comments: Immutable comment summaries.
        nodes: Immutable layout node summaries.
        statements: Immutable statement summaries.
        semicolon_lines: One-based lines containing semicolon tokens.
        lines: Immutable source line summaries.
    """

    syntax_valid: bool
    error_kind: str | None
    error_line: int | None
    error_column: int | None
    node_types: tuple[str, ...]
    declarations: tuple[DeclarationSummary, ...]
    comments: tuple[CommentSummary, ...]
    nodes: tuple[LayoutNodeSummary, ...]
    statements: tuple[StatementSummary, ...]
    semicolon_lines: tuple[int, ...]
    lines: tuple[LineSummary, ...]


def _integer(value: object, default: int = 1) -> int:
    """Return a positive integer from untrusted parser JSON.

    Args:
        value: Candidate parser value.
        default: Fallback value when the candidate is not positive.

    Returns:
        int: Positive candidate or fallback value.
    """

    return value if isinstance(value, int) and value > 0 else default


def _text(value: object) -> str:
    """Return a bounded parser string or an empty value.

    Args:
        value: Candidate parser value.

    Returns:
        str: Candidate text when valid, otherwise an empty string.
    """

    return value if isinstance(value, str) else ""


def _tuple_text(value: object) -> tuple[str, ...]:
    """Convert a parser JSON sequence into immutable text values.

    Args:
        value: Candidate parser sequence.

    Returns:
        tuple[str, ...]: Text members retained in source order.
    """

    if not isinstance(value, (list, tuple)):
        return ()

    return tuple(item for item in value if isinstance(item, str))


class TypeScriptParser:
    """Parse TypeScript and TSX without importing or delegating to JavaScript code."""

    def __init__(
        self, runner: NodeParserRunner | None = None, timeout: float = 10.0
    ) -> None:
        """Initialize the parser with an injectable fixed runner and timeout.

        Args:
            runner: Optional in-memory parser runner used for tests.
            timeout: Maximum parser process duration in seconds.
        """

        self._runner = runner or NodeParserRunner()
        self._timeout = timeout

    def parse(self, source: str) -> TypeScriptParseResult:
        """Parse source and return immutable TypeScript-specific summaries.

        Args:
            source: Complete TypeScript or TSX source held in memory.

        Returns:
            TypeScriptParseResult: Typed parser and source-structure summary.
        """

        outcome = self._runner.run_typescript(source, timeout=self._timeout)

        return self._result(outcome, source)

    @staticmethod
    def _result(outcome: NodeParserOutcome, source: str = "") -> TypeScriptParseResult:
        """Translate bounded runner JSON into typed summary records.

        Args:
            outcome: Source-redacted result returned by the node runner.
            source: Optional source text used to recover class method summaries.

        Returns:
            TypeScriptParseResult: Immutable parsed summary or syntax failure.
        """

        if not outcome.succeeded:
            return TypeScriptParseResult(
                False,
                outcome.error_kind,
                outcome.error_line,
                outcome.error_column,
                (),
                (),
                (),
                (),
                (),
                (),
                (),
            )

        payload: Mapping[str, object] = outcome.payload
        declarations: list[DeclarationSummary] = []

        for item in payload.get("declarations", ()):
            if isinstance(item, Mapping):
                declarations.append(
                    DeclarationSummary(
                        _text(item.get("kind")),
                        _text(item.get("name")),
                        _integer(item.get("line")),
                        _integer(item.get("end_line")),
                        bool(item.get("documented")),
                        _tuple_text(item.get("documentation_sections")),
                        bool(item.get("private")),
                    )
                )

        comments: list[CommentSummary] = []

        for item in payload.get("comments", ()):
            if isinstance(item, Mapping):
                comments.append(
                    CommentSummary(
                        _integer(item.get("line")),
                        _integer(item.get("end_line")),
                        bool(item.get("is_jsdoc")),
                        bool(item.get("has_description")),
                        _tuple_text(item.get("sections")),
                    )
                )

        nodes: list[LayoutNodeSummary] = []

        for item in payload.get("nodes", ()):
            if isinstance(item, Mapping):
                nodes.append(
                    LayoutNodeSummary(
                        _text(item.get("kind")),
                        _integer(item.get("line")),
                        _integer(item.get("end_line")),
                        bool(item.get("one_line_suite")),
                    )
                )

        statements: list[StatementSummary] = []

        for item in payload.get("statements", ()):
            if isinstance(item, Mapping):
                operation_lines = tuple(
                    _integer(line)
                    for line in item.get("operation_lines", ())
                    if isinstance(line, int)
                )
                statements.append(
                    StatementSummary(
                        _text(item.get("kind")),
                        _integer(item.get("line")),
                        _integer(item.get("end_line")),
                        max(0, _integer(item.get("operation_count"), 0)),
                        operation_lines,
                    )
                )

        lines: list[LineSummary] = []

        for item in payload.get("lines", ()):
            if isinstance(item, Mapping):
                lines.append(
                    LineSummary(
                        _integer(item.get("line")),
                        max(0, _integer(item.get("length"), 0)),
                        bool(item.get("blank")),
                        max(0, _integer(item.get("indent"), 0)),
                    )
                )
        semicolon_lines = tuple(
            _integer(item)
            for item in payload.get("semicolon_lines", ())
            if isinstance(item, int)
        )

        result = TypeScriptParseResult(
            True,
            None,
            None,
            None,
            _tuple_text(payload.get("node_types")),
            tuple(declarations),
            tuple(comments),
            tuple(nodes),
            tuple(statements),
            semicolon_lines,
            tuple(lines),
        )

        if source:
            result = _augment_method_declarations(result, source)

        return result


_METHOD_PATTERN = re.compile(
    r"^\s*(?:(?:public|private|protected|static|abstract|async|override|readonly|get|set|declare)\s+)*"
    r"(?P<name>[A-Za-z_$][\w$]*|constructor)\s*(?:<[^>{}()]*>)?\s*\((?P<params>[^)]*)\)"
)
_METHOD_EXCLUSIONS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "with",
    "function",
}


def _matching_end_line(lines: list[str], start_line: int, fallback: int) -> int:
    """Return a bounded brace-matched end line for one method declaration.

    Args:
        lines: Source lines held in memory.
        start_line: One-based method declaration line.
        fallback: End line used when no balanced body is found.

    Returns:
        int: One-based method end line.
    """

    balance = 0
    saw_open = False

    for index in range(start_line - 1, len(lines)):
        line = lines[index]
        balance += line.count("{")
        balance -= line.count("}")

        if "{" in line:
            saw_open = True

        if saw_open and balance <= 0:
            return index + 1

        if not saw_open and ";" in line:
            return index + 1

    return max(start_line, fallback)


def _augment_method_declarations(
    parsed: TypeScriptParseResult, source: str
) -> TypeScriptParseResult:
    """Add class methods omitted by the bounded ESTree declaration projection.

    Args:
        parsed: Immutable parser result produced by the node runner.
        source: Complete TypeScript or TSX source held in memory.

    Returns:
        TypeScriptParseResult: Parsed result with source-proven method summaries.
    """

    lines = source.splitlines()
    existing = {(item.kind, item.name, item.line) for item in parsed.declarations}
    additions: list[DeclarationSummary] = []

    class_ranges = tuple(
        (item.line, item.end_line)
        for item in parsed.declarations
        if "Class" in item.kind
    )

    for line_number, line in enumerate(lines, start=1):
        match = _METHOD_PATTERN.match(line)

        if match is None or match.group("name") in _METHOD_EXCLUSIONS:
            continue

        in_class = any(start < line_number <= end for start, end in class_ranges)

        if not in_class:
            continue

        name = match.group("name")
        kind = "MethodDefinition"
        key = (kind, name, line_number)

        if key in existing:
            continue

        additions.append(
            DeclarationSummary(
                kind=kind,
                name=name,
                line=line_number,
                end_line=_matching_end_line(lines, line_number, line_number),
                documented=False,
                documentation_sections=(),
                private=name.startswith("_"),
            )
        )
        existing.add(key)

    if not additions:
        return parsed

    declarations = tuple(
        sorted((*parsed.declarations, *additions), key=lambda item: (item.line, item.end_line))
    )

    return TypeScriptParseResult(
        parsed.syntax_valid,
        parsed.error_kind,
        parsed.error_line,
        parsed.error_column,
        parsed.node_types,
        declarations,
        parsed.comments,
        parsed.nodes,
        parsed.statements,
        parsed.semicolon_lines,
        parsed.lines,
    )


def parse_typescript(
    source: str, *, runner: NodeParserRunner | None = None
) -> TypeScriptParseResult:
    """Parse TypeScript or TSX source through a dedicated parser instance.

    Args:
        source: Complete TypeScript or TSX source held in memory.
        runner: Optional parser runner used for deterministic tests.

    Returns:
        TypeScriptParseResult: Immutable parser summary.
    """

    return TypeScriptParser(runner=runner).parse(source)


TypeScriptParseSummary = TypeScriptParseResult
"""Compatibility name for the immutable parser summary contract."""


__all__ = [
    "CommentSummary",
    "DeclarationSummary",
    "LayoutNodeSummary",
    "LineSummary",
    "StatementSummary",
    "TypeScriptParseResult",
    "TypeScriptParseSummary",
    "TypeScriptParser",
    "parse_typescript",
]
