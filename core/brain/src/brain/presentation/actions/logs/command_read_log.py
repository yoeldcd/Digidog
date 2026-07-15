"""Action module to read entries from the DB-backed workspace logs."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import datetime
import os
import re
from dataclasses import asdict
from pathlib import Path

# Application Modules Imports
from brain.application.logs.index_service import migrate_legacy_log_files_to_database, migrate_log_files_to_database
from brain.application.logs.records import LogEntryRecord, render_log_file
from brain.application.logs.store import list_log_entries
from brain.presentation.terminal import log_step, render_markdown, render_placeholders


WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "."))


def handle(args: argparse.Namespace) -> int:
    """Read log entries."""
    log_step(args, "Reading log entries...")
    color_enabled = getattr(args, "color", False)
    try:
        workspace_root = Path(WORKSPACE_ROOT).resolve()
        dt_str = args.datetime if args.datetime is not None else args.date
        if not dt_str:
            dt_str = datetime.datetime.now().strftime("%d-%m-%Y")
        day_str = _normalize_date_text(dt_str=dt_str.strip())
        time_filter = getattr(args, "time", None)
        normalized_time = _normalize_time_filter(str(time_filter)) if time_filter else None

        entries: list[LogEntryRecord] = list_log_entries(
            workspace_root=workspace_root,
            date_text=day_str,
            time_text=normalized_time,
        )
        if not entries:
            migrate_legacy_log_files_to_database(workspace_root=workspace_root, archive_sources=False)
            migrate_log_files_to_database(workspace_root=workspace_root, archive_sources=False)
            entries = list_log_entries(
                workspace_root=workspace_root,
                date_text=day_str,
                time_text=normalized_time,
            )

        if not entries:
            suffix = f" at {normalized_time}" if normalized_time else ""
            msg = f"__RED__No log entry found for date {day_str}{suffix}.__RESET__"
            print(render_placeholders(msg, color_enabled))
            args.json_payload = {
                "ok": True,
                "command": "read-log",
                "date": day_str,
                "time": normalized_time,
                "count": 0,
                "entries": [],
            }
            return 0

        content = render_log_file(date_text=day_str, entries=entries)
        limit = getattr(args, "limit", None)
        if limit is not None:
            text_lines = content.splitlines()
            if len(text_lines) > limit:
                rest = len(text_lines) - limit
                content = "\n".join(text_lines[:limit]) + f"\n\n__DIM__... {rest} more lines__RESET__"

        print(render_markdown(content, color_enabled), end="")
        args.json_payload = {
            "ok": True,
            "command": "read-log",
            "date": day_str,
            "time": normalized_time,
            "count": len(entries),
            "entries": [asdict(entry) for entry in entries],
        }
        return 0
    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1


def _normalize_date_text(dt_str: str) -> str:
    """
    Normalize a date argument to DD-MM-YYYY.

    Args:
        dt_str (str): Raw date text.

    Returns:
        str: DD-MM-YYYY date text.
    """
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(dt_str, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    raise ValueError("Date must follow format DD-MM-YYYY or YYYY-MM-DD.")


def _normalize_time_filter(time_text: str) -> str:
    """
    Normalize a time filter to HH:MM.

    Args:
        time_text (str): Raw time filter.

    Returns:
        str: HH:MM.
    """
    match = re.match(r"^(\d{1,2}):(\d{2})(?:\s*([ap]m))?$", time_text.strip(), flags=re.IGNORECASE)
    if match is None:
        raise ValueError("Time must follow format HH:MM.")
    hour = int(match.group(1))
    minute = int(match.group(2))
    ampm = (match.group(3) or "").casefold()
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"
