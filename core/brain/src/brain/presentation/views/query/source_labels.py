"""Source label helpers for global query terminal views."""

from __future__ import annotations

# Standard Libraries Imports
import re

# Application Modules Imports
from brain.application.querying.dtos import GlobalQueryResultDTO


def source_kind(result: GlobalQueryResultDTO) -> str:
    """
    Return the coarse reader-facing source kind.

    Args:
        result (GlobalQueryResultDTO): Result to inspect.

    Returns:
        str: diary, log, or memory.
    """
    source_type: str = result.source_ref.source_type.casefold()
    path: str = result.source_ref.path.replace("\\", "/")
    if source_type == "diary" or "/diary/" in path or path.startswith("memory/diary/"):
        return "diary"
    if (
        source_type in ("workspace_logs", "logs", "log")
        or "/logs/" in path
        or path.startswith("$agent/logs/")
        or path == "$agent/database/brain_logs.db"
    ):
        return "log"
    return "memory"


def source_title(result: GlobalQueryResultDTO) -> str:
    """
    Return a compact source title without duplicating the read command.

    Args:
        result (GlobalQueryResultDTO): Result to inspect.

    Returns:
        str: Source title.
    """
    title_text: str = result.source_ref.title or result.title or ""
    if result.source_ref.read_command.startswith("read-profile "):
        return result.source_ref.read_command.replace("read-profile ", "", 1).strip()
    return clean_heading_title(title=title_text)


def clean_heading_title(title: str) -> str:
    """
    Remove Markdown heading markers and entry timestamps from titles.

    Args:
        title (str): Raw title.

    Returns:
        str: Compact title.
    """
    clean_title: str = title.strip().lstrip("#").strip()
    timestamp_match = re.match(
        r"\d{2}-\d{2}-\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]m)?\s+-\s+(.+)",
        clean_title,
        flags=re.IGNORECASE,
    )
    if timestamp_match:
        return timestamp_match.group(1).strip()
    bracket_match = re.search(r"\[([^\]]+)\]\s*$", clean_title)
    if bracket_match:
        return bracket_match.group(1).strip()
    return clean_title


def source_fence_language(result: GlobalQueryResultDTO) -> str:
    """
    Return a Markdown fence language from the source file type.

    Args:
        result (GlobalQueryResultDTO): Result to inspect.

    Returns:
        str: Fence language.
    """
    path: str = result.source_ref.path.casefold()
    if path.endswith(".py"):
        return "python"
    if path.endswith(".js"):
        return "javascript"
    if path.endswith(".json"):
        return "json"
    if path.endswith(".toml"):
        return "toml"
    if path.endswith(".yaml") or path.endswith(".yml"):
        return "yaml"
    if path.endswith(".md") or path.endswith(".log.md") or path.endswith("brain_logs.db") or not path:
        return "md"
    return ""


def knowledge_scope_suffix(result: GlobalQueryResultDTO) -> str:
    """
    Return a compact knowledge scope suffix for graph results.

    Args:
        result (GlobalQueryResultDTO): Result to inspect.

    Returns:
        str: Empty string or bracketed scope text.
    """
    if result.source != "knowledge":
        return ""
    scope_name: str = str(result.data.get("knowledge_scope") or "")
    if not scope_name:
        return ""
    return f" [{scope_name}]"
