# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Public exports for symbol parser strategies and registry."""

from __future__ import annotations

from brain.application.symbols.parsers.base_parser import BaseSymbolParser
from brain.application.symbols.parsers.batch_parser import BatchSymbolParser, extract_batch_symbols_from_file
from brain.application.symbols.parsers.js_ts_parser import JsTsSymbolParser, extract_js_ts_symbols_from_file
from brain.application.symbols.parsers.powershell_parser import PowerShellSymbolParser, extract_powershell_symbols_from_file
from brain.application.symbols.parsers.python_parser import PythonSymbolParser, extract_python_symbols_from_file
from brain.application.symbols.parsers.registry import DEFAULT_PARSER_REGISTRY, ParserRegistry

__all__ = [
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
