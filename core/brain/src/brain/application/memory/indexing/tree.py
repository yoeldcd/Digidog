"""Memory source tree builders."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path

# Application Modules Imports
from brain.domain.sources.models import SourceRegistryRecordDTO


def records_to_tree(records: list[SourceRegistryRecordDTO]) -> dict:
    """
    Convert flat source registry rows into the memory tree shape.

    Args:
        records: Active memory source rows.

    Returns:
        dict: Tree structure consumed by memory-structure.
    """
    tree: dict = {}
    for record in sorted(records, key=lambda item: item.path.casefold()):
        parts: list[str] = [
            part
            for part in Path(record.path).parts
            if part not in {"memory", ""}
        ]
        if not parts:
            continue
        current: dict = tree
        for directory_name in parts[:-1]:
            directory_node: dict = current.setdefault(
                directory_name,
                {
                    "__type__": "dir",
                    "mtime": 0.0,
                    "entries": 0,
                    "children": {},
                },
            )
            directory_node["mtime"] = max(float(directory_node.get("mtime") or 0.0), record.mtime)
            current = directory_node.setdefault("children", {})

        file_name: str = Path(parts[-1]).stem
        current[file_name] = {
            "__type__": "file",
            "mtime": record.mtime,
            "size": record.size,
            "lines": record.lines,
            "entries": record.entries,
        }

    update_directory_entries(tree=tree)
    return tree


def update_directory_entries(tree: dict) -> tuple[int, float]:
    """
    Update directory entry counts and max mtimes recursively.

    Args:
        tree: Memory tree level.

    Returns:
        tuple[int, float]: Entry count and max mtime for this level.
    """
    max_mtime: float = 0.0
    for node in tree.values():
        if not isinstance(node, dict):
            continue
        if node.get("__type__") == "dir":
            child_count, child_mtime = update_directory_entries(node.setdefault("children", {}))
            node["entries"] = child_count
            node["mtime"] = max(float(node.get("mtime") or 0.0), child_mtime)
            max_mtime = max(max_mtime, float(node.get("mtime") or 0.0))
        elif node.get("__type__") == "file":
            max_mtime = max(max_mtime, float(node.get("mtime") or 0.0))
    return len(tree), max_mtime


_records_to_tree = records_to_tree
_update_directory_entries = update_directory_entries
