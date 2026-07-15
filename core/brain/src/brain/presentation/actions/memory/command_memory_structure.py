"""Action module to list all memory domains and subdomains."""

from __future__ import annotations

import argparse
import json

from brain.application.memory.indexing.index_service import load_index
from brain.presentation.terminal import render_placeholders, log_step



def get_all_relative_paths(index_data: dict) -> list[str]:
    """Return all indexed memory paths from an index tree."""
    paths = []

    def _walk(children: dict, prefix: str = "") -> None:
        for name, node in _iter_structure_items(children, uptime_order=False):
            memory_path = f"{prefix}.{name}" if prefix else name
            paths.append(memory_path)
            if node.get("__type__") == "dir":
                _walk(node.get("children", {}), memory_path)

    _walk(index_data)
    return sorted(paths)


def _is_index_node(node: object) -> bool:
    """Return whether an index value represents a renderable memory node."""
    return isinstance(node, dict) and node.get("__type__") in {"dir", "file"}


def _iter_structure_items(children: dict, uptime_order: bool, limit: int | None = None) -> list[tuple[str, dict]]:
    """Return directory and file nodes from an index level in display order."""
    items = [
        (name, node)
        for name, node in children.items()
        if _is_index_node(node)
    ]
    if uptime_order:
        items.sort(key=lambda item: item[1].get("mtime", 0), reverse=True)
    else:
        items.sort(key=lambda item: (item[1].get("__type__") != "dir", item[0].lower()))
    if limit is not None:
        items = items[:limit]
    return items


def _collect_index_paths(index_data: dict, uptime_order: bool, limit: int | None) -> list[str]:
    """Collect indexed memory paths while honoring order and per-level limit."""
    paths: list[str] = []

    def _walk(children: dict, prefix: str = "") -> None:
        for name, node in _iter_structure_items(children, uptime_order, limit):
            memory_path = f"{prefix}.{name}" if prefix else name
            paths.append(memory_path)
            if node.get("__type__") == "dir":
                _walk(node.get("children", {}), memory_path)

    _walk(index_data)
    return paths


def _metadata_label(node: dict, uptime_order: bool) -> str:
    """Format the metadata collected by the source registry for one node."""
    node_type = node.get("__type__")
    if node_type == "dir":
        label = f"(E: {node.get('entries', 0)})"
    else:
        size = node.get("size", "0KB")
        lines = node.get("lines", "0")
        entries = node.get("entries", 0)
        label = f"(Sz: {size} L: {lines} E: {entries})"

    if uptime_order:
        from datetime import datetime

        mtime = node.get("mtime", 0)
        label = f"{label} [Up: {datetime.fromtimestamp(mtime).strftime('%d-%m-%Y %H:%M:%S')}]"
    return label


def handle(args: argparse.Namespace) -> int:
    """Print domain hierarchy tree."""
    color_enabled = getattr(args, "color", False)
    try:
        limit = getattr(args, "limit", None)
        if limit is not None and limit < 0:
            raise ValueError("--limit must be zero or greater.")
        uptime_order = getattr(args, "uptime_order", False)
        tree_data = load_index()

        if args.json:
            paths = _collect_index_paths(tree_data, uptime_order, limit)
            print(json.dumps(paths, ensure_ascii=False, indent=2))
            return 0

        log_step(args, "Loading memory structure tree...")
        if not tree_data:
            msg = "__YELLOW__No domains found inside memory directory.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 0

        def _draw(children: dict, prefix: str = "") -> None:
            items = _iter_structure_items(children, uptime_order, limit)
            total_items = sum(1 for node in children.values() if _is_index_node(node))
            rest = max(0, total_items - len(items))
            display_items: list[tuple[str, str | None, dict | None]] = [
                ("node", name, node)
                for name, node in items
            ]
            if rest:
                display_items.append(("rest", None, None))

            for index, (item_type, name, node) in enumerate(display_items):
                is_last = index == len(display_items) - 1
                connector = "└── " if is_last else "├── "
                branch = f"{prefix}{connector}"

                if item_type == "rest":
                    line_msg = f"__DIM__{branch}... {rest} more__RESET__"
                    print(render_placeholders(line_msg, color_enabled))
                    continue

                metadata = _metadata_label(node, uptime_order)
                if node.get("__type__") == "dir":
                    line_msg = f"__DIM__{branch}__RESET____CYAN__{name}/__RESET__ __DIM__{metadata}__RESET__"
                else:
                    line_msg = f"__DIM__{branch}__RESET____GREEN__{name}__RESET__ __DIM__{metadata}__RESET__"
                print(render_placeholders(line_msg, color_enabled))
                if node.get("__type__") == "dir":
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    _draw(node.get("children", {}), next_prefix)

        _draw(tree_data)
        return 0
    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
