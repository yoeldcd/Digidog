"""Action module to read the DB-backed workspace logs index."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import os
from dataclasses import asdict
from pathlib import Path

# Application Modules Imports
from brain.application.logs.index_service import migrate_legacy_log_files_to_database, migrate_log_files_to_database
from brain.application.logs.store import list_log_entries, log_database_summary, rendered_logs_index
from brain.presentation.terminal import log_step, render_markdown, render_placeholders


WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "."))


def handle(args: argparse.Namespace) -> int:
    """Render the latest-entry log index from SQLite."""
    color_enabled = getattr(args, "color", False)
    try:
        log_step(args, "Reading DB-backed logs index...")
        workspace_root = Path(WORKSPACE_ROOT).resolve()

        entry_count, _domain_count, _latest_count = log_database_summary(workspace_root=workspace_root)
        if entry_count == 0:
            migrate_legacy_log_files_to_database(workspace_root=workspace_root, archive_sources=False)
            migrate_log_files_to_database(workspace_root=workspace_root, archive_sources=False)

        content = rendered_logs_index(workspace_root=workspace_root)
        all_entries = list_log_entries(workspace_root=workspace_root, newest_first=True)
        latest_by_domain = {}
        for entry in all_entries:
            latest_by_domain.setdefault(entry.domain, entry)
        entries = list(latest_by_domain.values())
        if args.section:
            section = args.section.strip().casefold()
            entries = [entry for entry in entries if entry.domain.casefold().startswith(section)]
        args.json_payload = {
            "ok": True,
            "command": "log-index",
            "section": args.section,
            "count": len(entries),
            "entries": [asdict(entry) for entry in entries],
        }

        if not args.section:
            print(render_markdown(content, color_enabled))
            return 0

        target_header = f"## {args.section.strip()}"
        lines = content.splitlines()
        output_lines = []
        in_section = False

        for line in lines:
            if line.strip().startswith("## "):
                if line.strip().lower() == target_header.lower():
                    in_section = True
                    output_lines.append(line)
                elif in_section:
                    break
            elif in_section:
                output_lines.append(line)

        if not output_lines:
            msg = f"__YELLOW__Domain section '{args.section}' not found in logs index.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 0

        print(render_markdown("\n".join(output_lines).strip(), color_enabled))
        return 0

    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
