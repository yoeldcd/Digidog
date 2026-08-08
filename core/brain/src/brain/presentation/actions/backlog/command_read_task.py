# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Read and display a specific task from the backlog."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from brain.application.backlog.service import BacklogTaskNotFoundError, get_backlog_task
from brain.presentation.terminal import render_placeholders


def handle(args: argparse.Namespace) -> int:
    """Read one backlog task by ID or number.

    Args:
        args (argparse.Namespace): Parsed options containing task_id or --id flag.

    Returns:
        int: Zero when task is read successfully; otherwise non-zero on error.
    """
    workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
    color_enabled = getattr(args, "color", False)
    is_json = getattr(args, "json", False)

    raw_id = getattr(args, "id", "") or getattr(args, "task_id", "") or ""
    raw_id = str(raw_id).strip()

    if not raw_id:
        err_msg = "Task ID is required. Use 'read-task <TASK_ID>' or 'read-task --id <TASK_ID>'."
        if is_json:
            args.json_payload = {"ok": False, "command": "read-task", "error": err_msg}
            print(json.dumps(args.json_payload, indent=2))
        else:
            print(f"Error: {err_msg}", file=sys.stderr)
        return 1

    try:
        task = get_backlog_task(workspace_root=workspace_root, task_id=raw_id)
    except (BacklogTaskNotFoundError, ValueError) as exc:
        err_text = str(exc)
        if is_json:
            args.json_payload = {"ok": False, "command": "read-task", "error": err_text}
            print(json.dumps(args.json_payload, indent=2))
        else:
            print(f"Error: {err_text}", file=sys.stderr)
        return 1

    task_mapping = task.as_mapping()
    payload = {
        "ok": True,
        "command": "read-task",
        "task": {
            **task_mapping,
            "domain": task.domain,
        },
    }
    args.json_payload = payload

    if is_json:
        print(json.dumps(payload, indent=2))
        return 0

    print(render_placeholders(f"__CYAN__Task [{task.task_id}]__RESET__ - {task.title}", color_enabled))
    print(
        render_placeholders(
            f"__YELLOW__Status:__RESET__ {task.status} | "
            f"__YELLOW__Priority:__RESET__ {task.priority} | "
            f"__YELLOW__Domain:__RESET__ {task.domain}",
            color_enabled,
        )
    )
    if task.created_at:
        print(f"Created At: {task.created_at}")
    if task.completed_at:
        print(f"Completed At: {task.completed_at}")
    print()
    if task.description:
        print("Description:")
        print(task.description)
        print()

    return 0
