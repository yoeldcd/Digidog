"""Action module to edit existing entries in the diary."""

from __future__ import annotations

import argparse
import datetime
import re
from pathlib import Path
from brain.application.memory.paths import resolve_file_path
from brain.application.memory.service import write_instance
from brain.presentation.terminal import render_placeholders, log_step



def handle(args: argparse.Namespace) -> int:
    """Edit an existing diary entry."""
    color_enabled = getattr(args, "color", False)
    log_step(args, '[1/3] Parsing inputs...')
    try:
        timestamp = args.datetime if args.datetime is not None else args.timestamp
        if timestamp is None:
            msg = "__RED__Error: Datetime must be provided via --datetime or compact positional form.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1
        dt_str = timestamp.strip()

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
        year_month = dt.strftime("%Y-%m")
        category = f"diary.{year_month}"
        key = date_str

        # Resolve path
        file_path = resolve_file_path(category, key)

        if not file_path.exists():
            msg = f"__RED__Error: No diary file found for date {date_str}.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        content = file_path.read_text(encoding="utf-8")

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

        if full_timestamp_str not in entries:
            msg = f"__RED__Error: No entry found with timestamp '{full_timestamp_str}'.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        # Extract current entry
        log_step(args, '[2/3] Editing entry...')
        curr_title, curr_text = entries[full_timestamp_str]

        # Apply edits
        if getattr(args, "title", None) is not None:
            curr_title = args.title.strip()

        if getattr(args, "replace", None) is not None:
            if getattr(args, "with_text", None) is None:
                msg = "__RED__Error: --with-text is required when using --replace.__RESET__"
                print(render_placeholders(msg, color_enabled))
                return 1
            # Replace literally
            curr_text = curr_text.replace(args.replace, args.with_text)

        if getattr(args, "append", None) is not None:
            curr_text = curr_text + "\n\n" + args.append.strip()

        compact_body = getattr(args, "body", None)
        if getattr(args, "text", None) is not None:
            curr_text = args.text.strip()
        elif compact_body is not None:
            curr_text = compact_body.strip()

        entries[full_timestamp_str] = (curr_title, curr_text)

        # Sort chronologically
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
            lines.append("")  # Blank line below header
            lines.append(t_body)
            lines.append("")
        new_content = "\n".join(lines).strip() + "\n"

        # Save via store
        log_step(args, '[3/3] Writing changes...')
        write_instance(category, key, new_content)

        # Rebuild index
        from brain.application.memory.indexing.index_service import build_full_index
        build_full_index()

        msg = f"__GREEN__Successfully edited diary entry__RESET__ for '__CYAN__{full_timestamp_str}__RESET__'."
        print(render_placeholders(msg, color_enabled))
        args.json_payload = {
            "ok": True,
            "command": "edit-diary",
            "entry": {
                "timestamp": full_timestamp_str,
                "date": date_str,
                "title": curr_title,
                "text": curr_text,
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
