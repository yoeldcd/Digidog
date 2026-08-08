# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""JavaScript and TypeScript symbol parser implementation."""

from __future__ import annotations

import os
import re

from brain.application.symbols.parsers.base_parser import BaseSymbolParser
from brain.domain.symbols.models import SymbolKind, SymbolLocationDTO


class JsTsSymbolParser(BaseSymbolParser):
    """Concrete symbol parser strategy for JavaScript and TypeScript source files."""

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """Return tuple of supported JS/TS file extensions.

        Returns:
            tuple[str, ...]: ('.js', '.jsx', '.ts', '.tsx')
        """
        return (".js", ".jsx", ".ts", ".tsx")

    @property
    def language_name(self) -> str:
        """Return lower-case language identifier.

        Returns:
            str: 'typescript'
        """
        return "typescript"

    def parse_symbols(
        self,
        filepath: str,
        name_pattern: str = "",
        kind_filter: SymbolKind = SymbolKind.ALL,
    ) -> tuple[SymbolLocationDTO, ...]:
        """Parse a JS/TS source file and extract matching symbol location contracts.

        Args:
            filepath (str): Target source code file path.
            name_pattern (str): Name substring or pattern filter (case-insensitive).
            kind_filter (SymbolKind): Specific symbol category filter.

        Returns:
            tuple[SymbolLocationDTO, ...]: Discovered symbol locations.
        """
        if not os.path.isfile(filepath):
            return ()

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return ()

        pattern_lower = name_pattern.strip().lower()
        symbols: list[SymbolLocationDTO] = []
        current_class: str = ""
        brace_depth = 0
        class_brace_level = -1

        # Regular expressions for JS/TS constructs
        class_regex = re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(class|interface|type)\s+([A-Za-z0-9_$]+)"
        )
        func_regex = re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function(?:\s*\*|\s+)?([A-Za-z0-9_$]+)\s*\(([^)]*)\)"
        )
        arrow_func_regex = re.compile(
            r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s+)?(?:\(([^)]*)\)|[A-Za-z0-9_$]+)\s*=>"
        )
        method_regex = re.compile(
            r"^\s*(?:(?:public|private|protected|static|override|readonly|async)\s+)*(?:get\s+|set\s+)?([A-Za-z0-9_$]+)\s*\(([^)]*)\)"
        )

        for i, line in enumerate(lines, 1):
            line_clean = line.strip()

            if not line_clean or line_clean.startswith("//") or line_clean.startswith("/*") or line_clean.startswith("*"):
                continue

            # Class / Interface / Type matching
            class_match = class_regex.search(line)
            if class_match:
                name = class_match.group(2)
                current_class = name
                class_brace_level = brace_depth

                if kind_filter in (SymbolKind.ALL, SymbolKind.CLASS):
                    if not pattern_lower or pattern_lower in name.lower():
                        symbols.append(
                            SymbolLocationDTO(
                                name=name,
                                kind=SymbolKind.CLASS,
                                filepath=filepath,
                                start_line=i,
                                end_line=i,
                                signature=line_clean.rstrip("{").strip(),
                                docstring_summary=_get_js_doc_summary(lines, i),
                                parent_symbol="",
                            )
                        )

                if "{" in line:
                    brace_depth += line.count("{") - line.count("}")
                continue

            # Track brace level
            opens = line.count("{")
            closes = line.count("}")

            if current_class and class_brace_level != -1 and (brace_depth + opens - closes) <= class_brace_level:
                if closes > opens and brace_depth <= class_brace_level + 1:
                    current_class = ""
                    class_brace_level = -1

            # Class method
            if current_class and brace_depth >= class_brace_level + 1:
                method_match = method_regex.search(line)
                if method_match:
                    name = method_match.group(1)
                    if name not in ("if", "for", "while", "switch", "catch", "return", "throw", "constructor"):
                        params = method_match.group(2) if method_match.lastindex and method_match.lastindex >= 2 else ""

                        if kind_filter in (SymbolKind.ALL, SymbolKind.METHOD):
                            if not pattern_lower or pattern_lower in name.lower():
                                symbols.append(
                                    SymbolLocationDTO(
                                        name=name,
                                        kind=SymbolKind.METHOD,
                                        filepath=filepath,
                                        start_line=i,
                                        end_line=i,
                                        signature=f"{name}({params.strip()})",
                                        docstring_summary=_get_js_doc_summary(lines, i),
                                        parent_symbol=current_class,
                                    )
                                )
                        brace_depth += opens - closes
                        continue

            # Standalone function / Arrow function
            func_match = func_regex.search(line) or arrow_func_regex.search(line)
            if func_match:
                name = func_match.group(1)
                params = func_match.group(2) if func_match.lastindex and func_match.lastindex >= 2 else ""

                if kind_filter in (SymbolKind.ALL, SymbolKind.FUNCTION):
                    if not pattern_lower or pattern_lower in name.lower():
                        symbols.append(
                            SymbolLocationDTO(
                                name=name,
                                kind=SymbolKind.FUNCTION,
                                filepath=filepath,
                                start_line=i,
                                end_line=i,
                                signature=f"function {name}({params.strip()})",
                                docstring_summary=_get_js_doc_summary(lines, i),
                                parent_symbol="",
                            )
                        )

            brace_depth += opens - closes

        return tuple(symbols)


def extract_js_ts_symbols_from_file(
    filepath: str,
    name_pattern: str = "",
    kind_filter: SymbolKind = SymbolKind.ALL,
) -> tuple[SymbolLocationDTO, ...]:
    """Convenience helper delegating to JsTsSymbolParser.

    Args:
        filepath (str): Target JS/TS file path.
        name_pattern (str): Name pattern filter.
        kind_filter (SymbolKind): Symbol category filter.

    Returns:
        tuple[SymbolLocationDTO, ...]: Discovered symbol locations.
    """
    return JsTsSymbolParser().parse_symbols(filepath, name_pattern, kind_filter)


def _get_js_doc_summary(lines: list[str], line_no: int) -> str:
    """Extract docstring/JSDoc summary from preceding comment lines.

    Args:
        lines (list[str]): File lines.
        line_no (int): 1-indexed target line number.

    Returns:
        str: JSDoc summary or empty string.
    """
    if line_no <= 1:
        return ""

    prev_idx = line_no - 2
    prev_line = lines[prev_idx].strip()

    if prev_line.startswith("//"):
        return prev_line.lstrip("/").strip()

    if prev_line.endswith("*/"):
        summary_lines: list[str] = []
        while prev_idx >= 0:
            l = lines[prev_idx].strip()
            clean = l.lstrip("/*").rstrip("*/").strip()
            if clean and not clean.startswith("@"):
                summary_lines.insert(0, clean)
            if "/*" in l:
                break
            prev_idx -= 1
        return summary_lines[0] if summary_lines else ""

    return ""
