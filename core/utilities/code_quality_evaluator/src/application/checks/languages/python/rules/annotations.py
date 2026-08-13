"""Python annotation rules."""

from __future__ import annotations

import ast

from src.domain.models import Evidence

from .evidence import evidence


def all_callables(tree: ast.AST) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]:
    """Return callable declarations in source order.

    Args:
        tree: Parsed Python tree.

    Returns:
        tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]: Ordered callables.
    """

    callables = tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )

    return tuple(sorted(callables, key=lambda node: (node.lineno, node.col_offset)))


def annotation_evidence(tree: ast.AST, path: str) -> tuple[Evidence, ...]:
    """Collect untyped parameters and return declarations.

    Args:
        tree: Parsed Python tree.
        path: Relative source path.

    Returns:
        tuple[Evidence, ...]: Source-ordered annotation findings.
    """

    findings: list[Evidence] = []

    for function in all_callables(tree):
        parameters = [
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        ]

        if function.args.vararg is not None:
            parameters.append(function.args.vararg)

        if function.args.kwarg is not None:
            parameters.append(function.args.kwarg)

        for parameter in parameters:
            if parameter.arg not in {"self", "cls"} and parameter.annotation is None:
                findings.append(
                    evidence(
                        path,
                        parameter.lineno,
                        f"untyped parameter: {parameter.arg}",
                    )
                )

        if function.returns is None:
            findings.append(
                evidence(path, function.lineno, f"untyped return: {function.name}")
            )

    return tuple(findings)


__all__ = ["all_callables", "annotation_evidence"]
