# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Workspace log index rebuild service."""

from __future__ import annotations

# Standard Libraries Imports
import datetime
import shutil
import sys
from pathlib import Path

# Application Modules Imports
from brain.application.logs.entry_formatting import normalize_log_type
from brain.application.logs.legacy_migration import parse_legacy_md_file
from brain.application.logs.parsing import glob_log_and_md_files, is_canonical_log_file, is_previous_log_file
from brain.application.logs.records import LogEntryRecord, parse_log_content
from brain.application.logs.source_registry import refresh_log_source_registry
from brain.application.logs.store import (
    get_logs_database_path,
    refresh_log_index,
    replace_source_entries,
)


def rebuild_logs_index(workspace_root: Path) -> Path:
    """
    Import file-backed logs into SQLite and refresh the DB latest-index projection.

    Args:
        workspace_root (Path): Workspace root.

    Returns:
        Path: SQLite logs database path.
    """
    logs_dir = workspace_root / "$agent" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    database_path = get_logs_database_path(workspace_root=workspace_root)

    log_files = glob_log_and_md_files(logs_dir)
    for log_file in log_files:
        content = log_file.read_text(encoding="utf-8")
        rel_path = log_file.relative_to(logs_dir).as_posix()

        if not is_canonical_log_file(log_file):
            rel_to_ws = log_file.relative_to(workspace_root).as_posix()
            sys.stderr.write(
                "\033[93m[WARNING] Legacy log file detected: "
                f"{rel_to_ws}. Run `update-log-index --fix` to import it into SQLite and archive the source.\033[0m\n",
            )
            continue

        imported_entries = parse_log_content(
            content=content,
            source_path=f"$agent/logs/{rel_path}",
            source_mtime=log_file.stat().st_mtime,
            source_size=log_file.stat().st_size,
        )
        replace_source_entries(
            workspace_root=workspace_root,
            source_path=f"$agent/logs/{rel_path}",
            entries=imported_entries,
        )

    refresh_log_index(workspace_root=workspace_root)
    refresh_log_source_registry(workspace_root=workspace_root, logs_dir=logs_dir)
    return database_path


def migrate_log_files_to_database(
    workspace_root: Path,
    archive_sources: bool = False,
    archive_errors: list[str] | None = None,
) -> list[str]:
    """
    Import canonical log files into SQLite and optionally move originals to `$agent/.tmp`.

    Args:
        workspace_root (Path): Workspace root.
        archive_sources (bool): Move imported files after successful import.
        archive_errors (list[str] | None): Optional warning sink for archive failures.

    Returns:
        list[str]: Stable paths imported into the database.
    """
    logs_dir: Path = workspace_root / "$agent" / "logs"
    if not logs_dir.exists():
        refresh_log_index(workspace_root=workspace_root)
        return []
    imported_paths: list[str] = []
    for log_file in glob_log_and_md_files(logs_dir):
        if not is_canonical_log_file(log_file):
            continue
        rel_path: str = log_file.relative_to(logs_dir).as_posix()
        source_path: str = f"$agent/logs/{rel_path}"
        content: str = log_file.read_text(encoding="utf-8")
        entries = parse_log_content(
            content=content,
            source_path=source_path,
            source_mtime=log_file.stat().st_mtime,
            source_size=log_file.stat().st_size,
        )
        replace_source_entries(workspace_root=workspace_root, source_path=source_path, entries=entries)
        imported_paths.append(source_path)
        if archive_sources:
            archive_imported_log_file_best_effort(
                workspace_root=workspace_root,
                logs_dir=logs_dir,
                log_file=log_file,
                source_path=source_path,
                archive_errors=archive_errors,
            )
    refresh_log_index(workspace_root=workspace_root)
    refresh_log_source_registry(workspace_root=workspace_root, logs_dir=logs_dir)
    return imported_paths


