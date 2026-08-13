"""Dedicated JavaScript and JSX parser/analyzer package."""

from .analyzer import JavaScriptAnalyzer, evaluate_javascript
from .parser import (
    CommentSummary,
    DeclarationSummary,
    JavaScriptParser,
    JavaScriptParseResult,
    JavaScriptParseSummary,
    LayoutNodeSummary,
    LineSummary,
    StatementSummary,
    parse_javascript,
)

__all__ = [
    "CommentSummary",
    "DeclarationSummary",
    "JavaScriptAnalyzer",
    "JavaScriptParseResult",
    "JavaScriptParseSummary",
    "JavaScriptParser",
    "LayoutNodeSummary",
    "LineSummary",
    "StatementSummary",
    "evaluate_javascript",
    "parse_javascript",
]
