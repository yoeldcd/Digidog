"""Edit one workspace backlog task through the SQLite-backed service."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from brain.application.backlog.service import BacklogTaskNotFoundError, edit_backlog_task
from brain.presentation.terminal import log_step, render_placeholders


def handle(args) -> int:
    """Persist explicitly supplied task fields without changing its status."""
    workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
    color_enabled = getattr(args, "color", False)
    log_step(args, f"Editing task '{args.task_id}'...")
    try:
        task = edit_backlog_task(
            workspace_root=workspace_root,
            task_id=args.task_id,
            title=args.title,
            description=args.description,
            priority=args.priority,
        )
    except (BacklogTaskNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    message = f"__GREEN__[SUCCESS] Task '{task.task_id}' updated without changing {task.status} state.__RESET__"
    print(render_placeholders(message, color_enabled))
    args.narration_title = task.title
    args.narration_description = task.description
    args.json_payload = {"ok": True, "command": "edit-task", "task": {**task.as_mapping(), "domain": task.domain}}
    return 0