def migrate_legacy_log_files_to_database(
    workspace_root: Path,
    archive_sources: bool = False,
    archive_errors: list[str] | None = None,
) -> list[str]:
    """
    Import legacy `.log` and dated `.md` logs directly into SQLite.

    Args:
        workspace_root (Path): Workspace root.
        archive_sources (bool): Move imported legacy files after successful import.
        archive_errors (list[str] | None): Optional warning sink for archive failures.

    Returns:
        list[str]: Stable paths imported into the database.
    """
    logs_dir: Path = workspace_root / "$agent" / "logs"
    if not logs_dir.exists():
        refresh_log_index(workspace_root=workspace_root)
        return []

    imported_paths: list[str] = []
    for log_file in glob_log_and_md_files(logs_dir):
        if is_canonical_log_file(log_file):
            continue
        rel_path = log_file.relative_to(logs_dir).as_posix()
        source_path = f"$agent/logs/{rel_path}"
        if is_previous_log_file(log_file):
            entries = parse_log_content(
                content=log_file.read_text(encoding="utf-8"),
                source_path=source_path,
                source_mtime=log_file.stat().st_mtime,
                source_size=log_file.stat().st_size,
            )
        else:
            entries = legacy_markdown_entries(log_file=log_file, source_path=source_path)
        if not entries:
            continue
        replace_source_entries(workspace_root=workspace_root, source_path=source_path, entries=entries)
        imported_paths.append(source_path)
        if archive_sources:
            archive_imported_log_file_best_effort(
                workspace_root=workspace_root,
                logs_dir=logs_dir,
                log_file=log_file,
                source_path=source_path,
                archive_errors=archive_errors,
            )

    refresh_log_index(workspace_root=workspace_root)
    refresh_log_source_registry(workspace_root=workspace_root, logs_dir=logs_dir)
    return imported_paths


def legacy_markdown_entries(log_file: Path, source_path: str) -> list[LogEntryRecord]:
    """
    Parse one dated legacy Markdown log file into structured DB records.

    Args:
        log_file (Path): Legacy Markdown file.
        source_path (str): Stable source path for DB lineage.

    Returns:
        list[LogEntryRecord]: Parsed records.
    """
    parsed_entries = parse_legacy_md_file(file_path=log_file)
    records: list[LogEntryRecord] = []
    for entry in parsed_entries:
        change_type = normalize_legacy_change_type(str(entry.get("git_type") or "feature"))
        date_text = str(entry["date"])
        records.append(
            LogEntryRecord(
                timestamp=f"{date_text} 12:00 am",
                domain=str(entry["domain"]),
                title=str(entry["title"]),
                change_type=change_type,
                why="Legacy log migration.",
                description=str(entry["description"]),
                impact=str(entry["impact"]),
                source_path=source_path,
                source_mtime=log_file.stat().st_mtime,
                source_size=log_file.stat().st_size,
            ),
        )
    return records


def normalize_legacy_change_type(change_type: str) -> str:
    """Normalize legacy change types with a conservative fallback."""
    try:
        return normalize_log_type(change_type=change_type)
    except ValueError:
        if change_type.casefold().strip() in {"doc", "docs"}:
            return "documentation"
        return "feature"


def archive_imported_log_file(workspace_root: Path, logs_dir: Path, log_file: Path) -> Path:
    """
    Move one imported log file into the workspace temporary archive.

    Args:
        workspace_root (Path): Workspace root.
        logs_dir (Path): Current logs directory.
        log_file (Path): Imported canonical log file.

    Returns:
        Path: Archive destination.
    """
    rel_path: Path = log_file.relative_to(logs_dir)
    archive_root: Path = workspace_root / "$agent" / ".tmp" / "migrated_logs_db"
    destination: Path = archive_root / rel_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        timestamp: str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        destination = destination.with_name(f"{destination.stem}.{timestamp}{destination.suffix}")
    shutil.move(str(log_file), str(destination))
    return destination


def archive_imported_log_file_best_effort(
    workspace_root: Path,
    logs_dir: Path,
    log_file: Path,
    source_path: str,
    archive_errors: list[str] | None = None,
) -> Path | None:
    """
    Archive one imported source without making cleanup failure rollback DB migration.

    Args:
        workspace_root (Path): Workspace root.
        logs_dir (Path): Current logs directory.
        log_file (Path): Imported log file.
        source_path (str): Stable source path used in DB lineage.
        archive_errors (list[str] | None): Optional warning sink for archive failures.

    Returns:
        Path | None: Archive destination when cleanup succeeds.
    """
    try:
        return archive_imported_log_file(workspace_root=workspace_root, logs_dir=logs_dir, log_file=log_file)
    except OSError as exc:
        warning = f"{source_path}: {exc}"
        if archive_errors is not None:
            archive_errors.append(warning)
        else:
            sys.stderr.write(f"\033[93m[WARNING] Imported but could not archive log source {warning}\033[0m\n")
        return None
