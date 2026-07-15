"""Formatting helpers for canonical workspace log entries."""

from __future__ import annotations

# Standard Libraries Imports
import datetime
import re


VALID_LOG_TYPES = (
    "feature",
    "fix",
    "refactor",
    "performance",
    "improvement",
    "documentation",
    "maintenance",
)
"""Allowed changelog entry types."""


def valid_log_types_text() -> str:
    """Return the canonical log types in their documented display order."""
    return ", ".join(VALID_LOG_TYPES)


def indent_text(text: str) -> str:
    """
    Indent lines by 4 spaces for canonical log sections.

    Args:
        text (str): Section text.

    Returns:
        str: Indented section text.
    """
    return "\n".join("    " + line for line in text.splitlines())


def normalize_log_type(change_type: str) -> str:
    """
    Validate and normalize a changelog type.

    Args:
        change_type (str): Raw changelog type.

    Returns:
        str: Normalized changelog type.
    """
    normalized_type = change_type.lower().strip()
    if normalized_type not in VALID_LOG_TYPES:
        valid_values = valid_log_types_text()
        raise ValueError(f"Invalid type '{change_type}'. Must be one of: {valid_values}")
    return normalized_type


def resolve_log_timestamp(timestamp: str | None = None) -> str:
    """
    Return a canonical log timestamp.

    Args:
        timestamp (str | None): Optional timestamp override.

    Returns:
        str: Timestamp in `DD-MM-YYYY HH:mm am/pm` shape.
    """
    if timestamp:
        return timestamp.strip()
    now = datetime.datetime.now()
    time_part = now.strftime("%I:%M").lower()
    ampm_part = now.strftime("%p").lower()
    return f"{now.strftime('%d-%m-%Y')} {time_part} {ampm_part}"


def parse_log_entry_date(timestamp: str) -> datetime.datetime:
    """
    Parse the date prefix from a canonical log timestamp.

    Args:
        timestamp (str): Log timestamp.

    Returns:
        datetime.datetime: Parsed date at midnight.
    """
    date_part = timestamp.split(" ")[0]
    try:
        return datetime.datetime.strptime(date_part, "%d-%m-%Y")
    except ValueError as exc:
        raise ValueError("Datetime must start with date in format DD-MM-YYYY.") from exc


def build_log_entry_text(
    timestamp: str,
    log_domain: str,
    title: str,
    change_type: str,
    why: str,
    description: str,
    impact: str,
) -> str:
    """
    Build one canonical Markdown log entry.

    Args:
        timestamp (str): Entry timestamp.
        log_domain (str): Changelog domain.
        title (str): Entry title.
        change_type (str): Normalized changelog type.
        why (str): Reason for the change.
        description (str): Change description.
        impact (str): Change impact.

    Returns:
        str: Markdown log entry.
    """
    return f"""## {timestamp}
### ({log_domain}) [{title}]
  **Type:**
    {change_type}
  **Why:**
    {why.strip()}
  **Description**
{indent_text(description.strip())}
  **Impact**
{indent_text(impact.strip())}"""


def read_log_command(timestamp: str) -> str:
    """
    Return the abstract CLI reader command for a log timestamp.

    Args:
        timestamp (str): Log timestamp.

    Returns:
        str: Read command for the log entry.
    """
    date_text = timestamp.split(" ")[0]
    time_match = re.search(r"\b(\d{1,2}:\d{2})(?:\s*([ap]m))?\b", timestamp, flags=re.IGNORECASE)
    if time_match is None:
        return f"read-log -d {date_text}"
    time_text = normalize_log_time(time_match.group(1), time_match.group(2) or "")
    return f"read-log -d {date_text} --time {time_text}"


def normalize_log_time(time_text: str, ampm: str = "") -> str:
    """
    Normalize a clock time to HH:MM.

    Args:
        time_text (str): Raw time text.
        ampm (str): Optional am/pm suffix.

    Returns:
        str: 24-hour HH:MM text.
    """
    hour_text, minute_text = time_text.split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text[:2])
    normalized_ampm = ampm.casefold().strip()
    if normalized_ampm == "pm" and hour < 12:
        hour += 12
    elif normalized_ampm == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"
