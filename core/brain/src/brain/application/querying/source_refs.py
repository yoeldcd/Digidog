"""Stable source-reference and reader-command helpers for query results."""

from __future__ import annotations

# Standard Libraries Imports
import os
import re
from pathlib import Path

# Application Modules Imports
from brain.application.querying.dtos import QuerySourceRefDTO


def source_ref_from_path(
    path: str,
    source_type: str = "",
    title: str = "",
    scope: str = "",
    line_number: int | None = None,
    entry_time: str = "",
    entry_title: str = "",
) -> QuerySourceRefDTO:
    """
    Build a structured source reference from a stable path.

    Args:
        path (str): Stable source path.
        source_type (str): Source family.
        title (str): Human-readable title.
        scope (str): Runtime scope.
        line_number (int | None): Optional line number.
        entry_time (str): Optional source-local entry time in HH:MM.
        entry_title (str): Optional source-local entry title.

    Returns:
        QuerySourceRefDTO: Structured source reference.
    """
    clean_path: str = path.replace("\\", "/").strip()
    return QuerySourceRefDTO(
        scope=scope,
        source_type=source_type,
        domain=source_domain_from_path(path=clean_path),
        read_command=source_read_command_from_path(path=clean_path, entry_time=entry_time),
        path=clean_path,
        title=entry_title or title or title_from_source_path(path=clean_path),
        structure=source_structure(path=clean_path),
        line_number=line_number,
    )


def source_structure(path: str) -> list[str]:
    """
    Return navigable source path segments.

    Args:
        path (str): Stable source path.

    Returns:
        list[str]: Human-readable path segments.
    """
    if not path:
        return []
    segments: list[str] = [
        segment
        for segment in path.replace("\\", "/").split("/")
        if segment
    ]
    if segments:
        segments[-1] = _strip_source_suffix(value=segments[-1])
    return segments


def _strip_source_suffix(value: str) -> str:
    """
    Strip known persisted source suffixes from one path segment.

    Args:
        value (str): Source path segment.

    Returns:
        str: Segment without storage suffix.
    """
    for suffix in (".log.md", ".md", ".log"):
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def source_domain_from_path(path: str) -> str:
    """
    Convert a stable source path into the user-facing memory/log domain.

    Args:
        path (str): Stable source path.

    Returns:
        str: Dot-notated logical domain.
    """
    clean_path: str = path.replace("\\", "/").strip().lstrip("/")
    if not clean_path:
        return ""
    segments: list[str] = source_structure(path=clean_path)
    if segments and segments[0] == "memory":
        segments = segments[1:]
    return ".".join(segment for segment in segments if segment)


def source_read_command_from_path(path: str, entry_time: str = "") -> str:
    """
    Return the CLI command that reads a stable source.

    Args:
        path (str): Stable source path.
        entry_time (str): Optional source-local entry time in HH:MM.

    Returns:
        str: Reader command or empty string when no command is known.
    """
    clean_path: str = path.replace("\\", "/").strip().lstrip("/")
    if not clean_path:
        return ""
    diary_command: str = _diary_read_command(path=clean_path, entry_time=entry_time)
    if diary_command:
        return diary_command
    log_command: str = _log_read_command(path=clean_path, entry_time=entry_time)
    if log_command:
        return log_command
    profile_command: str = _profile_read_command(path=clean_path)
    if profile_command:
        return profile_command
    if clean_path.startswith("memory/"):
        memory_domain: str = source_domain_from_path(path=clean_path)
        if memory_domain:
            return f'get-memory-entry "{memory_domain}"'
    return ""


def title_from_source_path(path: str) -> str:
    """
    Derive a readable title from a source path.

    Args:
        path (str): Stable source path.

    Returns:
        str: Title text.
    """
    structure: list[str] = source_structure(path=path)
    if not path:
        return ""
    return structure[-1] if structure else path


def source_type_from_memory_path(path: str) -> str:
    """
    Infer a memory source family from a path.

    Args:
        path (str): Memory-relative or stable path.

    Returns:
        str: Source type.
    """
    clean_path: str = path.replace("\\", "/").lstrip("/")
    if clean_path.startswith("memory/"):
        clean_path = clean_path.replace("memory/", "", 1)
    first_segment: str = clean_path.split("/", 1)[0] if clean_path else "memory"
    if first_segment == "diary":
        return "diary"
    if first_segment == "profiles":
        return "profiles"
    return "memory"


def resolve_stable_source_path(source_path: str) -> Path | None:
    """
    Resolve a stable source path into a local filesystem path.

    Args:
        source_path (str): Stable source path.

    Returns:
        Path | None: Filesystem path when resolvable.
    """
    clean_path: str = source_path.replace("\\", "/").strip()
    if not clean_path:
        return None
    from brain.infrastructure.runtime.paths import get_agent_home, get_workspace_root

    agent_home: Path = get_agent_home()
    workspace_root: Path = get_workspace_root()
    if clean_path.startswith("memory/"):
        return agent_home / clean_path
    if clean_path.startswith("$agent/"):
        return workspace_root / clean_path
    if clean_path.startswith("logs/"):
        return workspace_root / "$agent" / clean_path
    return agent_home / clean_path


def _diary_read_command(path: str, entry_time: str) -> str:
    """Return a diary reader command for a stable memory path."""
    match: re.Match[str] | None = re.search(r"(?:^|/)memory/diary/\d{4}-\d{2}/(\d{2}-\d{2}-\d{4})\.md$", path)
    if match is None:
        return ""
    time_text: str = f" --time {entry_time}" if entry_time else ""
    return f"read-diary -d {match.group(1)}{time_text}"


def _log_read_command(path: str, entry_time: str) -> str:
    """Return a log reader command for a stable log path."""
    match: re.Match[str] | None = re.search(
        r"(?:^|/)(?:\$agent/)?logs/\d{4}-\d{2}/(\d{2}-\d{2}-\d{4})(?:\.log)?(?:\.md)?$",
        path,
    )
    if match is None:
        return ""
    time_text: str = f" --time {entry_time}" if entry_time else ""
    return f"read-log -d {match.group(1)}{time_text}"


def _profile_read_command(path: str) -> str:
    """Return the profile reader command for a stable profile path."""
    file_match: re.Match[str] | None = re.search(r"(?:^|/)memory/profiles/([^/]+)\.md$", path)
    if file_match is not None:
        return f"read-profile {file_match.group(1)}"
    dir_match: re.Match[str] | None = re.search(r"(?:^|/)memory/profiles/([^/]+)/.+$", path)
    if dir_match is None:
        return ""
    return f"read-profile {dir_match.group(1)}"
