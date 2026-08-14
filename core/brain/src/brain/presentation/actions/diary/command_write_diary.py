# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Write timestamped diary entries through the memory persistence boundary.

The action validates CLI input, merges legacy and new entries, and rebuilds canonical Markdown.
It keeps one root authorization marker at the document boundary so authorization metadata remains
deterministic while the diary body and established CLI output contract remain unchanged.
"""

from __future__ import annotations

import argparse
import datetime
import re
from pathlib import Path
from brain.application.memory.paths import ensure_memory_root, resolve_file_path
from brain.application.memory.service import write_instance
from brain.presentation.terminal import render_placeholders, log_step


_ROOT_AUTHORIZATION_HEADER: str = "<!-- Authorized: root -->"


def handle(args: argparse.Namespace) -> int:
    """Normalize, merge, and persist one timestamped diary entry.

    This command boundary preserves legacy content and deterministic chronological ordering while
    rebuilding the single root authorization marker before storage. It converts validation and
    persistence failures into the established CLI status and output contract.

    Args:
        args (argparse.Namespace): Parsed command options containing the diary
            text, optional title, timestamp, and output settings.

    Returns:
        int: Zero when the entry is saved; otherwise one after reporting an input
            or storage error.
    """
    color_enabled = getattr(args, "color", False)

    # Command safety boundary: convert unexpected validation/storage failures into the established CLI error result.

    try:
        log_step(args, '[1/2] Parsing inputs...')

        # Text source selection: honor explicit --text before compact positional body input.
        text = args.text if args.text is not None else args.body

        # Input contract: reject missing diary text before deriving storage metadata.

        if text is None:
            msg = "__RED__Error: Diary text must be provided via --text or compact positional form.__RESET__"
            print(render_placeholders(msg, color_enabled))

            return 1
        title = getattr(args, "title", "").strip()
        dt_str = args.datetime

        # Timestamp selection: default to local time only when the caller omits the option.

        if not dt_str:
            now = datetime.datetime.now()
            dt_str = now.strftime("%d-%m-%Y %H:%M:%S")

        # Explicit timestamp path: trim caller input before recognizing the HH:MM shorthand.

        else:
            dt_str = dt_str.strip()

            # Short-form normalization: append seconds only to a complete date/time value.

            if len(dt_str.split(" ")) == 2:
                time_part = dt_str.split(" ")[1]

                # Precision normalization: expand HH:MM to HH:MM:SS without changing full timestamps.

                if len(time_part.split(":")) == 2:
                    dt_str += ":00"

        # Timestamp parsing boundary: isolate format errors so invalid input cannot reach persistence.

        try:
            dt = datetime.datetime.strptime(dt_str, "%d-%m-%Y %H:%M:%S")

        # Invalid timestamp branch: preserve the CLI message and stop before any storage write.

        except ValueError:
            msg = "__RED__Error: Datetime must follow format DD-MM-YYYY HH:MM:SS or DD-MM-YYYY HH:MM.__RESET__"
            print(render_placeholders(msg, color_enabled))

            return 1

        date_str = dt.strftime("%d-%m-%Y")
        full_timestamp_str = dt.strftime("%d-%m-%Y %H:%M:%S")

        # Storage identity: derive the diary category and daily key from the normalized timestamp.
        year_month = dt.strftime("%Y-%m")

        category = f"diary.{year_month}"
        key = date_str

        # Storage lookup: resolve the target file before reading existing or legacy content.
        file_path = resolve_file_path(category, key)

        # Existence probe: select the read path while keeping the missing-file branch empty.
        file_exists = file_path.exists()

        # Existing-file branch: preserve prior Markdown so entries can be merged in place.

        if file_exists:
            content = file_path.read_text(encoding="utf-8")

        # Missing-file branch: initialize an empty source for the first canonical rewrite.

        else:
            content = ""

        # Authorization invariant: remove historical markers before emitting exactly one canonical
        # root marker, preventing duplicate or displaced root authorization metadata.
        has_authorization_header = True

        # Authorization cleanup: filter old markers before parsing so none can be duplicated.
        content_lines = [
            line for line in content.splitlines() if line.strip() != _ROOT_AUTHORIZATION_HEADER
        ]
        content = "\n".join(content_lines)

        # Parser state: collect Markdown sections before replacing the requested timestamp key.
        entries = {}
        current_time = None
        current_title = ""
        current_text_lines = []

        # Section scan: inspect every stored line to preserve all existing entry bodies.

        for line in content.splitlines():

            # Header branch: start a new entry when a Markdown level-two header is encountered.

            if line.startswith("## "):

                # Commit branch: finalize the previous section before replacing parser state.

                if current_time:
                    entries[current_time] = (current_title, "\n".join(current_text_lines).strip())

                header_text = line[3:].strip()
                m = re.match(r'^(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})(?:\s*-\s*(.*))?$', header_text)

                # Timestamp-header branch: preserve recognized timestamps and optional titles.

                if m:
                    current_time = m.group(1)

                    # Title parsing: retain a present suffix and normalize absent titles to empty text.
                    current_title = m.group(2).strip() if m.group(2) else ""

                # Legacy-header branch: retain nonconforming header text instead of dropping data.

                else:
                    current_time = header_text
                    current_title = ""
                current_text_lines = []

            # Body branch: retain lines only after a header establishes an active entry.

            elif current_time is not None:
                current_text_lines.append(line)

        # Final-section branch: flush the last entry after iteration has no following header.

        if current_time:
            entries[current_time] = (current_title, "\n".join(current_text_lines).strip())

        # Upsert invariant: replace only the requested timestamp while retaining other entries.
        entries[full_timestamp_str] = (title, text.strip())

        # Sorting boundary: use parsed timestamps while keeping malformed legacy keys deterministic.

        def get_dt_key(k_str: str) -> datetime.datetime:
            """Convert a persisted diary key into a sorting timestamp.

            This helper keeps valid timestamps chronological and maps malformed legacy keys to
            datetime.min so rewriting remains deterministic without raising for old content.

            Args:
                k_str (str): Stored timestamp string from the diary entry map.

            Returns:
                datetime.datetime: Parsed timestamp, or the minimum datetime when
                the stored value is malformed.
            """

            # Sort-key parsing: convert valid persisted timestamps before applying the fallback.

            try:
                return datetime.datetime.strptime(k_str, "%d-%m-%Y %H:%M:%S")

            # Legacy-key fallback: use the minimum timestamp so malformed data remains sortable.

            except ValueError:
                return datetime.datetime.min

        sorted_keys = sorted(entries.keys(), key=get_dt_key)

        # Document assembly: rebuild canonical Markdown from the sorted entries and target date.
        lines = [f"# Diary - {date_str}", ""]

        # Authorization output invariant: prepend one root marker at the document boundary.

        if has_authorization_header:
            lines = [_ROOT_AUTHORIZATION_HEADER, ""] + lines

        # Serialization loop: emit each retained entry in chronological order with Markdown spacing.

        for k_str in sorted_keys:
            t_title, t_body = entries[k_str]

            # Title serialization: omit the delimiter when an entry has no title.
            title_part = f" - {t_title}" if t_title else ""
            lines.append(f"## {k_str}{title_part}")

            # Markdown spacing: keep a blank line below each level-two header for MD022 compliance.
            lines.append("")
            lines.append(t_body)
            lines.append("")
        new_content = "\n".join(lines).strip() + "\n"

        # Persistence boundary: write the complete document only after parsing and assembly succeed.
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

    # Failure branch: render unexpected errors through the existing CLI channel and return failure.

    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))

        return 1
