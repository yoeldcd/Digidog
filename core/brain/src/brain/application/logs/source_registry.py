"""Source registry refresh helpers for workspace logs."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path


def refresh_log_source_registry(workspace_root: Path, logs_dir: Path) -> None:
    """Refresh the local source registry for DB-backed or exported workspace logs."""
    del logs_dir
    try:
        from brain.infrastructure.runtime.paths import get_source_registry_path
        from brain.infrastructure.sources.registry.records import refresh_registry_records
        from brain.infrastructure.sources.scanning import scan_log_source_records

        records = scan_log_source_records(workspace_root=workspace_root)
        root_prefix = "$agent/database" if any(record.path.startswith("$agent/database/") for record in records) else "$agent/logs"
        refresh_registry_records(
            registry_path=get_source_registry_path(scope="local", workspace_root=workspace_root),
            scope="local",
            records=records,
            root_prefix=root_prefix,
        )
        if root_prefix == "$agent/database":
            refresh_registry_records(
                registry_path=get_source_registry_path(scope="local", workspace_root=workspace_root),
                scope="local",
                records=[],
                root_prefix="$agent/logs",
            )
    except Exception:
        pass


def refresh_log_source_record(workspace_root: Path, logs_dir: Path, log_file: Path) -> None:
    """Refresh local source registry records after a touched log source changes."""
    del log_file
    refresh_log_source_registry(workspace_root=workspace_root, logs_dir=logs_dir)
