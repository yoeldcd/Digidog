"""SQLite-backed memory source registry and structure service."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path

# Application Modules Imports
from brain.application.memory import paths
from brain.application.memory.indexing.stats import scan_file_stats
from brain.application.memory.indexing.tree import records_to_tree
from brain.application.sources.registry_service import refresh_source_registry
from brain.domain.sources.classification import memory_source_type
from brain.domain.sources.models import SourceRegistryRecordDTO
from brain.infrastructure.sources.registry.records import list_source_registry_records


def build_full_index() -> dict:
    """
    Refresh the memory source registry and return a tree-shaped view.

    Vector synchronization is intentionally owned by `update-vectorstore`,
    so memory index refreshes stay a cheap filesystem/SQLite operation.

    Returns:
        dict: Memory source tree reconstructed from `brain_sources.db`.
    """
    paths.ensure_memory_root()
    refresh_source_registry(
        scope="global",
        root=paths.MEMORY_ROOT,
        root_prefix="memory",
        suffixes=(".md",),
        source_type_resolver=memory_source_type,
    )
    records: list[SourceRegistryRecordDTO] = list_source_registry_records(
        scope="global",
        root_prefix="memory",
        active_only=True,
    )
    return records_to_tree(records=records)


def load_index() -> dict:
    """
    Load the current memory source tree from SQLite.

    Returns:
        dict: Memory source tree reconstructed from `brain_sources.db`.
    """
    return build_full_index()


def update_index_category(category: str, deleted: bool = False) -> None:
    """
    Refresh the memory source registry after a category change.

    Args:
        category: Changed memory category.
        deleted: Whether the category was deleted.
    """
    del category, deleted
    build_full_index()


def update_index_record(category: str, key: str, deleted: bool = False) -> None:
    """
    Refresh the memory source registry after a record change.

    Args:
        category: Changed memory category.
        key: Changed memory key.
        deleted: Whether the record was deleted.
    """
    del category, key, deleted
    build_full_index()


def get_file_stats(path: Path) -> tuple[str, str, int]:
    """
    Return source statistics from the registry when available.

    Args:
        path: Markdown file path.

    Returns:
        tuple[str, str, int]: Size, line count, and entry count labels.
    """
    try:
        source_path: str = f"memory/{path.relative_to(paths.MEMORY_ROOT).as_posix()}"
    except ValueError:
        source_path = path.as_posix()
    records = list_source_registry_records(scope="global", root_prefix="memory", active_only=True)
    for record in records:
        if record.path == source_path:
            return record.size, record.lines, record.entries
    return scan_file_stats(path=path)
