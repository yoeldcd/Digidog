"""Consumer state repository operations for source registries."""

from __future__ import annotations

# Standard Libraries Imports
import time
from pathlib import Path

# Application Modules Imports
from brain.domain.sources.models import SourceRegistryRecordDTO
from brain.infrastructure.runtime.paths import get_source_registry_path
from brain.infrastructure.sources.registry.connection import registry_session
from brain.infrastructure.sources.registry.mapping import row_to_record


def list_changed_records_for_consumer(
    registry_path: Path,
    scope: str,
    consumer_name: str,
    root_prefix: str,
    force_all: bool = False,
) -> tuple[list[SourceRegistryRecordDTO], list[str]]:
    """
    Return changed active records and deleted paths for one consumer.

    Args:
        registry_path: Source registry SQLite path.
        scope: Runtime scope.
        consumer_name: Consumer namespace stored in the registry.
        root_prefix: Stable source path prefix.
        force_all: Whether every active source should be returned as changed.

    Returns:
        Changed source records and deleted source paths.
    """
    changed_records: list[SourceRegistryRecordDTO] = []
    deleted_paths: list[str] = []
    with registry_session(registry_path=registry_path) as connection:
        rows = connection.execute(
            """
            SELECT
                sources.id,
                sources.path,
                sources.mtime,
                sources.size_label,
                sources.line_count_label,
                sources.entry_count,
                sources.source_type,
                sources.title,
                source_consumers.processed_mtime
            FROM sources
            LEFT JOIN source_consumers
                ON source_consumers.source_id = sources.id
                AND source_consumers.consumer = ?
            WHERE sources.scope = ?
                AND sources.path LIKE ?
                AND sources.active = 1
            ORDER BY sources.path
            """,
            (consumer_name, scope, f"{root_prefix.rstrip('/')}/%"),
        ).fetchall()
        for row in rows:
            processed_mtime = row["processed_mtime"]
            is_changed = force_all or processed_mtime is None
            if not is_changed:
                is_changed = abs(float(processed_mtime) - float(row["mtime"])) > 0.000001
            if is_changed:
                changed_records.append(row_to_record(row=row, active=True))

        deleted_rows = connection.execute(
            """
            SELECT sources.path
            FROM sources
            JOIN source_consumers
                ON source_consumers.source_id = sources.id
                AND source_consumers.consumer = ?
            WHERE sources.scope = ?
                AND sources.path LIKE ?
                AND sources.active = 0
            ORDER BY sources.path
            """,
            (consumer_name, scope, f"{root_prefix.rstrip('/')}/%"),
        ).fetchall()
        deleted_paths = [str(row["path"]) for row in deleted_rows]

    return changed_records, deleted_paths


def mark_consumer_source_processed(
    scope: str,
    consumer_name: str,
    source_path: str,
    mtime: float,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> None:
    """
    Store one processed source mtime for a consumer in SQLite.

    Args:
        scope: Runtime scope: `global` or `local`.
        consumer_name: Consumer namespace.
        source_path: Stable source path.
        mtime: Processed filesystem modification timestamp.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.
    """
    registry_path: Path = get_source_registry_path(
        scope=scope,
        agent_home=agent_home,
        workspace_root=workspace_root,
    )
    with registry_session(registry_path=registry_path) as connection:
        source_row = connection.execute(
            "SELECT id FROM sources WHERE scope = ? AND path = ?",
            (scope, source_path),
        ).fetchone()
        if source_row is None:
            connection.execute(
                """
                INSERT INTO sources(
                    scope,
                    source_type,
                    path,
                    title,
                    mtime,
                    size_label,
                    line_count_label,
                    entry_count,
                    active,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, '0KB', '0', 0, 1, ?)
                """,
                (scope, "unknown", source_path, Path(source_path).stem, float(mtime), time.time()),
            )
            source_row = connection.execute(
                "SELECT id FROM sources WHERE scope = ? AND path = ?",
                (scope, source_path),
            ).fetchone()
        source_id: int = int(source_row["id"])
        connection.execute(
            """
            INSERT INTO source_consumers(source_id, consumer, processed_mtime, processed_at, status)
            VALUES(?, ?, ?, ?, 'processed')
            ON CONFLICT(source_id, consumer) DO UPDATE SET
                processed_mtime = excluded.processed_mtime,
                processed_at = excluded.processed_at,
                status = excluded.status
            """,
            (source_id, consumer_name, float(mtime), time.time()),
        )
        connection.commit()


def remove_consumer_sources(
    scope: str,
    consumer_name: str,
    source_paths: list[str],
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> None:
    """
    Remove deleted source paths from a consumer state in SQLite.

    Args:
        scope: Runtime scope: `global` or `local`.
        consumer_name: Consumer namespace.
        source_paths: Stable source paths to remove.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.
    """
    if not source_paths:
        return
    registry_path: Path = get_source_registry_path(
        scope=scope,
        agent_home=agent_home,
        workspace_root=workspace_root,
    )
    placeholders: str = ", ".join("?" for _ in source_paths)
    with registry_session(registry_path=registry_path) as connection:
        connection.execute(
            f"""
            DELETE FROM source_consumers
            WHERE consumer = ?
                AND source_id IN (
                    SELECT id FROM sources WHERE scope = ? AND path IN ({placeholders})
                )
            """,
            (consumer_name, scope, *source_paths),
        )
        connection.commit()
