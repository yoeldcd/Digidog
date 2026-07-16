# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application services for Brain source freshness registries."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path

# Application Modules Imports
from brain.domain.sources.classification import memory_source_type
from brain.domain.sources.models import SourceRegistryCheckDTO, SourceRegistryRecordDTO, SourceTypeResolver
from brain.infrastructure.runtime.paths import get_agent_home, get_source_registry_path, get_workspace_root
from brain.infrastructure.sources.registry.consumers import list_changed_records_for_consumer
from brain.infrastructure.sources.registry.records import (
    list_source_registry_records,
    refresh_registry_records,
    upsert_registry_record,
)
from brain.infrastructure.sources.scanning import (
    scan_log_source_records,
    scan_source_file_record,
    scan_tree_source_records_incremental,
)


def ensure_brain_source_indexes(
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> list[SourceRegistryCheckDTO]:
    """
    Refresh every SQLite source registry used by brain knowledge backends.

    Args:
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.

    Returns:
        Registry refresh results.
    """
    resolved_agent_home: Path = get_agent_home(agent_home=agent_home)
    resolved_workspace_root: Path = get_workspace_root(workspace_root=workspace_root)
    checks: list[SourceRegistryCheckDTO] = [
        refresh_source_registry(
            scope="global",
            root=resolved_agent_home / "memory",
            root_prefix="memory",
            suffixes=(".md",),
            source_type_resolver=memory_source_type,
            agent_home=resolved_agent_home,
            workspace_root=resolved_workspace_root,
        ),
    ]

    log_records = scan_log_source_records(workspace_root=resolved_workspace_root)
    if log_records:
        root_prefix = "$agent/database" if any(record.path.startswith("$agent/database/") for record in log_records) else "$agent/logs"
        registry_path = get_source_registry_path(
            scope="local",
            agent_home=resolved_agent_home,
            workspace_root=resolved_workspace_root,
        )
        refresh_registry_records(
            registry_path=registry_path,
            scope="local",
            records=log_records,
            root_prefix=root_prefix,
        )
        if root_prefix == "$agent/database":
            refresh_registry_records(
                registry_path=registry_path,
                scope="local",
                records=[],
                root_prefix="$agent/logs",
            )
        checks.append(SourceRegistryCheckDTO(registry_path=registry_path.as_posix(), scanned=len(log_records)))
    return checks


def refresh_source_registry(
    scope: str,
    root: Path,
    root_prefix: str,
    suffixes: tuple[str, ...],
    source_type_resolver: SourceTypeResolver,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> SourceRegistryCheckDTO:
    """
    Refresh one scoped source registry from filesystem mtimes.

    Args:
        scope: Runtime scope: `global` or `local`.
        root: Source directory to scan.
        root_prefix: Stable source path prefix.
        suffixes: File suffixes accepted as source files.
        source_type_resolver: Function that maps paths to source families.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.

    Returns:
        Registry refresh summary.
    """
    registry_path: Path = get_source_registry_path(
        scope=scope,
        agent_home=agent_home,
        workspace_root=workspace_root,
    )
    existing_records: dict[str, SourceRegistryRecordDTO] = {
        record.path: record
        for record in list_source_registry_records(
            scope=scope,
            root_prefix=root_prefix,
            active_only=True,
            agent_home=agent_home,
            workspace_root=workspace_root,
        )
    }
    records, changed = scan_tree_source_records_incremental(
        root=root,
        root_prefix=root_prefix,
        suffixes=suffixes,
        source_type_resolver=source_type_resolver,
        existing_records=existing_records,
    )
    if not changed:
        return SourceRegistryCheckDTO(
            registry_path=registry_path.as_posix(),
            scanned=len(records),
        )
    refresh_registry_records(
        registry_path=registry_path,
        scope=scope,
        records=records,
        root_prefix=root_prefix,
    )
    return SourceRegistryCheckDTO(
        registry_path=registry_path.as_posix(),
        scanned=len(records),
    )


def refresh_source_record(
    scope: str,
    file_path: Path,
    root: Path,
    root_prefix: str,
    source_type_resolver: SourceTypeResolver,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> SourceRegistryCheckDTO:
    """
    Refresh one scoped source registry record without scanning the full tree.

    Args:
        scope: Runtime scope: `global` or `local`.
        file_path: Source file to upsert.
        root: Source directory used to compute the stable source path.
        root_prefix: Stable source path prefix.
        source_type_resolver: Function that maps paths to source families.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.

    Returns:
        Registry refresh summary for the single touched source.
    """
    registry_path: Path = get_source_registry_path(
        scope=scope,
        agent_home=agent_home,
        workspace_root=workspace_root,
    )
    record: SourceRegistryRecordDTO = scan_source_file_record(
        file_path=file_path,
        root=root,
        root_prefix=root_prefix,
        source_type_resolver=source_type_resolver,
    )
    upsert_registry_record(
        registry_path=registry_path,
        scope=scope,
        record=record,
    )
    return SourceRegistryCheckDTO(
        registry_path=registry_path.as_posix(),
        scanned=1,
    )


def diff_sources_for_consumer(
    scope: str,
    consumer_name: str,
    root: Path,
    root_prefix: str,
    suffixes: tuple[str, ...],
    source_type_resolver: SourceTypeResolver,
    force_all: bool = False,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> SourceRegistryCheckDTO:
    """
    Compare current source mtimes with one consumer's processed mtimes.

    Args:
        scope: Runtime scope: `global` or `local`.
        consumer_name: Consumer namespace stored in the registry.
        root: Source directory to scan.
        root_prefix: Stable source path prefix.
        suffixes: File suffixes accepted as source files.
        source_type_resolver: Function that maps paths to source families.
        force_all: Whether every active source should be returned as changed.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.

    Returns:
        Changed and deleted source paths.
    """
    refresh_check: SourceRegistryCheckDTO = refresh_source_registry(
        scope=scope,
        root=root,
        root_prefix=root_prefix,
        suffixes=suffixes,
        source_type_resolver=source_type_resolver,
        agent_home=agent_home,
        workspace_root=workspace_root,
    )
    registry_path: Path = Path(refresh_check.registry_path)
    changed_records, deleted_paths = list_changed_records_for_consumer(
        registry_path=registry_path,
        scope=scope,
        consumer_name=consumer_name,
        root_prefix=root_prefix,
        force_all=force_all,
    )
    return SourceRegistryCheckDTO(
        registry_path=registry_path.as_posix(),
        scanned=refresh_check.scanned,
        changed=changed_records,
        deleted=deleted_paths,
    )
