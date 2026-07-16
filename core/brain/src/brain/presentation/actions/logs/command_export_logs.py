# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to export DB-backed workspace logs."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import os
from dataclasses import asdict
from pathlib import Path

# Application Modules Imports
from brain.application.logs.export_service import export_logs_files, export_logs_markdown, export_logs_zip, normalize_export_filters
from brain.application.logs.store import list_log_entries
from brain.presentation.terminal import log_step, render_placeholders


WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "."))


def handle(args: argparse.Namespace) -> int:
    """Export logs to stdout, files, or zip."""
    color_enabled = getattr(args, "color", False)
    try:
        workspace_root = Path(WORKSPACE_ROOT).resolve()
        zip_path = getattr(args, "zip", None)
        files_mode = bool(getattr(args, "files", False))
        stdout_mode = bool(getattr(args, "stdout", False))
        output_path = getattr(args, "output", None)
        filter_kwargs = {
            "domain": getattr(args, "domain", None),
            "date_text": getattr(args, "date", None),
            "time_text": getattr(args, "time", None),
            "from_text": getattr(args, "from", None),
            "to_text": getattr(args, "to", None),
        }

        selected_modes = sum((bool(zip_path), files_mode, stdout_mode))
        if selected_modes > 1:
            msg = "__RED__Error: select only one export target: --stdout, --files, or --zip PATH.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1
        if selected_modes == 0:
            stdout_mode = True
        if output_path and not files_mode:
            msg = "__RED__Error: --output can only be used with --files.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        if zip_path:
            print(render_placeholders("__YELLOW__Warning: persistent exports are migration artifacts only; never use them as an internal content source.__RESET__", color_enabled))
            log_step(args, "Exporting DB-backed logs to zip...")
            result = export_logs_zip(
                workspace_root=workspace_root,
                output_path=_resolve_workspace_path(workspace_root=workspace_root, raw_path=str(zip_path)),
                **filter_kwargs,
            )
            msg = f"__GREEN__Exported {result.files_written} log files to {result.output_path}.__RESET__"
            print(render_placeholders(msg, color_enabled))
            args.json_payload = {
                "ok": True,
                "command": "export-logs",
                "mode": "zip",
                "filesWritten": result.files_written,
                "outputPath": result.output_path.as_posix(),
                "filters": filter_kwargs,
            }
            return 0

        if files_mode:
            print(render_placeholders("__YELLOW__Warning: persistent exports are migration artifacts only; never use them as an internal content source.__RESET__", color_enabled))
            log_step(args, "Exporting DB-backed logs to files...")
            output_dir = _resolve_workspace_path(workspace_root=workspace_root, raw_path=str(output_path)) if output_path else None
            result = export_logs_files(workspace_root=workspace_root, output_dir=output_dir, **filter_kwargs)
            msg = f"__GREEN__Exported {result.files_written} log files to {result.output_path}.__RESET__"
            print(render_placeholders(msg, color_enabled))
            args.json_payload = {
                "ok": True,
                "command": "export-logs",
                "mode": "files",
                "filesWritten": result.files_written,
                "outputPath": result.output_path.as_posix(),
                "filters": filter_kwargs,
            }
            return 0

        print(export_logs_markdown(workspace_root=workspace_root, **filter_kwargs), end="")
        filters = normalize_export_filters(
            date_text=filter_kwargs["date_text"],
            time_text=filter_kwargs["time_text"],
            from_text=filter_kwargs["from_text"],
            to_text=filter_kwargs["to_text"],
        )
        entries = list_log_entries(
            workspace_root=workspace_root,
            date_text=filters["date_text"],
            time_text=filters["time_text"],
            domain=filter_kwargs["domain"],
            from_sort=filters["from_sort"],
            to_sort=filters["to_sort"],
            newest_first=True,
        )
        args.json_payload = {
            "ok": True,
            "command": "export-logs",
            "mode": "stdout",
            "filters": filter_kwargs,
            "count": len(entries),
            "entries": [asdict(entry) for entry in entries],
        }
        return 0

    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1


def _resolve_workspace_path(workspace_root: Path, raw_path: str) -> Path:
    """Resolve a user-supplied path relative to the workspace root."""
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return workspace_root / path
