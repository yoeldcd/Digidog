"""Export DB-backed workspace logs for external consumers."""

from __future__ import annotations

# Standard Libraries Imports
import datetime
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

# Application Modules Imports
from brain.application.logs.parsing import log_file_name
from brain.application.logs.records import LogEntryRecord, render_log_file
from brain.application.logs.entry_formatting import normalize_log_time
from brain.application.logs.store import list_log_entries, rendered_logs_index


@dataclass(frozen=True)
class ExportLogsResult:
    """Result for file or zip log exports."""

    files_written: int
    output_path: Path


def export_logs_markdown(
    workspace_root: Path,
    domain: str | None = None,
    date_text: str | None = None,
    time_text: str | None = None,
    from_text: str | None = None,
    to_text: str | None = None,
) -> str:
    """
    Export logs as a single Markdown stream for stdout consumers.

    Args:
        workspace_root (Path): Workspace root.
        domain (str | None): Optional domain prefix filter.
        date_text (str | None): Optional exact date filter.
        time_text (str | None): Optional exact minute filter.
        from_text (str | None): Optional inclusive lower timestamp/date bound.
        to_text (str | None): Optional inclusive upper timestamp/date bound.

    Returns:
        str: Markdown containing grouped daily entries.
    """
    filters = normalize_export_filters(
        date_text=date_text,
        time_text=time_text,
        from_text=from_text,
        to_text=to_text,
    )
    entries: list[LogEntryRecord] = list_log_entries(
        workspace_root=workspace_root,
        date_text=filters["date_text"],
        time_text=filters["time_text"],
        domain=domain,
        from_sort=filters["from_sort"],
        to_sort=filters["to_sort"],
        newest_first=True,
    )
    active_domain: str = domain or "all"
    active_time: str = export_filter_label(filters=filters)
    title_suffix: str = f" ({active_time})" if active_time else ""
    lines: list[str] = [f"# Agent Tech Logs for {active_domain}{title_suffix}", ""]
    if not entries:
        lines.append("No matching log entries were found.")
        return "\n".join(lines).strip() + "\n"

    for entry in entries:
        lines.append(render_export_entry(entry=entry))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def export_logs_files(
    workspace_root: Path,
    output_dir: Path | None = None,
    domain: str | None = None,
    date_text: str | None = None,
    time_text: str | None = None,
    from_text: str | None = None,
    to_text: str | None = None,
) -> ExportLogsResult:
    """
    Export DB-backed logs as canonical Markdown files.

    Args:
        workspace_root (Path): Workspace root.
        output_dir (Path | None): Destination directory. Defaults to `$agent/logs`.
        domain (str | None): Optional domain prefix filter.
        date_text (str | None): Optional exact date filter.
        time_text (str | None): Optional exact minute filter.
        from_text (str | None): Optional inclusive lower timestamp/date bound.
        to_text (str | None): Optional inclusive upper timestamp/date bound.

    Returns:
        ExportLogsResult: Export summary.
    """
    resolved_output_dir: Path = output_dir or workspace_root / "$agent" / "logs"
    filters = normalize_export_filters(
        date_text=date_text,
        time_text=time_text,
        from_text=from_text,
        to_text=to_text,
    )
    entries: list[LogEntryRecord] = list_log_entries(
        workspace_root=workspace_root,
        date_text=filters["date_text"],
        time_text=filters["time_text"],
        domain=domain,
        from_sort=filters["from_sort"],
        to_sort=filters["to_sort"],
    )
    files_written: int = write_log_files(output_dir=resolved_output_dir, entries=entries)
    index_path: Path = resolved_output_dir / "index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(rendered_logs_index(workspace_root=workspace_root), encoding="utf-8")
    return ExportLogsResult(files_written=files_written + 1, output_path=resolved_output_dir)


