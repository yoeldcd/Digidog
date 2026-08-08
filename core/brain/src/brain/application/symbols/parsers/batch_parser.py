# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Windows Batch symbol parser implementation."""

from __future__ import annotations

import os
import re

from brain.application.symbols.parsers.base_parser import BaseSymbolParser
from brain.domain.symbols.models import SymbolKind, SymbolLocationDTO


class BatchSymbolParser(BaseSymbolParser):
    """Concrete symbol parser strategy for Windows Batch (.bat, .cmd) script files."""

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """Return tuple of supported Batch file extensions.

        Returns:
            tuple[str, ...]: ('.bat', '.cmd')
        """
        return (".bat", ".cmd")

    @property
    def language_name(self) -> str:
        """Return lower-case language identifier.

        Returns:
            str: 'batch'
        """
        return "batch"

    def parse_symbols(
        self,
        filepath: str,
        name_pattern: str = "",
        kind_filter: SymbolKind = SymbolKind.ALL,
    ) -> tuple[SymbolLocationDTO, ...]:
        """Parse a Windows Batch file (.bat, .cmd) and extract label procedure symbols.

        Args:
            filepath (str): Target Batch file path.
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

        # Regex matching label definitions (:LabelName)
        label_regex = re.compile(r"^\s*:([A-Za-z0-9_\-\.]+)", re.IGNORECASE)

        for i, line in enumerate(lines, 1):
            match = label_regex.search(line)
            if match:
                name = match.group(1)

                # Filter out special labels like EOF or comment-style labels
                if name.lower() in ("eof", "", "end"):
                    continue

                if kind_filter in (SymbolKind.ALL, SymbolKind.FUNCTION):
                    if not pattern_lower or pattern_lower in name.lower():
                        summary = _get_batch_rem_summary(lines, i)

                        symbols.append(
                            SymbolLocationDTO(
                                name=name,
                                kind=SymbolKind.FUNCTION,
                                filepath=filepath,
                                start_line=i,
                                end_line=i,
                                signature=f":{name}",
                                docstring_summary=summary,
                                parent_symbol="",
                            )
                        )

        return tuple(symbols)


def extract_batch_symbols_from_file(
    filepath: str,
    name_pattern: str = "",
    kind_filter: SymbolKind = SymbolKind.ALL,
) -> tuple[SymbolLocationDTO, ...]:
    """Convenience helper delegating to BatchSymbolParser.

    Args:
        filepath (str): Target Batch file path.
        name_pattern (str): Name pattern filter.
        kind_filter (SymbolKind): Symbol category filter.

    Returns:
        tuple[SymbolLocationDTO, ...]: Discovered symbol locations.
    """
    return BatchSymbolParser().parse_symbols(filepath, name_pattern, kind_filter)


def _get_batch_rem_summary(lines: list[str], line_no: int) -> str:
    """Extract REM / :: comment summary above label definition.

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
        if line.lower().startswith("rem ") or line.startswith("::"):
            clean = line[4:].strip() if line.lower().startswith("rem ") else line[2:].strip()
            if clean:
                comment_lines.insert(0, clean)
            prev_idx -= 1
        else:
            break

    return comment_lines[0] if comment_lines else ""
