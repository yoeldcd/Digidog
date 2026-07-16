# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to migrate workspace logs into SQLite and refresh the DB index."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import os
from pathlib import Path

# Application Modules Imports
from brain.application.logs.index_service import migrate_legacy_log_files_to_database, migrate_log_files_to_database
from brain.application.logs.store import get_logs_database_path, log_database_summary
from brain.presentation.terminal import log_step, render_placeholders


WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "."))


def _log_update_step(args: argparse.Namespace, message: str) -> None:
    """Print one update-log-index progress step, optionally under a parent task."""
    log_step(args, message, task=getattr(args, "log_task", None))


def handle(args: argparse.Namespace) -> int:
    """Import file-backed logs into SQLite and rebuild the latest-index projection."""
    color_enabled = getattr(args, "color", False)
    verbose_enabled = getattr(args, "verbose_log", False)
    try:
        workspace_root = Path(WORKSPACE_ROOT).resolve()
        mode = getattr(args, "mode", None)
        if mode is not None and mode.lower() != "fix":
            msg = "__RED__Error: update-log-index compact mode must be 'fix'.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        should_fix = getattr(args, "fix", False) or (mode is not None and mode.lower() == "fix")
        imported_legacy: list[str] = []
        archive_errors: list[str] = []
        if should_fix:
            _log_update_step(args, "[1/3] Importing legacy log files into SQLite...")
            imported_legacy = migrate_legacy_log_files_to_database(
                workspace_root=workspace_root,
                archive_sources=True,
                archive_errors=archive_errors,
            )
            if imported_legacy:
                for path in imported_legacy:
                    if verbose_enabled:
                        msg = f"__CYAN__Imported legacy source: {path}__RESET__"
                        print(render_placeholders(msg, color_enabled))
            else:
                if verbose_enabled:
                    msg = "__YELLOW__No legacy .md/.log log files found to import.__RESET__"
                    print(render_placeholders(msg, color_enabled))
        else:
            _log_update_step(args, "[1/3] Checking canonical log files...")

        _log_update_step(args, "[2/3] Importing canonical logs into SQLite and archiving originals...")
        imported_paths = migrate_log_files_to_database(
            workspace_root=workspace_root,
            archive_sources=True,
            archive_errors=archive_errors,
        )
        if verbose_enabled:
            if imported_paths:
                for path in imported_paths:
                    msg = f"__CYAN__Imported canonical source: {path}__RESET__"
                    print(render_placeholders(msg, color_enabled))
            else:
                msg = "__DIM__No canonical .log.md files needed import.__RESET__"
                print(render_placeholders(msg, color_enabled))

        for warning in archive_errors:
            msg = f"__YELLOW__Warning: imported but could not archive raw log source {warning}__RESET__"
            print(render_placeholders(msg, color_enabled))

        _log_update_step(args, "[3/3] Refreshing SQLite latest-index projection...")
        if verbose_enabled:
            database_path = get_logs_database_path(workspace_root=workspace_root)
            msg = f"__CYAN__Refreshed DB projection: {database_path.as_posix()}::log_index_latest__RESET__"
            print(render_placeholders(msg, color_enabled))
        entry_count, domain_count, latest_count = log_database_summary(workspace_root=workspace_root)

        msg = (
            "__GREEN__Logs database projection refreshed: "
            f"{entry_count} entries, {domain_count} domains, {latest_count} indexed latest rows"
            f" ({len(imported_paths) + len(imported_legacy)} source files imported"
            f", {len(archive_errors)} archive warnings).__RESET__"
        )
        print(render_placeholders(msg, color_enabled))
        args.json_payload = {
            "ok": True,
            "command": "update-log-index",
            "database": get_logs_database_path(workspace_root=workspace_root).as_posix(),
            "entries": entry_count,
            "domains": domain_count,
            "latestRows": latest_count,
            "imported": imported_legacy + imported_paths,
            "archiveWarnings": archive_errors,
        }
        return 0

    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
