"""Mark a task as finished in the workspace backlog."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from brain.presentation.terminal import render_placeholders, log_step
from brain.application.backlog.service import BacklogTaskNotFoundError, set_backlog_task_status



def handle(args) -> int:
    workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
    color_enabled = getattr(args, "color", False)

    log_step(args, f"Finishing task '{args.task_id}'...")
    try:
        task = set_backlog_task_status(workspace_root=workspace_root, task_id=args.task_id, status="DONE")
    except (BacklogTaskNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    msg = f"__GREEN__[SUCCESS] Task '{args.task_id}' finished.__RESET__"
    print(render_placeholders(msg, color_enabled))
    args.narration_title = task.title
    args.narration_description = task.description
    args.json_payload = {"ok": True, "command": "task-finished", "task": {**task.as_mapping(), "domain": task.domain}}
    return 0
