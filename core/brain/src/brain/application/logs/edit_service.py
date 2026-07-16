# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application service for editing DB-backed workspace log entries."""

from __future__ import annotations

# Standard Libraries Imports
from dataclasses import dataclass
from pathlib import Path

# Application Modules Imports
from brain.application.logs.entry_formatting import normalize_log_type, parse_log_entry_date, read_log_command
from brain.application.logs.records import LogEntryRecord
from brain.application.logs.store import (
    get_log_entry_by_timestamp,
    source_path_from_date,
    update_log_entry_by_timestamp,
)


class EditLogError(ValueError):
    """Raised when a log entry cannot be edited."""


@dataclass(frozen=True)
class EditLogRequest:
    """Input contract for editing one workspace log entry."""

    timestamp: str
    log_domain: str | None = None
    title: str | None = None
    change_type: str | None = None
    why: str | None = None
    description: str | None = None
    impact: str | None = None


@dataclass(frozen=True)
class EditLogResult:
    """Result contract for editing one workspace log entry."""

    log_file: Path
    timestamp: str
    read_command: str


def edit_log_entry(workspace_root: Path, request: EditLogRequest) -> EditLogResult:
    """
    Edit one DB-backed log entry and refresh the SQLite latest-index projection.

    Args:
        workspace_root (Path): Workspace root containing `$agent`.
        request (EditLogRequest): Entry timestamp and optional replacement values.

    Returns:
        EditLogResult: Edited log metadata.
    """
    timestamp: str = request.timestamp.strip()
    if not timestamp:
        raise EditLogError("Datetime must be provided via --datetime or compact positional form.")
    parse_log_entry_date(timestamp=timestamp)

    stored_entry: LogEntryRecord | None = get_log_entry_by_timestamp(workspace_root=workspace_root, timestamp=timestamp)
    if stored_entry is None:
        raise EditLogError(f"No log entry found matching timestamp '{timestamp}'.")

    replacement = LogEntryRecord(
        timestamp=stored_entry.timestamp,
        domain=_replacement_value(current=stored_entry.domain, replacement=request.log_domain),
        title=_replacement_value(current=stored_entry.title, replacement=request.title),
        change_type=(
            normalize_log_type(change_type=request.change_type)
            if request.change_type is not None
            else stored_entry.change_type
        ),
        why=_replacement_value(current=stored_entry.why, replacement=request.why),
        description=_replacement_value(current=stored_entry.description, replacement=request.description),
        impact=_replacement_value(current=stored_entry.impact, replacement=request.impact),
        source_path=stored_entry.source_path or source_path_from_date(date_text=stored_entry.timestamp.split(" ")[0]),
        source_mtime=stored_entry.source_mtime,
        source_size=stored_entry.source_size,
    )
    updated_id = update_log_entry_by_timestamp(
        workspace_root=workspace_root,
        timestamp=timestamp,
        replacement=replacement,
    )
    if updated_id is None:
        raise EditLogError(f"No log entry found matching timestamp '{timestamp}'.")

    return EditLogResult(
        log_file=workspace_root / replacement.source_path,
        timestamp=replacement.timestamp,
        read_command=read_log_command(timestamp=replacement.timestamp),
    )


def _replacement_value(current: str, replacement: str | None) -> str:
    """Return a stripped replacement value when provided, else the current value."""
    if replacement is None:
        return current
    return replacement.strip()
