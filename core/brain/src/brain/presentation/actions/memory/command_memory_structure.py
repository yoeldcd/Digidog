"""Action module to list all memory domains and subdomains."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import TypeAlias

from brain.application.authority.memory_guard import is_memory_access_allowed
from brain.application.memory import paths as memory_paths
from brain.application.memory.indexing.index_service import load_index
from brain.application.memory.paths import validate_part_name
from brain.presentation.terminal import log_step, render_placeholders


IndexNode: TypeAlias = dict[str, object]
IndexTree: TypeAlias = dict[str, IndexNode]



def get_all_relative_paths(index_data: Mapping[str, object]) -> list[str]:
    """Return every indexed memory path represented by an index tree.

    Args:
        index_data: Root node mapping loaded from the memory index.

    Returns:
        list[str]: Alphabetically sorted dotted paths for directories and entries.
    """
    paths: list[str] = []

    def _walk(children: Mapping[str, object], prefix: str = "") -> None:
        """Visit each indexed node and append its dotted path.

        Args:
            children: Index nodes at the current hierarchy level.
            prefix: Dotted path accumulated from parent directories.

        Returns:
            None.
        """

        for name, node in _iter_structure_items(children, uptime_order=False):
            memory_path = f"{prefix}.{name}" if prefix else name
            paths.append(memory_path)

            if node.get("__type__") == "dir":
                _walk(_children_for_node(node), memory_path)

    _walk(index_data)

    return sorted(paths)


def _is_index_node(node: object) -> bool:
    """Return whether an index value represents a renderable memory node.

    Args:
        node: Candidate value from an indexed hierarchy level.

    Returns:
        bool: True when the value is a directory or file node.
    """

    return isinstance(node, dict) and node.get("__type__") in {"dir", "file"}


def _children_for_node(node: IndexNode) -> Mapping[str, object]:
    """Return a directory node's children without exposing invalid values.

    Args:
        node: Indexed directory or file node.

    Returns:
        Mapping[str, object]: Child nodes when the node stores a mapping;
        otherwise an empty mapping.
    """
    children = node.get("children")

    if isinstance(children, dict):

        return children

    return {}


def _mtime_value(node: IndexNode) -> float:
    """Return a numeric modification time suitable for ordering and rendering.

    Args:
        node: Indexed node containing optional source metadata.

    Returns:
        float: Modification timestamp, or zero for missing or invalid metadata.
    """
    mtime = node.get("mtime", 0)

    if isinstance(mtime, (int, float)):

        return float(mtime)

    return 0.0


def _uptime_sort_key(item: tuple[str, IndexNode]) -> float:
    """Return the modification time used for descending uptime ordering.

    Args:
        item: Indexed name and node pair being ordered.

    Returns:
        float: Numeric modification timestamp for the indexed node.
    """

    return _mtime_value(item[1])


def _structure_sort_key(item: tuple[str, IndexNode]) -> tuple[bool, str]:
    """Return the directory-first alphabetical ordering key.

    Args:
        item: Indexed name and node pair being ordered.

    Returns:
        tuple[bool, str]: File-after-directory flag and normalized node name.
    """
    node_type = item[1].get("__type__")
    is_file = node_type != "dir"
    normalized_name = item[0].lower()

    return is_file, normalized_name

def _iter_structure_items(
    children: Mapping[str, object],
    uptime_order: bool,
    limit: int | None = None,
) -> list[tuple[str, IndexNode]]:
    """Return directory and file nodes from an index level in display order.

    Args:
        children: Indexed nodes at the current hierarchy level.
        uptime_order: Whether to order nodes by descending modification time.
        limit: Optional number of nodes to retain at this hierarchy level.

    Returns:
        list[tuple[str, IndexNode]]: Valid indexed nodes in display order.
    """
    items: list[tuple[str, IndexNode]] = []

    for name, node in children.items():

        if not isinstance(name, str):
            continue

        if not isinstance(node, dict):
            continue

        if not _is_index_node(node):
            continue
        items.append((name, node))

    if uptime_order:
        items.sort(key=_uptime_sort_key, reverse=True)

    else:
        items.sort(key=_structure_sort_key)

    if limit is not None:
        items = items[:limit]

    return items


def _resolve_memory_file_path(path_parts: tuple[str, ...]) -> Path:
    """Resolve a dotted index path to a canonical Markdown file beneath memory.

    Args:
        path_parts: Directory and file-stem components from the index hierarchy.

    Returns:
        Path: Canonical Markdown file path under the managed memory root.

    Raises:
        RuntimeError: If a path component is invalid or resolution encounters a
            managed path error.
        ValueError: If no components are supplied or the resolved path escapes the
            managed memory root.
    """

    if not path_parts:
        raise ValueError("Memory file path requires at least one component.")

    validated_parts = tuple(validate_part_name(part) for part in path_parts)
    memory_root = memory_paths.MEMORY_ROOT.resolve(strict=False)
    file_name = f"{validated_parts[-1]}.md"
    candidate = memory_root.joinpath(*validated_parts[:-1], file_name)
    resolved_candidate = candidate.resolve(strict=False)

    try:
        resolved_candidate.relative_to(memory_root)

    except ValueError as exc:
        raise ValueError("Resolved memory path escapes the managed memory root.") from exc


    return resolved_candidate


def _is_file_visible(path_parts: tuple[str, ...], authority: str) -> bool:
    """Read one raw Markdown entry and evaluate its authority header.

    Args:
        path_parts: Directory and file-stem components from the index hierarchy.
        authority: Caller authority used by the memory access guard.

    Returns:
        bool: True when the file exists, resolves safely, and is authorized.
    """

    try:
        file_path = _resolve_memory_file_path(path_parts)

    except (OSError, RuntimeError, ValueError):
        return False

    try:
        raw_content = file_path.read_text(encoding="utf-8")

    except (OSError, UnicodeError):
        return False

    allowed, _ = is_memory_access_allowed(raw_content, authority)

    return allowed


def _project_visible_tree(
    children: Mapping[str, object],
    authority: str,
    prefix: tuple[str, ...] = (),
) -> IndexTree:
    """Copy only authorized files and directories into a new index tree.

    Args:
        children: Raw index nodes at the current hierarchy level.
        authority: Caller authority used for every file-node authorization check.
        prefix: Hierarchy components leading to this level.

    Returns:
        IndexTree: Non-mutating projection containing visible nodes only.
    """
    visible_tree: IndexTree = {}


    for name, raw_node in children.items():

        if not isinstance(name, str):
            continue

        if not isinstance(raw_node, dict):
            continue

        if not _is_index_node(raw_node):
            continue

        path_parts = prefix + (name,)
        node_type = raw_node.get("__type__")

        if node_type == "file":
            if _is_file_visible(path_parts, authority):
                visible_tree[name] = dict(raw_node)
            continue

        visible_children = _project_visible_tree(
            _children_for_node(raw_node),
            authority,
            path_parts,
        )

        if not visible_children:
            continue

        visible_node = dict(raw_node)
        visible_node["children"] = visible_children
        visible_node["entries"] = len(visible_children)
        visible_tree[name] = visible_node

    return visible_tree


def _collect_index_paths(
    index_data: Mapping[str, object],
    uptime_order: bool,
    limit: int | None,
) -> list[str]:
    """Collect indexed memory paths while honoring order and per-level limit.

    Args:
        index_data: Authority-filtered memory tree.
        uptime_order: Whether to order nodes by descending modification time.
        limit: Optional number of nodes to retain at each hierarchy level.

    Returns:
        list[str]: Dotted paths in the filtered display order.
    """
    paths: list[str] = []

    def _walk(children: Mapping[str, object], prefix: str = "") -> None:
        """Collect paths recursively from one filtered hierarchy level.

        Args:
            children: Filtered index nodes at the current level.
            prefix: Dotted path accumulated from parent directories.

        Returns:
            None.
        """

        for name, node in _iter_structure_items(children, uptime_order, limit):
            memory_path = f"{prefix}.{name}" if prefix else name
            paths.append(memory_path)

            if node.get("__type__") == "dir":
                _walk(_children_for_node(node), memory_path)

    _walk(index_data)

    return paths


def _metadata_label(node: IndexNode, uptime_order: bool) -> str:
    """Format source metadata for one projected node.

    Args:
        node: Projected file or directory node with source metadata.
        uptime_order: Whether to append the formatted modification timestamp.

    Returns:
        str: Existing terminal metadata label for the node.
    """
    node_type = node.get("__type__")

    if node_type == "dir":
        label = f"(E: {node.get('entries', 0)})"

    else:
        size = node.get("size", "0KB")
        lines = node.get("lines", "0")
        entries = node.get("entries", 0)
        label = f"(Sz: {size} L: {lines} E: {entries})"

    if uptime_order:
        mtime = _mtime_value(node)
        timestamp = datetime.fromtimestamp(mtime).strftime("%d-%m-%Y %H:%M:%S")
        label = f"{label} [Up: {timestamp}]"

    return label


def handle(args: argparse.Namespace) -> int:
    """Render the authority-filtered memory hierarchy in JSON or terminal form.

    Args:
        args: Parsed command options, including output format, ordering, item
            limit, color mode, and caller authority.

    Returns:
        int: Zero when the hierarchy is rendered; otherwise one after reporting an
        error.

    Raises:
        ValueError: If the caller supplies a negative item limit. The exception is
            converted into the command's existing error output and status code.
    """
    color_enabled = getattr(args, "color", False)

    try:
        limit = getattr(args, "limit", None)

        if limit is not None and limit < 0:
            raise ValueError("--limit must be zero or greater.")

        uptime_order = getattr(args, "uptime_order", False)

        try:
            authority = args.authority

        except AttributeError as exc:
            raise ValueError("Command authority is required.") from exc

        if not isinstance(authority, str) or not authority.strip():
            raise ValueError("Command authority is required.")

        raw_tree = load_index(include_indexes=True)
        tree_data = _project_visible_tree(raw_tree, authority)

        if args.json:
            paths = _collect_index_paths(tree_data, uptime_order, limit)
            print(json.dumps(paths, ensure_ascii=False, indent=2))

            return 0

        log_step(args, "Loading memory structure tree...")

        if not tree_data:
            msg = "__YELLOW__No domains found inside memory directory.__RESET__"
            print(render_placeholders(msg, color_enabled))

            return 0

        def _draw(children: Mapping[str, object], prefix: str = "") -> None:
            """Render one filtered hierarchy level and its descendants.

            Args:
                children: Filtered index nodes at the current hierarchy level.
                prefix: Terminal indentation and branch prefix for this level.

            Returns:
                None.
            """
            items = _iter_structure_items(children, uptime_order, limit)
            all_items = _iter_structure_items(children, uptime_order)
            rest = max(0, len(all_items) - len(items))

            for index, (name, node) in enumerate(items):
                is_last = index == len(items) - 1 and rest == 0
                connector = "└── " if is_last else "├── "
                branch = f"{prefix}{connector}"
                metadata = _metadata_label(node, uptime_order)

                if node.get("__type__") == "dir":
                    line_msg = (
                        f"__DIM__{branch}__RESET__"
                        f"__CYAN__{name}/__RESET__ "
                        f"__DIM__{metadata}__RESET__"
                    )

                else:
                    line_msg = (
                        f"__DIM__{branch}__RESET__"
                        f"__GREEN__{name}__RESET__ "
                        f"__DIM__{metadata}__RESET__"
                    )

                print(render_placeholders(line_msg, color_enabled))

                if node.get("__type__") == "dir":
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    _draw(_children_for_node(node), next_prefix)

            if rest:
                branch = f"{prefix}└── "
                line_msg = f"__DIM__{branch}... {rest} more__RESET__"
                print(render_placeholders(line_msg, color_enabled))

        _draw(tree_data)

        return 0

    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))

        return 1
