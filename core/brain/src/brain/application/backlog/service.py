# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Backlog application service for the logs-database task projection."""

from __future__ import annotations

# Standard Libraries Imports
import datetime
import re
from dataclasses import dataclass
from pathlib import Path

# Application Modules Imports
from brain.application.backlog.models import BacklogTask, TASK_STATUSES, TaskNode
from brain.application.backlog.parser import load_tasks
from brain.application.backlog.repository import (
    add_task_record,
    delete_task_record,
    edit_task_record,
    get_backlog_path,
    get_task,
    insert_legacy_task,
    list_tasks,
    normalize_task_id,
    set_task_status_record,
)
from brain.application.logs.store import connect_logs_database


PRIORITIES = frozenset({"HIGH", "MEDIUM", "LOW"})
"""Supported persisted task priorities."""


class BacklogTaskNotFoundError(ValueError):
    """Raised when a requested task does not exist in the current workspace."""


class BacklogTaskDeletionError(ValueError):
    """Raised when an unfinished task is deleted without explicit force."""


@dataclass(slots=True, frozen=True)
class BacklogMigrationReport:
    """Counts resulting from an idempotent legacy Markdown import."""

    imported: int
    existing: int


def migrate_legacy_backlog(workspace_root: Path) -> BacklogMigrationReport:
    """
    Import task IDs missing from the legacy backlog Markdown source.

    SQLite is authoritative after a task has been imported. Re-running this
    function never overwrites task fields or state that have changed in the DB.
    """
    legacy_path = get_backlog_path(workspace_root=workspace_root)
    if not legacy_path.exists():
        return BacklogMigrationReport(imported=0, existing=0)

    legacy_root = load_tasks(workspace_root=workspace_root)
    legacy_source = legacy_path.as_posix()
    imported = 0
    existing = 0
    with connect_logs_database(workspace_root=workspace_root) as connection:
        for task in _walk_legacy_tasks(root=legacy_root):
            if insert_legacy_task(connection=connection, task=task, legacy_source=legacy_source):
                imported += 1
            else:
                existing += 1
    return BacklogMigrationReport(imported=imported, existing=existing)


def list_backlog_tasks(workspace_root: Path, domain: str | None = None, show_all: bool = False) -> list[BacklogTask]:
    """Migrate legacy tasks when needed, then return DB-backed backlog tasks."""
    migrate_legacy_backlog(workspace_root=workspace_root)
    return list_tasks(workspace_root=workspace_root, domain=domain, show_all=show_all)


def create_backlog_task(
    workspace_root: Path,
    domain: str,
    title: str,
    description: str,
    priority: str = "LOW",
) -> BacklogTask:
    """Create one working task after importing any legacy source task IDs."""
    normalized_domain = _normalize_domain(domain=domain)
    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("Task title must not be empty.")
    normalized_priority = _normalize_priority(priority=priority)
    migrate_legacy_backlog(workspace_root=workspace_root)
    return add_task_record(
        workspace_root=workspace_root,
        domain=normalized_domain,
        title=normalized_title,
        description=description.strip(),
        priority=normalized_priority,
    )


def set_backlog_task_status(workspace_root: Path, task_id: str, status: str) -> BacklogTask:
    """Set one task to `WORKING` or `DONE` and return its persistent record."""
    normalized_status = str(status).upper().strip()
    if normalized_status not in TASK_STATUSES:
        raise ValueError("Task status must be WORKING or DONE.")
    migrate_legacy_backlog(workspace_root=workspace_root)
    completed_at = _completed_at() if normalized_status == "DONE" else ""
    task = set_task_status_record(
        workspace_root=workspace_root,
        task_id=task_id,
        status=normalized_status,
        completed_at=completed_at,
    )
    if task is None:
        raise BacklogTaskNotFoundError(f"Task with ID '{normalize_task_id(task_id)}' not found.")
    return task


