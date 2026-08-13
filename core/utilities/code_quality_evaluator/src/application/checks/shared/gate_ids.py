"""Stable gate identifiers shared by every language analyzer.

The evaluator treats gate identifiers as a public contract. Keeping the complete
declaration in one immutable mapping lets analyzers validate fixed cardinality
and lets the dispatcher build a total registry without language branches.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from src.domain.models import Language

SHARED_GATE_IDS: Final[tuple[str, ...]] = (
    "REQ-01-DIGEST",
    "REQ-01-CONTENT",
    "REQ-01-PATH",
    "REQ-01-LINE-LENGTH",
    "REQ-01-REQUIRED",
    "REQ-01-FORBIDDEN",
)
"""The six artifact gates that always run before language gates."""

ARTIFACT_GATE_IDS: Final[tuple[str, ...]] = SHARED_GATE_IDS
"""Alias naming the shared artifact gate declaration explicitly."""

PYTHON_GATE_IDS: Final[tuple[str, ...]] = (
    "PY-SYNTAX",
    "PY-ANNOTATIONS",
    "PY-DOCSTRINGS",
    "PY-IMPORTS",
    "PY-NO-ANY",
    "PY-VERTICAL-LAYOUT",
    "PY-COMPACTNESS",
)
"""Fixed gate declaration for Python analyzers."""

JAVASCRIPT_GATE_IDS: Final[tuple[str, ...]] = (
    "JS-SYNTAX",
    "JS-DOCUMENTATION",
    "JS-VERTICAL-LAYOUT",
    "JS-COMPACTNESS",
)
"""Fixed gate declaration for JavaScript analyzers."""

TYPESCRIPT_GATE_IDS: Final[tuple[str, ...]] = (
    "TS-SYNTAX",
    "TS-DOCUMENTATION",
    "TS-VERTICAL-LAYOUT",
    "TS-COMPACTNESS",
)
"""Fixed gate declaration for TypeScript analyzers."""

JSON_GATE_IDS: Final[tuple[str, ...]] = (
    "JSON-SYNTAX",
    "JSON-STRUCTURE",
)
"""Fixed gate declaration for JSON analyzers."""

MARKDOWN_GATE_IDS: Final[tuple[str, ...]] = (
    "MD-SYNTAX",
    "MD-STRUCTURE",
    "MD-COMPACTNESS",
)
"""Fixed syntax, structure, and anti-compactness gates for Markdown analyzers."""

POWERSHELL_GATE_IDS: Final[tuple[str, ...]] = (
    "PS-SYNTAX",
    "PS-DOCUMENTATION",
    "PS-VERTICAL-LAYOUT",
    "PS-COMPACTNESS",
)
"""Fixed gate declaration for PowerShell analyzers."""


LANGUAGE_GATE_IDS: Final[Mapping[Language, tuple[str, ...]]] = MappingProxyType(
    {
        Language.PYTHON: PYTHON_GATE_IDS,
        Language.JAVASCRIPT: JAVASCRIPT_GATE_IDS,
        Language.TYPESCRIPT: TYPESCRIPT_GATE_IDS,
        Language.JSON: JSON_GATE_IDS,
        Language.MARKDOWN: MARKDOWN_GATE_IDS,
        Language.POWERSHELL: POWERSHELL_GATE_IDS,
    }
)
"""Immutable total mapping from every supported language to its gates."""

SUPPORTED_LANGUAGES: Final[tuple[Language, ...]] = tuple(LANGUAGE_GATE_IDS)
"""Stable language order used when constructing a total registry."""


def gate_ids_for(language: Language) -> tuple[str, ...]:
    """Return the exact analyzer gate declaration for one language.

    Args:
        language: Supported source language selected by the caller.

    Returns:
        tuple[str, ...]: Immutable gate IDs in declaration order.

    Raises:
        ValueError: If the language is not present in the total declaration.
    """

    try:
        return LANGUAGE_GATE_IDS[language]

    except (KeyError, TypeError) as error:
        raise ValueError(f"unsupported language: {language!r}") from error


__all__ = [
    "ARTIFACT_GATE_IDS",
    "JAVASCRIPT_GATE_IDS",
    "JSON_GATE_IDS",
    "LANGUAGE_GATE_IDS",
    "MARKDOWN_GATE_IDS",
    "POWERSHELL_GATE_IDS",
    "PYTHON_GATE_IDS",
    "SHARED_GATE_IDS",
    "SUPPORTED_LANGUAGES",
    "TYPESCRIPT_GATE_IDS",
    "gate_ids_for",
]
