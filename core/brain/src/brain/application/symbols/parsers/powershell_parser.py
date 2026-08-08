# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""PowerShell symbol parser implementation."""

from __future__ import annotations

import os
import re

from brain.application.symbols.parsers.base_parser import BaseSymbolParser
from brain.domain.symbols.models import SymbolKind, SymbolLocationDTO


class PowerShellSymbolParser(BaseSymbolParser):
    """Concrete symbol parser strategy for PowerShell (.ps1, .psm1) script files."""

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """Return tuple of supported PowerShell file extensions.

        Returns:
            tuple[str, ...]: ('.ps1', '.psm1')
        """
        return (".ps1", ".psm1")

    @property
    def language_name(self) -> str:
        """Return lower-case language identifier.

        Returns:
            str: 'powershell'
        """
        return "powershell"

    def parse_symbols(
        self,
        filepath: str,
        name_pattern: str = "",
        kind_filter: SymbolKind = SymbolKind.ALL,
    ) -> tuple[SymbolLocationDTO, ...]:
        """Parse a PowerShell file (.ps1) and extract matching function and filter symbols.

        Args:
            filepath (str): Target PowerShell file path.
            name_pattern (str): Name pattern filter (case-insensitive).
            kind_filter (SymbolKind): Symbol category filter.

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

        # Regex matching function or filter definitions
        func_regex = re.compile(r"^\s*(?:function|filter)\s+([A-Za-z0-9_\-\:\.]+)(?:\s*\(([^)]*)\))?", re.IGNORECASE)

        for i, line in enumerate(lines, 1):
            match = func_regex.search(line)
            if match:
                name = match.group(1)
                params = match.group(2) or ""

                if kind_filter in (SymbolKind.ALL, SymbolKind.FUNCTION):
                    if not pattern_lower or pattern_lower in name.lower():
                        summary = _get_ps1_comment_summary(lines, i)
                        sig = f"function {name}({params.strip()})" if params else f"function {name}"

                        symbols.append(
                            SymbolLocationDTO(
                                name=name,
                                kind=SymbolKind.FUNCTION,
                                filepath=filepath,
                                start_line=i,
                                end_line=i,
                                signature=sig,
                                docstring_summary=summary,
                                parent_symbol="",
                            )
                        )

        return tuple(symbols)


def extract_powershell_symbols_from_file(
    filepath: str,
    name_pattern: str = "",
    kind_filter: SymbolKind = SymbolKind.ALL,
) -> tuple[SymbolLocationDTO, ...]:
    """Convenience helper delegating to PowerShellSymbolParser.

    Args:
        filepath (str): Target PowerShell file path.
        name_pattern (str): Name pattern filter.
        kind_filter (SymbolKind): Symbol category filter.

    Returns:
        tuple[SymbolLocationDTO, ...]: Discovered symbol locations.
    """
    return PowerShellSymbolParser().parse_symbols(filepath, name_pattern, kind_filter)


def _get_ps1_comment_summary(lines: list[str], line_no: int) -> str:
    """Extract doc comment summary above function definition.

    Args:
        lines (list[str]): Source lines.
        line_no (int): 1-indexed target line number.

    Returns:
        str: Comment summary or empty string.
    """
    if line_no <= 1:
        return ""

    prev_idx = line_no - 2
    comment_lines: list[str] = []

    while prev_idx >= 0:
        line = lines[prev_idx].strip()
        if line.startswith("#"):
            clean = line.lstrip("#").strip()
            if clean and not clean.startswith(".SYNOPSIS") and not clean.startswith(".DESCRIPTION"):
                comment_lines.insert(0, clean)
            prev_idx -= 1
        else:
            break

    return comment_lines[0] if comment_lines else ""
