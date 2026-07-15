"""Backlog Markdown parser."""

from __future__ import annotations

# Standard Libraries Imports
import re
from pathlib import Path

# Application Modules Imports
from brain.application.backlog.models import TaskNode
from brain.application.backlog.repository import get_backlog_path


TASK_RE = re.compile(r"^\s*-\s*\[([ xX]|WORKING)\]\s*#(t\d+)\s*(?:\((HIGH|MEDIUM|LOW)\))?:\s*(.*?)(?:\s+-\s+(.*))?$")
"""Checklist item parser with optional priority, status, and description."""


def load_tasks(workspace_root: Path) -> TaskNode:
    """Parse backlog.md into a TaskNode tree."""
    tasks_file = get_backlog_path(workspace_root)
    root = TaskNode("", 0)
    if not tasks_file.exists():
        return root

    content = tasks_file.read_text(encoding="utf-8")
    active_nodes = [root]

    for line in content.splitlines():
        line_strip = line.strip()
        if not line_strip:
            continue

        header_match = re.match(r"^(#{1,6})\s+(.+)$", line_strip)
        if header_match:
            level = len(header_match.group(1))
            name = header_match.group(2).strip()

            while len(active_nodes) > level:
                active_nodes.pop()

            parent = active_nodes[-1]
            if name not in parent.children:
                parent.children[name] = TaskNode(name, level)

            active_nodes.append(parent.children[name])
            continue

        completed_at = ""
        line_for_task = line
        checked_match = re.search(r"\s*\(checked:\s*([^)]+)\)\s*$", line_for_task)
        if checked_match:
            completed_at = checked_match.group(1).strip()
            line_for_task = line_for_task[:checked_match.start()]

        task_match = TASK_RE.match(line_for_task)
        if task_match:
            status_char = task_match.group(1).upper()
            checked = status_char == "X"
            status = "DONE" if checked else ("WORKING" if status_char == "WORKING" else "TODO")
            task_id = task_match.group(2)
            priority = task_match.group(3) if task_match.group(3) else "LOW"
            title = task_match.group(4).strip()
            description = task_match.group(5).strip() if task_match.group(5) else ""

            active_nodes[-1].tasks.append({
                "id": task_id,
                "priority": priority,
                "title": title,
                "description": description,
                "checked": checked,
                "status": status,
                "completed_at": completed_at,
            })

    return root
