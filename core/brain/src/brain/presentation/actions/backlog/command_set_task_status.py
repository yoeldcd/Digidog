# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Set one workspace backlog task state."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from brain.application.backlog.service import BacklogTaskNotFoundError, set_backlog_task_status
from brain.presentation.terminal import log_step, render_placeholders


def handle(args) -> int:
    """Set one task to `WORKING` or `DONE`."""
    workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
    color_enabled = getattr(args, "color", False)
    requested_status = str(args.status).upper().strip()
    log_step(args, f"Setting task '{args.task_id}' to {requested_status}...")
    try:
        task = set_backlog_task_status(
            workspace_root=workspace_root,
            task_id=args.task_id,
            status=requested_status,
        )
    except (BacklogTaskNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    message = f"__GREEN__[SUCCESS] Task '{task.task_id}' is now {task.status}.__RESET__"
    print(render_placeholders(message, color_enabled))
    args.narration_title = task.title
    args.narration_description = task.description
    args.json_payload = {"ok": True, "command": "set-task-status", "task": {**task.as_mapping(), "domain": task.domain}}
    return 0
