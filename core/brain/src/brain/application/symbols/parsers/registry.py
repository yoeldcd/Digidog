# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Strategy registry for managing and dispatching symbol parsers."""

from __future__ import annotations

import os
from typing import Sequence

from brain.application.symbols.parsers.base_parser import BaseSymbolParser
from brain.application.symbols.parsers.batch_parser import BatchSymbolParser
from brain.application.symbols.parsers.js_ts_parser import JsTsSymbolParser
from brain.application.symbols.parsers.powershell_parser import PowerShellSymbolParser
from brain.application.symbols.parsers.python_parser import PythonSymbolParser
from brain.domain.symbols.models import SymbolKind, SymbolLocationDTO


class ParserRegistry:
    """Strategy registry holding registered BaseSymbolParser instances."""

    def __init__(self, parsers: Sequence[BaseSymbolParser] | None = None) -> None:
        """Initialize registry with a sequence of symbol parser strategies.

        Args:
            parsers (Sequence[BaseSymbolParser] | None): Initial parser strategies.
        """
        self._parsers: list[BaseSymbolParser] = list(parsers) if parsers else []

    def register(self, parser: BaseSymbolParser) -> None:
        """Register a new BaseSymbolParser strategy.

        Args:
            parser (BaseSymbolParser): Parser instance to register.
        """
        if parser not in self._parsers:
            self._parsers.append(parser)

    def get_all_parsers(self) -> tuple[BaseSymbolParser, ...]:
        """Return tuple of all registered parser strategies.

        Returns:
            tuple[BaseSymbolParser, ...]: Registered strategies.
        """
        return tuple(self._parsers)

    def parse_file(
        self,
        filepath: str,
        name_pattern: str,
        kind_filter: SymbolKind,
        requested_lang: str,
    ) -> tuple[SymbolLocationDTO, ...]:
        """Polymorphically dispatch file parsing across registered strategies.

        Args:
            filepath (str): Target source code file path.
            name_pattern (str): Name filter pattern.
            kind_filter (SymbolKind): Symbol category filter.
            requested_lang (str): Language filter string ("python", "all", etc.).

        Returns:
            tuple[SymbolLocationDTO, ...]: Discovered symbol locations.
        """
        ext = os.path.splitext(filepath)[1].lower()
        symbols: list[SymbolLocationDTO] = []
        lang_norm = requested_lang.lower().strip()

        for parser in self._parsers:
            ext_match = ext in parser.supported_extensions

            accepted_langs = {
                "all",
                "",
                "auto",
                parser.language_name,
                parser.language_name[:2],
            }
            if parser.language_name in ("typescript", "javascript"):
                accepted_langs.update({"javascript", "js", "typescript", "ts"})
            elif parser.language_name == "powershell":
                accepted_langs.update({"powershell", "ps1", "ps"})
            elif parser.language_name == "batch":
                accepted_langs.update({"batch", "bat", "cmd"})
            elif parser.language_name == "python":
                accepted_langs.update({"python", "py"})

            lang_match = lang_norm in accepted_langs

            if ext_match and lang_match:
                found = parser.parse_symbols(filepath, name_pattern, kind_filter)
                symbols.extend(found)

        return tuple(symbols)


DEFAULT_PARSER_REGISTRY = ParserRegistry(
    [
        PythonSymbolParser(),
        JsTsSymbolParser(),
        PowerShellSymbolParser(),
        BatchSymbolParser(),
    ]
)
