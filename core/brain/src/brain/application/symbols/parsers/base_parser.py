# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Abstract base contract for language-specific symbol parser strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from brain.domain.symbols.models import SymbolKind, SymbolLocationDTO


class BaseSymbolParser(ABC):
    """Abstract Strategy contract for source code symbol parsers.

    Subclasses implement language-specific syntax parsing (e.g. Python AST, JSDoc,
    PowerShell functions, Batch procedures) to extract standardized symbol locations.
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """Return file extensions supported by this parser (e.g. ('.py',)).

        Returns:
            tuple[str, ...]: Tuple of lower-case file extension strings.
        """
        ...

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Return the primary lower-case language identifier (e.g. 'python').

        Returns:
            str: Language identifier string.
        """
        ...

    @abstractmethod
    def parse_symbols(
        self,
        filepath: str,
        name_pattern: str = "",
        kind_filter: SymbolKind = SymbolKind.ALL,
    ) -> tuple[SymbolLocationDTO, ...]:
        """Parse source code from a file and return matching symbol location contracts.

        Args:
            filepath (str): Target source code file path.
            name_pattern (str): Name substring or pattern filter (case-insensitive).
            kind_filter (SymbolKind): Specific symbol category filter.

        Returns:
            tuple[SymbolLocationDTO, ...]: Tuple of extracted symbol location DTOs.
        """
        ...
