"""Idempotent file and directory steps used by runtime migration."""

from __future__ import annotations

# Standard Libraries Imports
import shutil
from pathlib import Path
from typing import Iterable

from brain.infrastructure.runtime.migration_dtos import RuntimeMigrationActionDTO, RuntimeMigrationReportDTO


SQLITE_SIDECAR_SUFFIXES: tuple[str, ...] = ("-wal", "-shm", "-journal")
"""SQLite sidecar suffixes migrated beside database files."""


def migrate_sqlite_database(
    legacy_candidates: Iterable[Path],
    target: Path,
    report: RuntimeMigrationReportDTO,
) -> None:
    """Move one legacy SQLite database candidate into its target path."""
    for legacy_path in legacy_candidates:
        if not legacy_path.exists():
            continue
        if target.exists() and target.stat().st_size > 0:
            if legacy_path.stat().st_size == 0:
                legacy_path.unlink()
                record(report=report, action="removed", source=legacy_path, detail="empty legacy database")
                continue
            report.warnings.append(
                f"Skipped legacy database migration because target already exists: {legacy_path} -> {target}",
            )
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy_path), str(target))
        record(report=report, action="moved", source=legacy_path, target=target, detail="legacy SQLite database")
        move_sqlite_sidecars(source_base=legacy_path, target_base=target, report=report)


def move_sqlite_sidecars(source_base: Path, target_base: Path, report: RuntimeMigrationReportDTO) -> None:
    """Move SQLite sidecar files beside a migrated database."""
    for suffix in SQLITE_SIDECAR_SUFFIXES:
        source_sidecar: Path = Path(f"{source_base}{suffix}")
        if not source_sidecar.exists():
            continue
        target_sidecar: Path = Path(f"{target_base}{suffix}")
        if target_sidecar.exists():
            report.warnings.append(f"Skipped SQLite sidecar because target exists: {source_sidecar}")
            continue
        shutil.move(str(source_sidecar), str(target_sidecar))
        record(report=report, action="moved", source=source_sidecar, target=target_sidecar, detail="SQLite sidecar")


def migrate_directory(source: Path, target: Path, report: RuntimeMigrationReportDTO) -> None:
    """Move a legacy runtime directory when the target can safely receive it."""
    if not source.exists():
        return
    if is_empty_or_gitignore_only(source):
        shutil.rmtree(source)
        record(report=report, action="removed", source=source, detail="empty legacy directory")
        return
    if target.exists() and not is_empty_or_gitignore_only(target):
        report.warnings.append(f"Skipped legacy directory migration because target already has data: {source} -> {target}")
        return
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    record(report=report, action="moved", source=source, target=target, detail="legacy runtime directory")


def remove_derived_json(source: Path, report: RuntimeMigrationReportDTO) -> None:
    """Remove a retired derived JSON file."""
    if source.exists() and source.is_file():
        source.unlink()
        record(report=report, action="removed", source=source, detail="retired derived JSON index")


def remove_empty_legacy_directory(source: Path, report: RuntimeMigrationReportDTO) -> None:
    """Remove a legacy directory if it is empty or contains only `.gitignore`."""
    if source.exists() and source.is_dir() and is_empty_or_gitignore_only(source):
        shutil.rmtree(source)
        record(report=report, action="removed", source=source, detail="empty legacy directory")


def is_empty_or_gitignore_only(path: Path) -> bool:
    """Return whether a directory has no substantive files."""
    if not path.exists() or not path.is_dir():
        return False
    entries: list[Path] = list(path.iterdir())
    return not entries or all(entry.is_file() and entry.name == ".gitignore" for entry in entries)


def record(
    report: RuntimeMigrationReportDTO,
    action: str,
    source: Path,
    target: Path | None = None,
    detail: str = "",
) -> None:
    """Append one migration action to the report."""
    report.actions.append(
        RuntimeMigrationActionDTO(
            action=action,
            source=source.as_posix(),
            target="" if target is None else target.as_posix(),
            detail=detail,
        ),
    )
