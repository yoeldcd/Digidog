# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Domain models and value objects for symbol search and code structure navigation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SymbolKind(Enum):
    """Supported symbol kinds for filtering search queries.

    Members:
        ALL: Match any symbol category (classes, functions, methods).
        CLASS: Match class declarations.
        FUNCTION: Match top-level function declarations.
        METHOD: Match class method declarations.
    """

    ALL = "all"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


@dataclass(frozen=True)
class SymbolLocationDTO:
    """Immutable location contract representing a discovered code symbol.

    Attributes:
        name: Identifier name of the symbol (e.g. class or function name).
        kind: Semantic category of the symbol.
        filepath: Absolute or workspace-relative file path where symbol is defined.
        start_line: 1-indexed line number where the symbol definition begins.
        end_line: 1-indexed line number where the symbol definition ends.
        signature: Parameter signature string of the symbol.
        docstring_summary: First line or summary of the symbol's docstring.
        parent_symbol: Containing class name if this symbol is a method, or empty string.
    """

    name: str
    kind: SymbolKind
    filepath: str
    start_line: int
    end_line: int
    signature: str
    docstring_summary: str
    parent_symbol: str = ""

    def as_dict(self) -> dict[str, object]:
        """Convert symbol location contract into a serializable dictionary.

        Returns:
            dict[str, object]: Dictionary representation of the symbol location.
        """
        return {
            "name": self.name,
            "kind": self.kind.value,
            "filepath": self.filepath,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "signature": self.signature,
            "docstring_summary": self.docstring_summary,
            "parent_symbol": self.parent_symbol,
        }


@dataclass(frozen=True)
class SymbolSearchQuery:
    """Query parameter container for symbol lookup operations.

    Attributes:
        name_pattern: Search substring or pattern matching symbol names.
        language: Programming language parser to apply (defaults to "python").
        path: Base directory or file path to search within.
        kind: Filtering category restriction (defaults to SymbolKind.ALL).
    """

    name_pattern: str
    language: str = ""
    path: str = "."
    kind: SymbolKind = SymbolKind.ALL
