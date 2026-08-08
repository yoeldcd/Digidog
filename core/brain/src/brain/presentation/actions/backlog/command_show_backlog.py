# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Display the workspace backlog, optionally filtered by domain."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from brain.application.backlog.rendering import render_task_table, resolve_task_reference
from brain.application.backlog.service import list_backlog_tasks
from brain.presentation.terminal import render_markdown



def _status_emoji(status: str) -> str:
    """Return the compact visual marker for one backlog lifecycle state."""
    return {'WORKING': '🛠️', 'DONE': '✅'}.get(status, '🕒')


def _priority_emoji(priority: str) -> str:
    """Return the compact visual marker for one backlog priority."""
    return {'HIGH': '🔴', 'MEDIUM': '🟠', 'LOW': '🟢'}.get(priority, '⚪')


def handle(args: argparse.Namespace) -> int:
    """Render workspace backlog tasks, optionally restricted to one domain.

    Args:
        args (argparse.Namespace): Parsed command options containing the optional
            domain filter and completed-task inclusion flag.

    Returns:
        int: Always zero after rendering the requested task tree.
    """
    workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
    color_enabled = getattr(args, "color", False)

    show_all = getattr(args, "all", False)
    tasks = list_backlog_tasks(workspace_root=workspace_root, domain=args.task_domain, show_all=show_all)
    projected_tasks = [resolve_task_reference(task=task, workspace_root=workspace_root) for task in tasks]
    table = render_task_table(tasks=projected_tasks)
    print(render_markdown(table, color_enabled))
    pending_tasks = [task for task in tasks if not task.done]
    args.narration_task_count = len(pending_tasks)
    args.narration_output = ''
    args.narration_table_columns = ['estado', 'dominio', 'tarea']
    args.narration_table_rows = [
        {'estado': f'{_status_emoji(task.status)} `{task.status}` · {_priority_emoji(task.priority)} `{task.priority}`', 'dominio': task.domain,
         'tarea': f'`{task.task_id}` — {task.title}'}
        for task in projected_tasks
    ]
    args.json_payload = {
        "ok": True,
        "command": "show-backlog",
        "domain": args.task_domain,
        "includeDone": show_all,
        "count": len(tasks),
        "tasks": [{**task.as_mapping(), "domain": task.domain} for task in projected_tasks],
    }
    return 0
