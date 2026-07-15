"""Backlog persistence helpers backed by the local logs SQLite database."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path
import sqlite3
import time

# Application Modules Imports
from brain.application.backlog.models import BacklogTask, TaskNode
from brain.application.logs.store import connect_logs_database


BACKLOG_FILE_NAME = "backlog.md"
"""Canonical backlog filename."""


def get_backlog_path(workspace_root: Path) -> Path:
    """Return the legacy Markdown source path used only for migration."""
    return workspace_root / "$agent" / "data" / BACKLOG_FILE_NAME


def normalize_task_id(task_id: str) -> str:
    """Normalize a user-provided task identifier to the persisted `tN` form."""
    normalized = str(task_id).strip().lstrip("#")
    if not normalized:
        raise ValueError("Task ID must not be empty.")
    return normalized if normalized.startswith("t") else f"t{normalized}"


def list_tasks(workspace_root: Path, domain: str | None = None, show_all: bool = False) -> list[BacklogTask]:
    """Return persisted tasks, optionally limited to one domain subtree."""
    clauses: list[str] = []
    values: list[str] = []
    if domain:
        clauses.append("(domain = ? OR domain LIKE ?)")
        values.extend([domain, f"{domain}.%"])
    if not show_all:
        clauses.append("status != 'DONE'")
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect_logs_database(workspace_root=workspace_root) as connection:
        rows = connection.execute(
            f"""
            SELECT task_id, domain, title, description, priority, status, completed_at, created_at
            FROM backlog_tasks
            {where_sql}
            ORDER BY domain COLLATE NOCASE, created_at, task_id
            """,
            tuple(values),
        ).fetchall()
    return [_row_to_task(row) for row in rows]


def add_task_record(
    workspace_root: Path,
    domain: str,
    title: str,
    description: str,
    priority: str,
) -> BacklogTask:
    """Create and return one working task using a workspace-unique ID."""
    now = time.time()
    with connect_logs_database(workspace_root=workspace_root) as connection:
        connection.execute("BEGIN IMMEDIATE")
        task_id = _next_task_id(connection)
        connection.execute(
            """
            INSERT INTO backlog_tasks(
                task_id, domain, title, description, priority, status, completed_at,
                legacy_source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'TODO', '', '', ?, ?)
            """,
            (task_id, domain, title, description, priority, now, now),
        )
        row = connection.execute(
            """
            SELECT task_id, domain, title, description, priority, status, completed_at, created_at
            FROM backlog_tasks WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
    return _row_to_task(row)


def insert_legacy_task(connection: sqlite3.Connection, task: BacklogTask, legacy_source: str) -> bool:
    """Insert one legacy task when its ID has not been migrated before."""
    now = time.time()
    cursor = connection.execute(
        """
        INSERT INTO backlog_tasks(
            task_id, domain, title, description, priority, status, completed_at,
            legacy_source, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(task_id) DO NOTHING
        """,
        (
            task.task_id,
            task.domain,
            task.title,
            task.description,
            task.priority,
            task.status,
            task.completed_at,
            legacy_source,
            now,
            now,
        ),
    )
    return cursor.rowcount == 1


def get_task(workspace_root: Path, task_id: str) -> BacklogTask | None:
    """Return one task by normalized identifier."""
    normalized = normalize_task_id(task_id)
    with connect_logs_database(workspace_root=workspace_root) as connection:
        row = connection.execute(
            """
            SELECT task_id, domain, title, description, priority, status, completed_at, created_at
            FROM backlog_tasks WHERE task_id = ?
            """,
            (normalized,),
        ).fetchone()
    return _row_to_task(row) if row is not None else None


