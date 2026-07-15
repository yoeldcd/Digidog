"""Backlog tree terminal renderer."""

from __future__ import annotations

# Application Modules Imports
from brain.application.backlog.models import TaskNode


def render_tree(root: TaskNode, domain_filter: str | None = None, color_enabled: bool = False) -> str:
    """Generate a premium hierarchical tree string of tasks."""
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
        if node.level > 0:
            connector = "`-- " if is_last else "+-- "
            lines.append(f"{prefix}{connector}{node.name}/")
            next_prefix = prefix + ("    " if is_last else "|   ")
        else:
            next_prefix = ""

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
