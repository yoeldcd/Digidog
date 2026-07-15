"""Direct Markdown text-result mapping and excerpt helpers."""

from __future__ import annotations

# Standard Libraries Imports
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# Application Modules Imports
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO, QuerySourceRefDTO
from brain.application.querying.language import normalize_query_text
from brain.application.querying.source_refs import (
    resolve_stable_source_path,
    source_read_command_from_path,
    source_ref_from_path,
    source_type_from_memory_path,
    title_from_source_path,
)


DATED_SOURCE_ENTRY_RE = re.compile(
    r"^##\s+(?P<date>\d{2}-\d{2}-\d{4})\s+"
    r"(?P<time>\d{1,2}:\d{2})(?::\d{2})?"
    r"(?:\s*(?P<ampm>[ap]m))?"
    r"(?:\s+-\s+(?P<title>.+))?\s*$",
    re.IGNORECASE,
)
"""Markdown heading pattern for dated diary/log entries."""


def build_memory_text_result(
    markdown_path: Path,
    memory_root: Path,
    content: str,
    line: str,
    line_number: int,
    matches: list[tuple[str, int, int]],
    rank: float,
) -> GlobalQueryResultDTO:
    """
    Build a normalized direct Markdown text query result.

    Args:
        markdown_path (Path): Matched Markdown file.
        memory_root (Path): Memory root directory.
        content (str): Full Markdown file content.
        line (str): Matched line.
        line_number (int): One-based matched line number.
        matches (list[tuple[str, int, int]]): Fuzzy match spans.
        rank (float): Backend rank.

    Returns:
        GlobalQueryResultDTO: Normalized direct text result.
    """
    relative_path: str = markdown_path.relative_to(memory_root).as_posix()
    title: str = relative_path[:-3] if relative_path.endswith(".md") else relative_path
    entry_metadata: dict[str, str] = source_entry_metadata_from_content(
        path=relative_path,
        content=content,
        line_number=line_number,
    )
    if entry_metadata.get("entry_title"):
        title = entry_metadata["entry_title"]
    excerpt: str = context_window_from_lines(
        lines=content.splitlines(),
        line_number=line_number,
        radius=2,
    )
    excerpt = remove_dated_entry_headings(text=excerpt)
    data: dict[str, Any] = {
        "path": relative_path,
        "line_number": line_number,
        "line": line,
        "excerpt": excerpt,
        "matches": [match[0] for match in matches],
        **entry_metadata,
    }
    source_ref: QuerySourceRefDTO = source_ref_from_path(
        path=f"memory/{relative_path}",
        source_type=source_type_from_memory_path(relative_path),
        line_number=line_number,
        entry_time=entry_metadata.get("entry_time", ""),
        entry_title=entry_metadata.get("entry_title", ""),
    )
    return GlobalQueryResultDTO(
        source="memory",
        mechanism="text",
        kind="text_memory",
        rank=rank,
        title=title,
        text=excerpt,
        data=data,
        content=QueryContentDTO(
            title=title,
            excerpt=excerpt,
            body=excerpt,
            location=f"line {line_number}",
        ),
        source_ref=source_ref,
    )


def context_window_from_lines(lines: list[str], line_number: int, radius: int = 2) -> str:
    """
    Return a compact context window around one line.

    Args:
        lines (list[str]): Source lines.
        line_number (int): One-based center line number.
        radius (int): Number of surrounding lines.

    Returns:
        str: Context window.
    """
    center_index: int = max(0, line_number - 1)
    start_index: int = max(0, center_index - radius)
    end_index: int = min(len(lines), center_index + radius + 1)
    return "\n".join(lines[start_index:end_index]).strip()


def source_entry_metadata_from_content(path: str, content: str, line_number: int) -> dict[str, str]:
    """
    Infer dated-entry metadata around a matched source line.

    Args:
        path (str): Memory-relative source path.
        content (str): Full source content.
        line_number (int): One-based matched line number.

    Returns:
        dict[str, str]: Entry title, date, time, and reader command metadata.
    """
    clean_path: str = path.replace("\\", "/").strip()
    if not clean_path.startswith("diary/"):
        return {}

    lines: list[str] = content.splitlines()
    start_index: int = min(max(line_number - 1, 0), max(len(lines) - 1, 0))
    for index in range(start_index, -1, -1):
        match: re.Match[str] | None = DATED_SOURCE_ENTRY_RE.match(lines[index].strip())
        if match is None:
            continue
        entry_time: str = normalize_source_entry_time(
            time_text=match.group("time") or "",
            ampm=match.group("ampm") or "",
        )
        date_text: str = match.group("date") or ""
        read_command: str = source_read_command_from_path(
            path=f"memory/{clean_path}",
            entry_time=entry_time,
        )
        return {
            "entry_date": date_text,
            "entry_time": entry_time,
            "entry_title": (match.group("title") or title_from_source_path(path=clean_path)).strip(),
            "read_command": read_command,
        }
    return {}


def normalize_source_entry_time(time_text: str, ampm: str = "") -> str:
    """Normalize a heading time to HH:MM."""
    clean_time: str = time_text.strip()
    clean_ampm: str = ampm.casefold().strip()
    if not clean_time:
        return ""
    try:
        if clean_ampm:
            return datetime.strptime(f"{clean_time} {clean_ampm}", "%I:%M %p").strftime("%H:%M")
        return datetime.strptime(clean_time, "%H:%M").strftime("%H:%M")
    except ValueError:
        return clean_time[:5]


def remove_dated_entry_headings(text: str) -> str:
    """Remove dated entry headings from a display excerpt."""
    return "\n".join(
        line
        for line in text.splitlines()
        if DATED_SOURCE_ENTRY_RE.match(line.strip()) is None
    ).strip()


def read_source_excerpt(source_path: str, query_text: str, fallback_terms: list[str]) -> str:
    """
    Read a short excerpt from a source file.

    Args:
        source_path (str): Stable source path.
        query_text (str): Query text.
        fallback_terms (list[str]): Extra terms to locate context.

    Returns:
        str: Source excerpt.
    """
    resolved_path: Path | None = resolve_stable_source_path(source_path=source_path)
    if resolved_path is None or not resolved_path.exists() or not resolved_path.is_file():
        return ""
    try:
        content: str = resolved_path.read_text(encoding="utf-8")
    except Exception:
        return ""
    lines: list[str] = content.splitlines()
    tokens: list[str] = [
        token
        for token in normalize_query_text(value=" ".join([query_text, *fallback_terms])).split()
        if len(token) > 1
    ]
    for line_index, line in enumerate(lines, 1):
        normalized_line: str = normalize_query_text(value=line)
        if any(token in normalized_line for token in tokens):
            return context_window_from_lines(lines=lines, line_number=line_index, radius=3)
    return compact_excerpt(text=content, limit=900)


def compact_excerpt(text: str, limit: int = 900) -> str:
    """Return a bounded excerpt while preserving useful line boundaries."""
    compact_text: str = "\n".join(
        " ".join(line.split())
        for line in text.splitlines()
        if line.strip()
    )
    if len(compact_text) <= limit:
        return compact_text
    return f"{compact_text[:max(0, limit - 1)].rstrip()}..."
