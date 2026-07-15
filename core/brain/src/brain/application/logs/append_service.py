"""Application service for appending canonical workspace log entries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Application Modules Imports
from brain.application.logs.entry_formatting import (
    normalize_log_type,
    read_log_command,
    resolve_log_timestamp,
)
from brain.application.logs.records import LogEntryRecord
from brain.application.logs.store import insert_log_entry, source_path_from_date


class AppendLogError(ValueError):
    """Raised when a log entry cannot be appended."""


@dataclass(frozen=True)
class AppendLogRequest:
    """Input contract for appending one workspace log entry."""

    log_domain: str
    title: str
    change_type: str
    why: str
    description: str
    impact: str
    timestamp: str | None = None


@dataclass(frozen=True)
class AppendLogResult:
    """Result contract for appending one workspace log entry."""

    log_file: Path
    timestamp: str
    read_command: str


def append_log_entry(workspace_root: Path, request: AppendLogRequest) -> AppendLogResult:
    """
    Append one canonical log entry to the DB-backed log store.

    Args:
        workspace_root (Path): Workspace root containing `$agent/logs`.
        request (AppendLogRequest): Entry input values.

    Returns:
        AppendLogResult: Written log metadata.
    """
    timestamp: str = resolve_log_timestamp(timestamp=request.timestamp)
    change_type: str = normalize_log_type(change_type=request.change_type)
    date_part = timestamp.split(" ")[0]
    source_path: str = source_path_from_date(date_text=date_part)
    log_file: Path = workspace_root / source_path
    insert_log_entry(
        workspace_root=workspace_root,
        entry=LogEntryRecord(
            timestamp=timestamp,
            domain=request.log_domain.strip(),
            title=request.title.strip(),
            change_type=change_type,
            why=request.why.strip(),
            description=request.description.strip(),
            impact=request.impact.strip(),
            source_path=source_path,
        ),
    )
    return AppendLogResult(
        log_file=log_file,
        timestamp=timestamp,
        read_command=read_log_command(timestamp=timestamp),
    )