def export_logs_zip(
    workspace_root: Path,
    output_path: Path,
    domain: str | None = None,
    date_text: str | None = None,
    time_text: str | None = None,
    from_text: str | None = None,
    to_text: str | None = None,
) -> ExportLogsResult:
    """
    Export DB-backed logs as a zip archive of canonical Markdown files.

    Args:
        workspace_root (Path): Workspace root.
        output_path (Path): Destination zip path.
        domain (str | None): Optional domain prefix filter.
        date_text (str | None): Optional exact date filter.
        time_text (str | None): Optional exact minute filter.
        from_text (str | None): Optional inclusive lower timestamp/date bound.
        to_text (str | None): Optional inclusive upper timestamp/date bound.

    Returns:
        ExportLogsResult: Export summary.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir) / "logs"
        files_result = export_logs_files(
            workspace_root=workspace_root,
            output_dir=temp_root,
            domain=domain,
            date_text=date_text,
            time_text=time_text,
            from_text=from_text,
            to_text=to_text,
        )
        with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(temp_root.rglob("*")):
                if not file_path.is_file():
                    continue
                archive.write(file_path, file_path.relative_to(temp_root).as_posix())
    return ExportLogsResult(files_written=files_result.files_written, output_path=output_path)


def write_log_files(output_dir: Path, entries: list[LogEntryRecord]) -> int:
    """
    Write daily log Markdown files under an output directory.

    Args:
        output_dir (Path): Destination logs directory.
        entries (list[LogEntryRecord]): Entries to export.

    Returns:
        int: Number of daily files written.
    """
    entries_by_date: dict[str, list[LogEntryRecord]] = group_entries_by_date(entries=entries)
    written_count: int = 0
    for date_text, date_entries in entries_by_date.items():
        try:
            parsed_date = datetime.datetime.strptime(date_text, "%d-%m-%Y")
        except ValueError:
            month_dir = output_dir
        else:
            month_dir = output_dir / parsed_date.strftime("%Y-%m")
        file_path: Path = month_dir / log_file_name(date_text)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(render_log_file(date_text=date_text, entries=date_entries), encoding="utf-8")
        written_count += 1
    return written_count


def group_entries_by_date(entries: list[LogEntryRecord]) -> dict[str, list[LogEntryRecord]]:
    """
    Group entries by date in their current order.

    Args:
        entries (list[LogEntryRecord]): Entries to group.

    Returns:
        dict[str, list[LogEntryRecord]]: Entries keyed by DD-MM-YYYY.
    """
    entries_by_date: dict[str, list[LogEntryRecord]] = {}
    for entry in entries:
        date_text: str = entry.timestamp.split(" ")[0]
        entries_by_date.setdefault(date_text, []).append(entry)
    return entries_by_date


def render_export_entry(entry: LogEntryRecord) -> str:
    """
    Render one entry for the wiki-friendly stdout export stream.

    Args:
        entry (LogEntryRecord): Entry to render.

    Returns:
        str: Markdown entry without daily file preamble.
    """
    return "\n".join(
        [
            f"## {entry.timestamp}",
            f"### ({entry.domain}) [{entry.title}]",
            "  **Type:**",
            f"    {entry.change_type}",
            "  **Why:**",
            f"    {entry.why}",
            "  **Description**",
            indent_export_text(text=entry.description),
            "  **Impact**",
            indent_export_text(text=entry.impact),
        ],
    )


def indent_export_text(text: str) -> str:
    """Indent export body text using canonical log formatting."""
    return "\n".join(f"    {line}" for line in text.splitlines())


def normalize_export_filters(
    date_text: str | None = None,
    time_text: str | None = None,
    from_text: str | None = None,
    to_text: str | None = None,
) -> dict[str, str | None]:
    """Normalize CLI-facing date/time filters for SQL queries."""
    normalized_date = normalize_date_filter(date_text) if date_text else None
    normalized_time = normalize_time_filter(time_text) if time_text else None
    from_sort = normalize_timestamp_bound(raw_text=from_text, end_of_day=False) if from_text else None
    to_sort = normalize_timestamp_bound(raw_text=to_text, end_of_day=True) if to_text else None
    return {
        "date_text": normalized_date,
        "time_text": normalized_time,
        "from_sort": from_sort,
        "to_sort": to_sort,
    }


def normalize_date_filter(raw_text: str) -> str:
    """Normalize DD-MM-YYYY or YYYY-MM-DD dates to DD-MM-YYYY."""
    value = raw_text.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(value, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    raise ValueError("Date filters must follow DD-MM-YYYY or YYYY-MM-DD.")


def normalize_time_filter(raw_text: str) -> str:
    """Normalize HH:MM with optional am/pm to HH:MM."""
    match = re.match(r"^(\d{1,2}:\d{2})(?:\s*([ap]m))?$", raw_text.strip(), flags=re.IGNORECASE)
    if match is None:
        raise ValueError("Time filters must follow HH:MM with optional am/pm.")
    return normalize_log_time(match.group(1), match.group(2) or "")


def normalize_timestamp_bound(raw_text: str, end_of_day: bool) -> str:
    """Normalize an inclusive date or timestamp bound to timestamp_sort format."""
    value = raw_text.strip()
    date_part = value
    time_part: str | None = None
    if " " in value:
        date_part, time_part = value.split(" ", 1)
    normalized_date = normalize_date_filter(date_part)
    parsed_date = datetime.datetime.strptime(normalized_date, "%d-%m-%Y")
    if time_part:
        normalized_time = normalize_time_filter(time_part)
    else:
        normalized_time = "23:59" if end_of_day else "00:00"
    hour_text, minute_text = normalized_time.split(":", 1)
    return parsed_date.replace(hour=int(hour_text), minute=int(minute_text), second=0).strftime("%Y-%m-%d %H:%M:%S")


def export_filter_label(filters: dict[str, str | None]) -> str:
    """Return a compact human-readable label for active timing filters."""
    parts = []
    if filters["date_text"]:
        parts.append(f"date {filters['date_text']}")
    if filters["time_text"]:
        parts.append(f"time {filters['time_text']}")
    if filters["from_sort"]:
        parts.append(f"from {filters['from_sort']}")
    if filters["to_sort"]:
        parts.append(f"to {filters['to_sort']}")
    return ", ".join(parts)
