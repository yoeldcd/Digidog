# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to read entries from the diary."""

from __future__ import annotations

import argparse
import datetime
import re
from brain.application.memory.paths import resolve_file_path
from brain.presentation.terminal import render_placeholders, render_markdown, log_step



def handle(args: argparse.Namespace) -> int:
    """Read diary entries."""
    log_step(args, 'Reading diary entries...')
    color_enabled = getattr(args, "color", False)
    try:
        dt_str = args.datetime if args.datetime is not None else args.date

        # Determine date
        if not dt_str:
            now = datetime.datetime.now()
            dt_str = now.strftime("%d-%m-%Y")

        try:
            dt = datetime.datetime.strptime(dt_str.strip(), "%d-%m-%Y")
        except ValueError:
            msg = "__RED__Error: Date must follow format DD-MM-YYYY.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        year_month = dt.strftime("%Y-%m") # YYYY-MM

        category = f"diary.{year_month}"
        key = dt.strftime("%d-%m-%Y")

        # Resolve path
        file_path = resolve_file_path(category, key)

        if not file_path.exists():
            msg = f"__RED__No diary entry found for date {dt_str}.__RESET__"
            print(render_placeholders(msg, color_enabled))
            args.json_payload = {
                "ok": True,
                "command": "read-diary",
                "date": dt.strftime("%d-%m-%Y"),
                "count": 0,
                "entries": [],
            }
            return 0

        content = file_path.read_text(encoding="utf-8")
        time_filter = getattr(args, "time", None)
        if time_filter:
            content = _filter_entry_by_time(
                content=content,
                date_text=dt.strftime("%d-%m-%Y"),
                time_text=str(time_filter),
            )
            if not content:
                msg = f"__RED__No diary entry found for date {dt_str} at {time_filter}.__RESET__"
                print(render_placeholders(msg, color_enabled))
                args.json_payload = {
                    "ok": True,
                    "command": "read-diary",
                    "date": dt.strftime("%d-%m-%Y"),
                    "time": str(time_filter),
                    "count": 0,
                    "entries": [],
                }
                return 0
        entries = _parse_diary_entries(content=content)
        limit = getattr(args, "limit", None)
        if limit is not None:
            text_lines = content.splitlines()
            if len(text_lines) > limit:
                rest = len(text_lines) - limit
                content = "\n".join(text_lines[:limit]) + f"\n\n__DIM__... {rest} more lines__RESET__"

        print(render_markdown(content, color_enabled), end="")
        args.json_payload = {
            "ok": True,
            "command": "read-diary",
            "date": dt.strftime("%d-%m-%Y"),
            "time": str(time_filter) if time_filter else None,
            "count": len(entries),
            "entries": entries,
        }
        return 0
    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1


def _filter_entry_by_time(content: str, date_text: str, time_text: str) -> str:
    """
    Return the entry matching a date and exact HH:MM time.

    Args:
        content (str): Diary Markdown content.
        date_text (str): Date in DD-MM-YYYY.
        time_text (str): Time in HH:MM.

    Returns:
        str: Matching entry block or empty string.
    """
    normalized_time: str = _normalize_time_filter(time_text=time_text)
    entry_blocks: list[str] = re.split(r"(?=^##\s+)", content, flags=re.MULTILINE)
    for block in entry_blocks:
        first_line: str = block.splitlines()[0].strip() if block.splitlines() else ""
        match = re.match(rf"^##\s+{re.escape(date_text)}\s+(\d{{1,2}}:\d{{2}})(?::\d{{2}})?\s+-", first_line)
        if match is None:
            continue
        if _normalize_time_filter(match.group(1)) == normalized_time:
            title_line = content.splitlines()[0] if content.startswith("# ") else f"# Diary - {date_text}"
            return f"{title_line.rstrip()}\n\n{block.strip()}\n"
    return ""


def _parse_diary_entries(content: str) -> list[dict[str, str]]:
    """Parse diary Markdown into semantic entry payloads."""
    entries: list[dict[str, str]] = []
    blocks = re.split(r"(?=^##\s+)", content, flags=re.MULTILINE)
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines or not lines[0].startswith("## "):
            continue
        match = re.match(r"^##\s+(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})(?:\s+-\s+(.*))?$", lines[0])
        if match is None:
            continue
        entries.append({
            "timestamp": match.group(1),
            "title": (match.group(2) or "").strip(),
            "text": "\n".join(lines[1:]).strip(),
        })
    return entries


def _normalize_time_filter(time_text: str) -> str:
    """
    Normalize a time filter to HH:MM.

    Args:
        time_text (str): Raw time filter.

    Returns:
        str: HH:MM.
    """
    match = re.match(r"^(\d{1,2}):(\d{2})", time_text.strip())
    if match is None:
        raise ValueError("Time must follow format HH:MM.")
    return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
