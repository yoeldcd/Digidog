# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Backlog tree terminal renderer."""

from __future__ import annotations

# Standard Libraries Imports
from dataclasses import replace
from pathlib import Path

# Application Modules Imports
from brain.application.backlog.models import BacklogTask, TaskNode


BACKLOG_IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "gif", "webp")
"""Supported persisted visual-reference extensions in deterministic lookup order."""


def resolve_task_reference_path(task_id: str, workspace_root: Path) -> str | None:
    """Return the canonical existing visual-reference path for one task.

    Args:
        task_id: Stable task identifier used by the attachment filename.
        workspace_root: Workspace containing the ``$agent/pictures`` attachment store.

    Returns:
        str | None: Canonical workspace-relative attachment path, or ``None``
        when no supported attachment exists.
    """
    pictures_dir = workspace_root / "$agent" / "pictures"
    for extension in BACKLOG_IMAGE_EXTENSIONS:
        filename = f"backlog-pic-{task_id}.{extension}"
        if (pictures_dir / filename).is_file():
            return f"$agent/pictures/{filename}"

    return None


def resolve_task_reference(task: BacklogTask, workspace_root: Path) -> BacklogTask:
    """Resolve a task's visual-reference marker for read-only CLI projection.

    Args:
        task: Persistent backlog task whose description may contain ``{ref_image}``.
        workspace_root: Workspace containing the ``$agent/pictures`` attachment store.

    Returns:
        A projected task with the marker replaced by its canonical workspace-relative
        path, or the original task when no marker or attachment exists.
    """
    if "{ref_image}" not in task.description:
        return task

    reference_path = resolve_task_reference_path(task.task_id, workspace_root)
    if reference_path is None:
        return task

    return replace(task, description=task.description.replace("{ref_image}", reference_path))


def render_task_table(tasks: list[BacklogTask]) -> str:
    """Render backlog task details as a visual-only Markdown table.

    Args:
        tasks (list[BacklogTask]): Tasks selected by command filters.

    Returns:
        str: Complete Markdown table, or a concise empty-state message.
    """
    if not tasks:
        return "No tasks registered in this workspace."

    lines = [
        "| ID | Status | Priority | Domain | Title | Description |",
        "|---|---|---|---|---|---|",
    ]
    for task in sorted(tasks, key=_task_table_sort_key):
        cells = (
            task.task_id,
            task.status,
            task.priority,
            task.domain,
            task.title,
            task.description or "—",
        )
        escaped_cells = (_escape_table_cell(cell) for cell in cells)
        lines.append(f"| {' | '.join(escaped_cells)} |")
    return "\n".join(lines)


def _task_table_sort_key(task: BacklogTask) -> tuple[int, int, float, str]:
    """Return stable status, priority, creation, and identifier ordering.

    Args:
        task (BacklogTask): Task whose display order is required.

    Returns:
        tuple[int, int, float, str]: Ascending deterministic table sort key.
    """
    status_weight = {"WORKING": 0, "TODO": 1, "DONE": 2}.get(task.status, 3)
    priority_weight = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(task.priority, 3)
    return status_weight, priority_weight, task.created_at, task.task_id


def _escape_table_cell(value: object) -> str:
    """Escape one value for a single-line Markdown table cell.

    Args:
        value (object): Raw task field rendered inside a table cell.

    Returns:
        str: Single-line text with pipe delimiters escaped.
    """
    return str(value).replace("|", r"\|").replace("\r", " ").replace("\n", " ").strip()


