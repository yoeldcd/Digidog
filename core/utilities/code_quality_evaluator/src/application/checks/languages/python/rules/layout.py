"""Python vertical-layout rules driven by AST and token source spans."""

from __future__ import annotations

import ast

from src.domain.models import Evidence, LanguageQualityPolicy

from ..parser import ParseResult
from .evidence import evidence

_CONTROL_TOKENS: tuple[tuple[type[ast.AST], str], ...] = (
    (ast.ClassDef, "class"),
    (ast.AsyncFunctionDef, "async_def"),
    (ast.FunctionDef, "def"),
    (ast.If, "if"),
    (ast.For, "for"),
    (ast.AsyncFor, "async_for"),
    (ast.While, "while"),
    (ast.Try, "try"),
    (ast.ExceptHandler, "except"),
    (ast.With, "with"),
    (ast.AsyncWith, "async_with"),
    (ast.Match, "match"),
    (ast.Return, "return"),
    (ast.Raise, "raise"),
    (ast.Yield, "yield"),
)


def _statement_events(tree: ast.Module) -> tuple[tuple[str, ast.AST, int, int], ...]:
    """Return configured AST layout events with decorator-aware starts.

    Args:
        tree: Parsed Python module.

    Returns:
        tuple[tuple[str, ast.AST, int, int], ...]: Token, node, start, end lines.
    """

    events: list[tuple[str, ast.AST, int, int]] = []

    for node in ast.walk(tree):
        token_name = next(
            (
                token
                for node_type, token in _CONTROL_TOKENS
                if isinstance(node, node_type)
            ),
            None,
        )

        if token_name is None or not hasattr(node, "lineno"):
            continue

        start = node.lineno
        decorators = getattr(node, "decorator_list", ())

        if decorators:
            start = min(decorator.lineno for decorator in decorators)

        end = getattr(node, "end_lineno", start) or start
        events.append((token_name, node, start, end))

    return tuple(
        sorted(events, key=lambda item: (item[2], getattr(item[1], "col_offset", 0)))
    )


def _clause_events(parsed: ParseResult) -> tuple[tuple[str, ast.AST, int, int], ...]:
    """Return tokenized clause events not represented by standalone AST nodes.

    Args:
        parsed: Successful parser result containing source tokens and lines.

    Returns:
        tuple[tuple[str, ast.AST, int, int], ...]: Clause source spans.
    """

    clause_names = {"elif", "else", "finally", "case"}
    events: list[tuple[str, ast.AST, int, int]] = []

    for token in parsed.tokens:
        if token.type != 1 or token.string not in clause_names:
            continue

        line_index = token.start[0] - 1
        source_line = (
            parsed.lines[line_index].lstrip() if line_index < len(parsed.lines) else ""
        )
        is_elif = token.string == "elif" and source_line.startswith("elif ")
        is_else = token.string == "else" and source_line.startswith("else:")
        is_finally = token.string == "finally" and source_line.startswith("finally:")
        is_case = (
            token.string == "case"
            and source_line.startswith("case ")
            and ":" in source_line
        )

        if not (is_elif or is_else or is_finally or is_case):
            continue

        placeholder = ast.Pass(lineno=token.start[0], col_offset=token.start[1])
        events.append((token.string, placeholder, token.start[0], token.start[0]))

    return tuple(events)


def _leading_indent(line: str) -> int:
    """Return leading indentation width, treating tabs as four spaces.

    Args:
        line: Source line text.

    Returns:
        int: Number of leading whitespace characters.
    """

    return len(line) - len(line.lstrip(" \t"))


def layout_evidence(
    parsed: ParseResult,
    policy: LanguageQualityPolicy | None,
    path: str,
) -> tuple[Evidence, ...]:
    """Collect configured blank-boundary violations.

    Args:
        parsed: Successful parser result.
        policy: Optional policy controlling blank boundaries.
        path: Relative source path.

    Returns:
        tuple[Evidence, ...]: Source-ordered layout findings.
    """

    if policy is None or not policy.vertical_layout.enabled or parsed.module is None:
        return ()

    lines = parsed.lines
    configured_before = set(policy.vertical_layout.blank_before)
    configured_after = set(policy.vertical_layout.blank_after)
    minimum = policy.vertical_layout.minimum_blank_lines
    findings: list[Evidence] = []
    events = (*_statement_events(parsed.module), *_clause_events(parsed))

    for token_name, node, start, end in sorted(
        events,
        key=lambda item: (item[2], getattr(item[1], "col_offset", 0)),
    ):
        if token_name in configured_before and start > 1:
            previous_line = lines[start - 2].strip() if start - 2 < len(lines) else ""
            current_line = lines[start - 1] if start - 1 < len(lines) else ""
            current_indent = _leading_indent(current_line)
            previous_indent = _leading_indent(lines[start - 2])
            first_child_after_header = (
                previous_line.endswith(":") and current_indent > previous_indent
            )
            blank_count = 0
            cursor = start - 2

            while cursor >= 0 and not lines[cursor].strip():
                blank_count += 1
                cursor -= 1

            if not first_child_after_header and blank_count < minimum:
                findings.append(
                    evidence(path, start, f"blank line missing before {token_name}")
                )

        if token_name in configured_after and end < len(lines):
            blank_count = 0
            cursor = end

            while cursor < len(lines) and not lines[cursor].strip():
                blank_count += 1
                cursor += 1

            if blank_count < minimum:
                findings.append(
                    evidence(path, end, f"blank line missing after {token_name}")
                )

    return tuple(findings)


__all__ = ["layout_evidence"]