def set_task_status_record(workspace_root: Path, task_id: str, status: str, completed_at: str) -> BacklogTask | None:
    """Persist a validated task status and return the updated record."""
    normalized = normalize_task_id(task_id)
    with connect_logs_database(workspace_root=workspace_root) as connection:
        cursor = connection.execute(
            """
            UPDATE backlog_tasks
            SET status = ?, completed_at = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (status, completed_at, time.time(), normalized),
        )
        if cursor.rowcount != 1:
            return None
        row = connection.execute(
            """
            SELECT task_id, domain, title, description, priority, status, completed_at, created_at
            FROM backlog_tasks WHERE task_id = ?
            """,
            (normalized,),
        ).fetchone()
    return _row_to_task(row)


def edit_task_record(
    workspace_root: Path,
    task_id: str,
    title: str | None,
    description: str | None,
    priority: str | None,
) -> BacklogTask | None:
    """Update explicitly supplied task fields without changing task status."""
    normalized = normalize_task_id(task_id)
    changes: list[str] = []
    values: list[object] = []
    if title is not None:
        changes.append("title = ?")
        values.append(title)
    if description is not None:
        changes.append("description = ?")
        values.append(description)
    if priority is not None:
        changes.append("priority = ?")
        values.append(priority)
    if not changes:
        return get_task(workspace_root=workspace_root, task_id=normalized)
    changes.append("updated_at = ?")
    values.append(time.time())
    values.append(normalized)
    with connect_logs_database(workspace_root=workspace_root) as connection:
        cursor = connection.execute(
            f"UPDATE backlog_tasks SET {', '.join(changes)} WHERE task_id = ?",
            tuple(values),
        )
        if cursor.rowcount != 1:
            return None
        row = connection.execute(
            """
            SELECT task_id, domain, title, description, priority, status, completed_at, created_at
            FROM backlog_tasks WHERE task_id = ?
            """,
            (normalized,),
        ).fetchone()
    return _row_to_task(row)


def delete_task_record(workspace_root: Path, task_id: str) -> bool:
    """Delete one already-authorized task and report whether it existed."""
    normalized = normalize_task_id(task_id)
    with connect_logs_database(workspace_root=workspace_root) as connection:
        cursor = connection.execute("DELETE FROM backlog_tasks WHERE task_id = ?", (normalized,))
    return cursor.rowcount == 1


def _next_task_id(connection: sqlite3.Connection) -> str:
    """Return the next numeric task ID from the persistent store."""
    rows = connection.execute("SELECT task_id FROM backlog_tasks").fetchall()
    highest = 0
    for row in rows:
        value = str(row["task_id"])
        if value.startswith("t") and value[1:].isdigit():
            highest = max(highest, int(value[1:]))
    return f"t{highest + 1}"


def _row_to_task(row: sqlite3.Row) -> BacklogTask:
    """Map a SQLite backlog row into its application record."""
    return BacklogTask(
        task_id=str(row["task_id"]),
        domain=str(row["domain"]),
        title=str(row["title"]),
        description=str(row["description"]),
        priority=str(row["priority"]),
        status=str(row["status"]),
        completed_at=str(row["completed_at"] or ""),
        created_at=float(row["created_at"] or 0.0),
    )


def save_tasks(workspace_root: Path, root: TaskNode) -> None:
    """Serialize the TaskNode tree back to backlog.md."""
    tasks_file = get_backlog_path(workspace_root)
    tasks_file.parent.mkdir(parents=True, exist_ok=True)

    lines = []

    def serialize(node: TaskNode) -> None:
        if node.level > 0:
            lines.append(f"{'#' * node.level} {node.name}\n")
            # Sort node.tasks in the same order before serializing to backlog.md!
            def priority_weight(p: str) -> int:
                val = str(p).upper()
                if val == "HIGH":
                    return 0
                if val == "MEDIUM":
                    return 1
                return 2

            def task_sort_key(t: dict[str, object]) -> tuple[int, int, float, str]:
                st = str(t.get("status", "TODO")).upper()
                pr = str(t.get("priority", "LOW")).upper()
                cre = float(t.get("created_at") or 0.0)
                com = str(t.get("completed_at") or "")
                if st == "TODO":
                    return (0, priority_weight(pr), cre, "")
                elif st == "WORKING":
                    return (1, priority_weight(pr), cre, "")
                else:
                    return (2, 0, 0.0, com)

            sorted_tasks = sorted(node.tasks, key=task_sort_key)
            for task in sorted_tasks:
                st_val = str(task.get("status", "TODO")).upper()
                status = "x" if st_val == "DONE" else ("WORKING" if st_val == "WORKING" else " ")
                desc_suffix = f" - {task['description']}" if task["description"] else ""
                completed_suffix = f" (checked: {task['completed_at']})" if task.get("completed_at") else ""
                lines.append(f"- [{status}] #{task['id']} ({task['priority']}): {task['title']}{desc_suffix}{completed_suffix}")
            lines.append("")

        for child in sorted(node.children.values(), key=lambda item: item.name):
            serialize(child)

    serialize(root)

    output_text = "\n".join(lines).strip()
    if output_text:
        tasks_file.write_text(output_text + "\n", encoding="utf-8")
    else:
        if tasks_file.exists():
            tasks_file.unlink()
