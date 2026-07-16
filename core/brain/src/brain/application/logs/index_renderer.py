# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Markdown renderer for the workspace log domain index."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path

# Application Modules Imports
from brain.application.logs.parsing import log_date_stem, log_read_command


class DomainNode:
    """Tree node used to render nested log domains."""

    def __init__(self) -> None:
        self.subdomains: dict[str, DomainNode] = {}
        self.entry: dict[str, object] | None = None


def build_domain_tree(latest_entries: dict) -> dict[str, DomainNode]:
    """Build a nested domain tree from latest log entries by domain."""
    parent_nodes = {}
    for domain, entry_info in latest_entries.items():
        parts = domain.split(".")
        parent = parts[0]
        if parent not in parent_nodes:
            parent_nodes[parent] = DomainNode()

        current = parent_nodes[parent]
        for part in parts[1:]:
            if part not in current.subdomains:
                current.subdomains[part] = DomainNode()
            current = current.subdomains[part]
        current.entry = entry_info
    return parent_nodes


def render_logs_index(latest_entries: dict) -> str:
    """Render latest domain entries as the human-readable workspace log index."""
    parent_nodes = build_domain_tree(latest_entries=latest_entries)
    output_lines = [
        "# Workspace Logs Index",
        "",
        "This file lists the last log entry command that modified each domain/subdomain.",
        "",
    ]

    for parent in sorted(parent_nodes.keys()):
        node = parent_nodes[parent]
        output_lines.append(f"## {parent}")
        output_lines.append("")
        if not node.subdomains:
            if node.entry:
                parsed_dt, entry_ts, rel_path, git_type, title = node.entry
                del parsed_dt
                stem = log_date_stem(Path(rel_path))
                type_str = f"({git_type}) " if git_type else ""
                title_suffix = f" | title: {title}" if title else ""
                output_lines.append(f"* {type_str}last entry `{log_read_command(stem, entry_ts)}`{title_suffix}")
        else:
            for child in sorted(node.subdomains.keys()):
                output_lines.extend(render_node(child, node.subdomains[child], [parent]))

        if output_lines[-1] != "":
            output_lines.append("")

    return "\n".join(output_lines)


def render_node(name: str, node: DomainNode, path_segments: list[str]) -> list[str]:
    """Render one nested domain node."""
    lines = []
    current_path = path_segments + [name]
    full_name = ".".join(current_path)

    if node.subdomains:
        header_level = "#" * (2 + len(path_segments))
        lines.append(f"{header_level} {full_name}")
        lines.append("")
        for child in sorted(node.subdomains.keys()):
            lines.extend(render_node(child, node.subdomains[child], current_path))
    else:
        if node.entry:
            parsed_dt, entry_ts, rel_path, git_type, title = node.entry
            del parsed_dt
            stem = log_date_stem(Path(rel_path))
            type_str = f"({git_type}) " if git_type else ""
            title_suffix = f" | title: {title}" if title else ""
            lines.append(f"* {name} : {type_str}last entry `{log_read_command(stem, entry_ts)}`{title_suffix}")
    return lines
