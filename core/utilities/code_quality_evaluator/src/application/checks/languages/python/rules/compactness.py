"""Python compactness and one-line syntax rules."""

from __future__ import annotations

import ast
from collections import Counter

from src.domain.models import Evidence, LanguageQualityPolicy

from ..parser import ParseResult
from .evidence import evidence

_OPERATION_TYPES = (
    ast.Await,
    ast.Attribute,
    ast.BinOp,
    ast.BoolOp,
    ast.Call,
    ast.Compare,
    ast.NamedExpr,
    ast.Subscript,
    ast.UnaryOp,
    ast.Yield,
)


def _semicolon_evidence(parsed: ParseResult, path: str) -> tuple[Evidence, ...]:
    """Collect semicolon tokens while ignoring strings and comments.

    Args:
        parsed: Successful parser result containing token spans.
        path: Relative source path.

    Returns:
        tuple[Evidence, ...]: Source-ordered semicolon findings.
    """

    return tuple(
        evidence(path, token.start[0], "semicolon statement separator")
        for token in parsed.tokens
        if token.type == 54 and token.string == ";"
    )


def _one_line_suite_evidence(tree: ast.Module, path: str) -> tuple[Evidence, ...]:
    """Collect control declarations whose suite starts on their header line.

    Args:
        tree: Parsed Python module.
        path: Relative source path.

    Returns:
        tuple[Evidence, ...]: Source-ordered one-line suite findings.
    """

    findings: list[Evidence] = []
    suite_nodes = (
        ast.ClassDef,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.ExceptHandler,
    )

    for node in ast.walk(tree):
        if not isinstance(node, suite_nodes) or not hasattr(node, "lineno"):
            continue

        body = getattr(node, "body", ())

        if any(getattr(statement, "lineno", -1) == node.lineno for statement in body):
            findings.append(evidence(path, node.lineno, "one-line suite"))

    return tuple(findings)


def _operation_count(statement: ast.stmt) -> int:
    """Count expression operations while excluding nested suites.

    Args:
        statement: Statement whose operations are counted.

    Returns:
        int: Number of operation AST nodes.
    """

    count = 0

    def visit(node: ast.AST) -> None:
        """Visit one node and accumulate operation counts.

        Args:
            node: AST node currently traversed.

        Returns:
            None: Count is accumulated in the enclosing scope.
        """

        nonlocal count

        if node is not statement and isinstance(node, ast.stmt):
            return

        if isinstance(node, _OPERATION_TYPES):
            if isinstance(node, ast.BoolOp):
                count += max(1, len(node.values) - 1)

            elif isinstance(node, ast.Compare):
                count += max(1, len(node.ops))

            else:
                count += 1

        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(statement)

    return count


def _operation_locations(statement: ast.stmt) -> tuple[int, ...]:
    """Return source lines for every operation in one statement.

    Args:
        statement: Statement whose operation locations are collected.

    Returns:
        tuple[int, ...]: Source-ordered operation lines.
    """

    locations: list[int] = []

    def visit(node: ast.AST) -> None:
        """Visit expression nodes while excluding nested suites.

        Args:
            node: AST node being inspected.

        Returns:
            None: Locations are accumulated in the enclosing scope.
        """

        if node is not statement and isinstance(node, ast.stmt):
            return

        if isinstance(node, _OPERATION_TYPES) and hasattr(node, "lineno"):
            locations.append(node.lineno)

        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(statement)

    return tuple(locations)


def _is_exempt_operation_statement(
    statement: ast.stmt,
    policy: LanguageQualityPolicy,
) -> bool:
    """Return whether compactness exemptions apply to one statement.

    Args:
        statement: Statement under compactness evaluation.
        policy: Compactness policy containing exemption switches.

    Returns:
        bool: ``True`` when a configured exemption applies.
    """

    nodes = tuple(ast.walk(statement))

    if policy.compactness.exempt_comprehensions and any(
        isinstance(node, ast.comprehension) for node in nodes
    ):
        return True

    operation_nodes = tuple(
        node for node in nodes if isinstance(node, _OPERATION_TYPES)
    )
    fluent_types = (ast.Call, ast.Attribute, ast.Subscript)

    return (
        policy.compactness.exempt_fluent_chains
        and len(operation_nodes) > 1
        and all(isinstance(node, fluent_types) for node in operation_nodes)
    )


def compactness_evidence(
    parsed: ParseResult,
    policy: LanguageQualityPolicy | None,
    path: str,
) -> tuple[Evidence, ...]:
    """Collect semicolon, suite, statement, and operation findings.

    Args:
        parsed: Successful parser result.
        policy: Optional compactness policy.
        path: Relative source path.

    Returns:
        tuple[Evidence, ...]: Source-ordered compactness findings.
    """

    if policy is None or parsed.module is None:
        return ()

    compactness = policy.compactness
    findings: list[Evidence] = []

    if compactness.forbid_semicolons:
        findings.extend(_semicolon_evidence(parsed, path))

    if compactness.forbid_one_line_suites:
        findings.extend(_one_line_suite_evidence(parsed.module, path))

    statements = tuple(
        node for node in ast.walk(parsed.module) if isinstance(node, ast.stmt)
    )
    line_counts = Counter(node.lineno for node in statements)

    for line, count in sorted(line_counts.items()):
        if count > compactness.max_statements_per_line:
            findings.append(evidence(path, line, "too many statements on one line"))

    if compactness.max_operations_per_statement is not None:
        ordered_statements = sorted(
            statements,
            key=lambda node: (node.lineno, node.col_offset),
        )

        for statement in ordered_statements:
            if _is_exempt_operation_statement(statement, policy):
                continue

            operation_count = _operation_count(statement)

            if operation_count > compactness.max_operations_per_statement:
                findings.extend(
                    evidence(path, line, "too many operations in one statement")
                    for line in _operation_locations(statement)
                )

    return tuple(
        sorted(
            findings,
            key=lambda item: (item.line_start or 0, item.line_end or 0, item.summary),
        )
    )


__all__ = ["compactness_evidence"]
