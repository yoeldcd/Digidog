"""Row mapping for source registry records."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
from pathlib import Path

# Application Modules Imports
from brain.domain.sources.models import SourceRegistryRecordDTO


def row_to_record(
    sqlite_row: sqlite3.Row | None = None,
    *,
    row: sqlite3.Row | None = None,
    active: bool,
) -> SourceRegistryRecordDTO:
    """
    Convert a SQLite source row into a DTO.

    Args:
        sqlite_row: Source row.
        row: Source row alias for call-site readability.
        active: Active-state fallback.

    Returns:
        Source registry record.
    """
    source_row: sqlite3.Row = row if row is not None else sqlite_row  # type: ignore[assignment]
    return SourceRegistryRecordDTO(
        id=int(source_row["id"]) if "id" in source_row.keys() and source_row["id"] is not None else None,
        path=str(source_row["path"]),
        mtime=float(source_row["mtime"]),
        size=str(source_row["size_label"] or "0KB"),
        lines=str(source_row["line_count_label"] or "0"),
        entries=int(source_row["entry_count"] or 0),
        source_type=str(source_row["source_type"]),
        title=str(source_row["title"] or Path(str(source_row["path"])).stem),
        active=active,
    )
