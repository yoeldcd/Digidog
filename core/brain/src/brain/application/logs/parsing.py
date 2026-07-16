# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Workspace log filename, timestamp, and entry parsing helpers."""

from __future__ import annotations

# Standard Libraries Imports
import datetime
import re
from pathlib import Path


STANDARD_LOG_SUFFIX = ".log.md"
"""Canonical workspace log file suffix."""

LEGACY_STANDARD_LOG_SUFFIX = ".log"
"""Previous workspace log file suffix."""


def to_slug(s: str) -> str:
    """Normalize a domain name to lowercase-hyphenated slug format."""
    normalized = s.strip().lower().replace("`", "")
    normalized = re.sub(r"(?<=\d)\.(?=\d)", "-", normalized)
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"[^a-z0-9_.-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    normalized = re.sub(r"\.+", ".", normalized)
    return normalized.strip(".-") or "unknown"


def log_file_name(date_str: str) -> str:
    """Return the canonical log filename for a DD-MM-YYYY date."""
    return f"{date_str}{STANDARD_LOG_SUFFIX}"


def log_date_stem(path: Path) -> str:
    """Return the date stem from canonical and legacy log filenames."""
    name = path.name
    if name.endswith(STANDARD_LOG_SUFFIX):
        return name[: -len(STANDARD_LOG_SUFFIX)]
    return path.stem


def is_canonical_log_file(path: Path) -> bool:
    """Return true when path uses the canonical `.log.md` suffix."""
    return path.name.casefold().endswith(STANDARD_LOG_SUFFIX)


def is_previous_log_file(path: Path) -> bool:
    """Return true when path uses the previous `.log` suffix."""
    return path.suffix.casefold() == LEGACY_STANDARD_LOG_SUFFIX


def parse_entry(timestamp: str, body_text: str) -> tuple[str, str, str]:
    """Parse log domain, title, and type from a canonical log entry body."""
    del timestamp
    domain = "unknown"
    title = "Untitled Change"

    header_match = re.search(r"^### \(([^)]+)\)\s*\[([^\]]+)\]", body_text, re.MULTILINE)
    if header_match:
        domain = to_slug(header_match.group(1))
        title = header_match.group(2).strip()

    type_match = re.search(r"\*\*Type:\*\*\s*\n?\s*([a-zA-Z0-9_\-]+)", body_text, re.IGNORECASE)
    git_type = type_match.group(1).strip().lower() if type_match else "feature"

    return domain, title, git_type


def parse_log_timestamp(ts_str: str) -> datetime.datetime:
    """Parse a canonical or legacy log timestamp."""
    ts_str = ts_str.strip().lower()
    ts_str = re.sub(r"\s+", " ", ts_str)
    for fmt in ("%d-%m-%Y %I:%M %p", "%d-%m-%Y %H:%M", "%d-%m-%Y %I:%M%p", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    date_match = re.search(r"(\d{2})-(\d{2})-(\d{4})", ts_str)
    if date_match:
        try:
            return datetime.datetime.strptime(date_match.group(0), "%d-%m-%Y")
        except ValueError:
            pass
    return datetime.datetime.min


def log_read_command(date_stem: str, entry_ts: str) -> str:
    """Return the CLI command that reads the indexed log entry."""
    parsed_dt = parse_log_timestamp(entry_ts)
    if parsed_dt == datetime.datetime.min:
        return f"read-log -d {date_stem}"
    return f"read-log -d {date_stem} --time {parsed_dt.strftime('%H:%M')}"


def glob_log_and_md_files(logs_dir: Path) -> list[Path]:
    """Return candidate log files in stable order."""
    paths: dict[str, Path] = {}
    for pattern in ("*.log.md", "*.log", "*.md"):
        for path in logs_dir.rglob(pattern):
            if not path.is_file() or path.name == "index.md":
                continue
            paths[path.resolve().as_posix()] = path
    return sorted(paths.values())
