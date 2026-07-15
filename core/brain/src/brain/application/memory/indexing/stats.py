"""Memory file statistics helpers."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path


def scan_file_stats(path: Path) -> tuple[str, str, int]:
    """
    Compute source stats for one file when the registry is not current.

    Args:
        path: Source file path.

    Returns:
        tuple[str, str, int]: Size, line count, and entry count labels.
    """
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return "0KB", "0", 0
    lines = content.splitlines()
    entries = sum(1 for line in lines if is_entry_line(line=line))
    size_bytes = path.stat().st_size
    return format_size(size_bytes=size_bytes), format_line_count(line_count=len(lines)), entries


def is_entry_line(line: str) -> bool:
    """Return whether a line should count as a lightweight source entry."""
    stripped_line = line.strip()
    if stripped_line.startswith("#"):
        return True
    if not stripped_line.startswith(("-", "*", "+")):
        return False
    marker_text = stripped_line[1:].strip()
    return marker_text.startswith("**") and ":" in marker_text


def format_size(size_bytes: int) -> str:
    """Return a compact byte-size label."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    return f"{size_bytes / 1024:.1f}KB"


def format_line_count(line_count: int) -> str:
    """Return a compact line-count label."""
    if line_count >= 1_000_000:
        return f"{line_count / 1_000_000:.1f}M"
    if line_count >= 1_000:
        return f"{line_count / 1_000:.1f}K"
    if line_count >= 100:
        return f"{line_count / 100:.1f}H"
    return str(line_count)


_scan_file_stats = scan_file_stats
_is_entry_line = is_entry_line
_format_size = format_size
_format_line_count = format_line_count