def edit_backlog_task(
    workspace_root: Path,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
) -> BacklogTask:
    """Edit supplied fields while preserving the task's current status."""
    migrate_legacy_backlog(workspace_root=workspace_root)
    normalized_title = title.strip() if title is not None else None
    if normalized_title is not None and not normalized_title:
        raise ValueError("Task title must not be empty.")
    normalized_priority = _normalize_priority(priority) if priority is not None else None
    task = edit_task_record(
        workspace_root=workspace_root,
        task_id=task_id,
        title=normalized_title,
        description=description.strip() if description is not None else None,
        priority=normalized_priority,
    )
    if task is None:
        raise BacklogTaskNotFoundError(f"Task with ID '{normalize_task_id(task_id)}' not found.")
    return task


def remove_backlog_task(workspace_root: Path, task_id: str, force: bool = False) -> None:
    """Delete a completed task, or explicitly override the guard with force."""
    migrate_legacy_backlog(workspace_root=workspace_root)
    task = get_task(workspace_root=workspace_root, task_id=task_id)
    if task is None:
        raise BacklogTaskNotFoundError(f"Task with ID '{normalize_task_id(task_id)}' not found.")
    if task.status != "DONE" and not force:
        raise BacklogTaskDeletionError(
            f"Task '{task.task_id}' is WORKING. Mark it DONE first or retry with --force.",
        )
    delete_task_record(workspace_root=workspace_root, task_id=task.task_id)


def build_task_tree(tasks: list[BacklogTask]) -> TaskNode:
    """Build the presentation tree from the durable flat task projection."""
    root = TaskNode("", 0)
    for task in tasks:
        current = root
        for level, part in enumerate(task.domain.split("."), start=1):
            if part not in current.children:
                current.children[part] = TaskNode(part, level)
            current = current.children[part]
        current.tasks.append(task.as_mapping())
    return root


def get_next_task_id(root: TaskNode) -> str:
    """Walk a legacy tree and return the next `tN` identifier."""
    max_num = 0
    for task in _walk_node_tasks(root=root):
        task_match = re.match(r"^t(\d+)$", str(task["id"]))
        if task_match:
            max_num = max(max_num, int(task_match.group(1)))
    return f"t{max_num + 1}"


def _walk_legacy_tasks(root: TaskNode) -> list[BacklogTask]:
    """Convert a parsed legacy tree into normalized migration records."""
    tasks: list[BacklogTask] = []

    def walk(node: TaskNode, path: list[str]) -> None:
        current_path = path if node.level == 0 else [*path, node.name]
        for task in node.tasks:
            status = str(task.get("status", "DONE" if task.get("checked") else "TODO"))
            tasks.append(
                BacklogTask(
                    task_id=normalize_task_id(str(task["id"])),
                    domain=".".join(current_path) or "backlog",
                    title=str(task.get("title", "")).strip(),
                    description=str(task.get("description", "")).strip(),
                    priority=_normalize_priority(str(task.get("priority", "LOW"))),
                    status=status,
                    completed_at=str(task.get("completed_at", "")).strip() if status == "DONE" else "",
                ),
            )
        for child in node.children.values():
            walk(child, current_path)

    walk(root, [])
    return tasks


def _walk_node_tasks(root: TaskNode) -> list[dict[str, object]]:
    """Return all legacy task mappings below a tree node."""
    found = list(root.tasks)
    for child in root.children.values():
        found.extend(_walk_node_tasks(root=child))
    return found


def _normalize_domain(domain: str) -> str:
    """Validate and normalize one dot-notated backlog domain."""
    parts = [part.strip() for part in str(domain).split(".") if part.strip()]
    if not parts:
        raise ValueError("Task domain must not be empty.")
    return ".".join(parts)


def _normalize_priority(priority: str) -> str:
    """Validate one priority value."""
    normalized = str(priority).upper().strip()
    if normalized not in PRIORITIES:
        raise ValueError("Task priority must be HIGH, MEDIUM, or LOW.")
    return normalized


def _completed_at() -> str:
    """Return the human-readable completion time used by existing task output."""
    return datetime.datetime.now().strftime("%d-%m-%Y %I:%M %p").lower()
