"""Python import and forbidden ``Any`` rules."""

from __future__ import annotations

import ast

from src.domain.models import Evidence

from .evidence import evidence


def import_evidence(tree: ast.Module, path: str) -> tuple[Evidence, ...]:
    """Collect wildcard and duplicate imports in source order.

    Args:
        tree: Parsed Python module.
        path: Relative source path.

    Returns:
        tuple[Evidence, ...]: Import findings.
    """

    findings: list[Evidence] = []
    seen_modules: set[str] = set()
    imports = tuple(
        sorted(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ),
            key=lambda node: (node.lineno, node.col_offset),
        )
    )

    for node in imports:
        if isinstance(node, ast.ImportFrom) and any(
            alias.name == "*" for alias in node.names
        ):
            findings.append(evidence(path, node.lineno, "wildcard import"))

        module = (
            node.module
            if isinstance(node, ast.ImportFrom)
            else ",".join(alias.name for alias in node.names)
        )

        if module in seen_modules:
            findings.append(evidence(path, node.lineno, f"duplicate import: {module}"))

        seen_modules.add(module)

    return tuple(findings)


def any_evidence(tree: ast.Module, path: str) -> tuple[Evidence, ...]:
    """Collect every use of the forbidden ``Any`` type symbol.

    Args:
        tree: Parsed Python module.
        path: Relative source path.

    Returns:
        tuple[Evidence, ...]: Source-ordered ``Any`` findings.
    """

    return tuple(
        evidence(path, node.lineno, "Any usage")
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "Any"
    )


__all__ = ["any_evidence", "import_evidence"]
