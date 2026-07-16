# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to write entries to the diary."""

from __future__ import annotations

import argparse
import datetime
import re
from pathlib import Path
from brain.application.memory.paths import ensure_memory_root, resolve_file_path
from brain.application.memory.service import write_instance
from brain.presentation.terminal import render_placeholders, log_step



def handle(args: argparse.Namespace) -> int:
    """Write or update diary entry."""
    color_enabled = getattr(args, "color", False)
    try:
        log_step(args, '[1/2] Parsing inputs...')
        text = args.text if args.text is not None else args.body
        if text is None:
            msg = "__RED__Error: Diary text must be provided via --text or compact positional form.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1
        title = getattr(args, "title", "").strip()
        dt_str = args.datetime

        # Determine datetime
        if not dt_str:
            now = datetime.datetime.now()
            dt_str = now.strftime("%d-%m-%Y %H:%M:%S")
        else:
            dt_str = dt_str.strip()
            # Support parsing either HH:MM or HH:MM:SS
            if len(dt_str.split(" ")) == 2:
                time_part = dt_str.split(" ")[1]
                if len(time_part.split(":")) == 2:
                    dt_str += ":00"

        try:
            dt = datetime.datetime.strptime(dt_str, "%d-%m-%Y %H:%M:%S")
        except ValueError:
            msg = "__RED__Error: Datetime must follow format DD-MM-YYYY HH:MM:SS or DD-MM-YYYY HH:MM.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        date_str = dt.strftime("%d-%m-%Y")
        full_timestamp_str = dt.strftime("%d-%m-%Y %H:%M:%S")

        # Category/key parts
        year_month = dt.strftime("%Y-%m") # YYYY-MM

        category = f"diary.{year_month}"
        key = date_str

        # Resolve path
        file_path = resolve_file_path(category, key)

        # Read existing content if file exists
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
        else:
            content = ""

        # Parse existing entries
        entries = {}
        current_time = None
        current_title = ""
        current_text_lines = []
        for line in content.splitlines():
            if line.startswith("## "):
                if current_time:
                    entries[current_time] = (current_title, "\n".join(current_text_lines).strip())
                header_text = line[3:].strip()
                m = re.match(r'^(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})(?:\s*-\s*(.*))?$', header_text)
                if m:
                    current_time = m.group(1)
                    current_title = m.group(2).strip() if m.group(2) else ""
                else:
                    current_time = header_text
                    current_title = ""
                current_text_lines = []
            elif current_time is not None:
                current_text_lines.append(line)
        if current_time:
            entries[current_time] = (current_title, "\n".join(current_text_lines).strip())

        # Add or update the entry
        entries[full_timestamp_str] = (title, text.strip())

        # Sort chronologically by parsing keys back to datetime
        def get_dt_key(k_str: str) -> datetime.datetime:
            try:
                return datetime.datetime.strptime(k_str, "%d-%m-%Y %H:%M:%S")
            except ValueError:
                return datetime.datetime.min

        sorted_keys = sorted(entries.keys(), key=get_dt_key)

        # Compose content
        lines = [f"# Diary - {date_str}", ""]
        for k_str in sorted_keys:
            t_title, t_body = entries[k_str]
            title_part = f" - {t_title}" if t_title else ""
            lines.append(f"## {k_str}{title_part}")
            lines.append("")  # Blank line below header for MD022 compliance
            lines.append(t_body)
            lines.append("")
        new_content = "\n".join(lines).strip() + "\n"

        # Save via store write_instance
        log_step(args, '[2/2] Writing diary entry...')
        write_instance(category, key, new_content)

        msg = f"__GREEN__Saved diary entry__RESET__ for '__CYAN__{full_timestamp_str}__RESET__'."
        print(render_placeholders(msg, color_enabled))
        args.json_payload = {
            "ok": True,
            "command": "write-diary",
            "entry": {
                "timestamp": full_timestamp_str,
                "date": date_str,
                "title": title,
                "text": text.strip(),
                "domain": category,
                "key": key,
                "path": file_path.as_posix(),
            },
        }
        return 0
    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