def render_tree(root: TaskNode, domain_filter: str | None = None, color_enabled: bool = False) -> str:
    """Generate a premium hierarchical tree string of tasks.

    Args:
        root: `TaskNode`. The root TaskNode of the backlog hierarchy to render.
        domain_filter: `str | None`. An optional dot-separated string used to traverse the tree to a specific domain before rendering.
        color_enabled: `bool`. A flag indicating whether to include terminal color formatting tags in the output.

    Returns:
        str: A multi-line string representing the visual tree of tasks or a message indicating no tasks were found.
    """
    start_node = root
    if domain_filter:
        parts = [part.strip() for part in domain_filter.split(".") if part.strip()]
        for part in parts:
            if part in start_node.children:
                start_node = start_node.children[part]
            else:
                return "No tasks found matching filter."

    if start_node.is_empty():
        return "No tasks registered in this workspace."

    lines = []

    def draw_node(node: TaskNode, prefix: str = "", is_last: bool = True) -> None:
        """Recursively processes a TaskNode to append its tasks and child nodes to the rendering buffer with appropriate tree connectors.

        Args:
            node: `TaskNode`. The current TaskNode being rendered.
            prefix: `str`. The indentation prefix inherited from parent nodes to maintain tree structure.
            is_last: `bool`. A boolean indicating if the current node is the last sibling in its group, determining the connector style.
        """
        if node.level > 0:
            connector = "`-- " if is_last else "+-- "
            lines.append(f"{prefix}{connector}{node.name}/")
            next_prefix = prefix + ("    " if is_last else "|   ")
        else:
            next_prefix = ""

        def priority_weight(p: str) -> int:
            """Maps a priority string to a numeric weight to facilitate sorting, where higher priority tasks receive lower numeric values.

            Args:
                p: `str`. The priority label string to evaluate.

            Returns:
                int: An integer weight representing the priority level.
            """
            val = str(p).upper()
            if val == "HIGH":
                return 0
            if val == "MEDIUM":
                return 1
            return 2

        def task_sort_key(t: dict[str, object]) -> tuple[int, int, float, str]:
            """Calculates a sorting tuple for a task based on its status, priority weight, creation timestamp, and completion date.

            Args:
                t: `dict[str, object]`. A dictionary containing task attributes.

            Returns:
                tuple[int, int, float, str]: A tuple used as a sort key to order tasks by status, priority, and chronology.
            """
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
        all_items = []
        for task in sorted_tasks:
            status = str(task.get("status", "DONE" if task.get("checked") else "TODO")).upper()
            status_box = "[ ]" if status == "TODO" else f"[{status}]"

            priority_val = str(task.get("priority", "LOW")).upper()
            priority_text = f" ({priority_val})"
            if color_enabled:
                if priority_val == "HIGH":
                    priority_text = " __RED__(HIGH)__RESET__"
                elif priority_val == "MEDIUM":
                    priority_text = " __YELLOW__(MEDIUM)__RESET__"
                else:
                    priority_text = " __DIM__(LOW)__RESET__"

            if color_enabled:
                if status == "DONE":
                    status_text = f"__GREEN__{status_box} #{task['id']}__RESET__{priority_text}"
                elif status == "WORKING":
                    status_text = f"__CYAN__{status_box} #{task['id']}__RESET__{priority_text}"
                else:
                    status_text = f"__DIM__{status_box} #{task['id']}__RESET__{priority_text}"
            else:
                status_text = f"{status_box} #{task['id']}{priority_text}"

            desc_suffix = f" - {task['description']}" if task["description"] else ""
            completed_at = task.get("completed_at", "")
            completed_suffix = f" (completed: {completed_at})" if completed_at else ""
            if color_enabled and completed_at:
                completed_suffix = f" __DIM__(completed: {completed_at})__RESET__"

            all_items.append((False, f"{status_text}: {task['title']}{desc_suffix}{completed_suffix}"))

        sorted_children = sorted(node.children.values(), key=lambda item: item.name)
        for child in sorted_children:
            if not child.is_empty():
                all_items.append((True, child))

        for index, (is_subfolder, item) in enumerate(all_items):
            item_is_last = index == len(all_items) - 1
            if is_subfolder:
                draw_node(item, next_prefix, item_is_last)
            else:
                item_connector = "`-- " if item_is_last else "+-- "
                lines.append(f"{next_prefix}{item_connector}{item}")

    if start_node.level > 0:
        draw_node(start_node, prefix="", is_last=True)
    else:
        sorted_top = sorted(start_node.children.values(), key=lambda item: item.name)
        active_top = [child for child in sorted_top if not child.is_empty()]
        for index, child in enumerate(active_top):
            draw_node(child, prefix="", is_last=(index == len(active_top) - 1))

    return "\n".join(lines)
