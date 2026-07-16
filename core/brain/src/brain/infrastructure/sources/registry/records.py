# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Source record repository operations for source registries."""

from __future__ import annotations

# Standard Libraries Imports
import time
from pathlib import Path

# Application Modules Imports
from brain.domain.sources.models import SourceRegistryRecordDTO
from brain.infrastructure.runtime.paths import get_source_registry_path
from brain.infrastructure.sources.registry.connection import registry_session
from brain.infrastructure.sources.registry.mapping import row_to_record


def refresh_registry_records(
    registry_path: Path,
    scope: str,
    records: list[SourceRegistryRecordDTO],
    root_prefix: str,
) -> None:
    """
    Upsert active source records and mark disappeared paths inactive.

    Args:
        registry_path: Source registry SQLite path.
        scope: Runtime scope.
        records: Current source records.
        root_prefix: Stable source path prefix.
    """
    active_paths: set[str] = {record.path for record in records}
    now_timestamp: float = time.time()
    with registry_session(registry_path=registry_path) as connection:
        for record in records:
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
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(scope, path) DO UPDATE SET
                    source_type = excluded.source_type,
                    title = excluded.title,
                    mtime = excluded.mtime,
                    size_label = excluded.size_label,
                    line_count_label = excluded.line_count_label,
                    entry_count = excluded.entry_count,
                    active = 1,
                    updated_at = excluded.updated_at
                """,
                (
                    scope,
                    record.source_type,
                    record.path,
                    record.title,
                    float(record.mtime),
                    record.size,
                    record.lines,
                    int(record.entries),
                    now_timestamp,
                ),
            )

        existing_rows = connection.execute(
            """
            SELECT path FROM sources
            WHERE scope = ?
                AND path LIKE ?
                AND active = 1
            """,
            (scope, f"{root_prefix.rstrip('/')}/%"),
        ).fetchall()
        for row in existing_rows:
            source_path: str = str(row["path"])
            if source_path not in active_paths:
                connection.execute(
                    "UPDATE sources SET active = 0, updated_at = ? WHERE scope = ? AND path = ?",
                    (now_timestamp, scope, source_path),
                )
        connection.commit()


def upsert_registry_record(
    registry_path: Path,
    scope: str,
    record: SourceRegistryRecordDTO,
) -> None:
    """
    Upsert one active source record without scanning or deactivating siblings.

    Args:
        registry_path: Source registry SQLite path.
        scope: Runtime scope.
        record: Current source record.
    """
    now_timestamp: float = time.time()
    with registry_session(registry_path=registry_path) as connection:
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
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(scope, path) DO UPDATE SET
                source_type = excluded.source_type,
                title = excluded.title,
                mtime = excluded.mtime,
                size_label = excluded.size_label,
                line_count_label = excluded.line_count_label,
                entry_count = excluded.entry_count,
                active = 1,
                updated_at = excluded.updated_at
            """,
            (
                scope,
                record.source_type,
                record.path,
                record.title,
                float(record.mtime),
                record.size,
                record.lines,
                int(record.entries),
                now_timestamp,
            ),
        )
        connection.commit()


def list_source_registry_records(
    scope: str,
    root_prefix: str,
    active_only: bool = True,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> list[SourceRegistryRecordDTO]:
    """
    Read source records from a scoped registry.

    Args:
        scope: Runtime scope: `global` or `local`.
        root_prefix: Stable source path prefix.
        active_only: Whether inactive records should be hidden.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.

    Returns:
        Registry records.
    """
    registry_path: Path = get_source_registry_path(
        scope=scope,
        agent_home=agent_home,
        workspace_root=workspace_root,
    )
    where_active: str = "AND active = 1" if active_only else ""
    with registry_session(registry_path=registry_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                id,
                path,
                mtime,
                size_label,
                line_count_label,
                entry_count,
                source_type,
                title,
                active
            FROM sources
            WHERE scope = ?
                AND path LIKE ?
                {where_active}
            ORDER BY path
            """,
            (scope, f"{root_prefix.rstrip('/')}/%"),
        ).fetchall()
    return [row_to_record(row=row, active=bool(row["active"])) for row in rows]
