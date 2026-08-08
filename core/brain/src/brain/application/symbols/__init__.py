# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Public application exports for multi-language symbol search services and strategies."""

from __future__ import annotations

from brain.application.symbols.parsers import (
    DEFAULT_PARSER_REGISTRY,
    BaseSymbolParser,
    BatchSymbolParser,
    JsTsSymbolParser,
    ParserRegistry,
    PowerShellSymbolParser,
    PythonSymbolParser,
    extract_batch_symbols_from_file,
    extract_js_ts_symbols_from_file,
    extract_powershell_symbols_from_file,
    extract_python_symbols_from_file,
)
from brain.application.symbols.symbol_search_service import infer_language_from_extension, search_symbols

__all__ = [
    "infer_language_from_extension",
    "search_symbols",
    "BaseSymbolParser",
    "PythonSymbolParser",
    "JsTsSymbolParser",
    "PowerShellSymbolParser",
    "BatchSymbolParser",
    "ParserRegistry",
    "DEFAULT_PARSER_REGISTRY",
    "extract_python_symbols_from_file",
    "extract_js_ts_symbols_from_file",
    "extract_powershell_symbols_from_file",
    "extract_batch_symbols_from_file",
]
