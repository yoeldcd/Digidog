# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application service coordinating code symbol search operations across target files."""

from __future__ import annotations

import os

from brain.application.symbols.parsers.registry import DEFAULT_PARSER_REGISTRY, ParserRegistry
from brain.domain.symbols.models import SymbolLocationDTO, SymbolSearchQuery

EXTENSION_TO_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".psd1": "powershell",
    ".bat": "batch",
    ".cmd": "batch",
}


def infer_language_from_extension(filepath: str) -> str | None:
    """Infer target programming language from file extension.

    Args:
        filepath (str): Target source code file path.

    Returns:
        str | None: Inferred language name or None if extension is unmapped.
    """
    ext = os.path.splitext(filepath)[1].lower()
    return EXTENSION_TO_LANGUAGE_MAP.get(ext)


def search_symbols(
    query: SymbolSearchQuery,
    registry: ParserRegistry = DEFAULT_PARSER_REGISTRY,
) -> tuple[SymbolLocationDTO, ...]:
    """Search for matching code symbols across files or directories polymorphically.

    Args:
        query (SymbolSearchQuery): Search parameters and filters.
        registry (ParserRegistry): Parser strategy registry.

    Returns:
        tuple[SymbolLocationDTO, ...]: Discovered symbol location contracts.
    """
    target_path = os.path.abspath(query.path)

    if not os.path.exists(target_path):
        return ()

    symbols: list[SymbolLocationDTO] = []
    requested_lang = query.language.lower().strip() if query.language else ""

    if os.path.isfile(target_path):
        if not requested_lang or requested_lang in ("auto", "all"):
            inferred = infer_language_from_extension(target_path)
            if inferred:
                requested_lang = inferred

        found = registry.parse_file(target_path, query.name_pattern, query.kind, requested_lang)
        symbols.extend(found)
        return tuple(symbols)

    # Traverse directory tree
    for root, dirs, files in os.walk(target_path):
        # Exclude hidden and environment directories
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in ("__pycache__", "venv", "node_modules", "dist", "build")
        ]

        for file in files:
            filepath = os.path.join(root, file)
            file_lang = requested_lang
            if not file_lang or file_lang in ("auto", "all"):
                inferred = infer_language_from_extension(filepath)
                if inferred:
                    file_lang = inferred
            found = registry.parse_file(filepath, query.name_pattern, query.kind, file_lang)
            symbols.extend(found)

    return tuple(symbols)
