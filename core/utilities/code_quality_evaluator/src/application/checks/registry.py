"""Production composition root for the total language analyzer dispatcher."""

from __future__ import annotations

from typing import Final

from .dispatcher import AnalyzerDispatcher, AnalyzerRegistry
from .languages.javascript import JavaScriptAnalyzer
from .languages.json import JsonAnalyzer
from .languages.markdown import MarkdownAnalyzer
from .languages.powershell import PowerShellAnalyzer
from .languages.python import PythonAnalyzer
from .languages.typescript import TypeScriptAnalyzer


def build_default_dispatcher() -> AnalyzerDispatcher:
    """Instantiate the complete production analyzer dispatcher.

    Args:
        No arguments are accepted.

    Returns:
        AnalyzerDispatcher: Frozen dispatcher with one analyzer for every
        supported language, in the canonical registry order.
    """

    analyzers = (
        PythonAnalyzer(),
        JavaScriptAnalyzer(),
        TypeScriptAnalyzer(),
        JsonAnalyzer(),
        MarkdownAnalyzer(),
        PowerShellAnalyzer(),
    )
    registry = AnalyzerRegistry.from_analyzers(analyzers)

    return AnalyzerDispatcher(registry)


DEFAULT_DISPATCHER: Final[AnalyzerDispatcher] = build_default_dispatcher()
"""Immutable production dispatcher shared by facade evaluations."""


__all__ = ["DEFAULT_DISPATCHER", "build_default_dispatcher"]
