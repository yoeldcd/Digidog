"""Delete a task from the workspace backlog."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from brain.presentation.terminal import render_placeholders, log_step
from brain.application.backlog.service import BacklogTaskDeletionError, BacklogTaskNotFoundError, remove_backlog_task



def handle(args) -> int:
    workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
    color_enabled = getattr(args, "color", False)

    log_step(args, f"Deleting task '{args.task_id}'...")
    try:
        remove_backlog_task(workspace_root=workspace_root, task_id=args.task_id, force=bool(args.force))
    except (BacklogTaskDeletionError, BacklogTaskNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    safety = " with --force" if args.force else ""
    msg = f"__GREEN__[SUCCESS] Task '{args.task_id}' deleted safely{safety}.__RESET__"
    print(render_placeholders(msg, color_enabled))
    args.json_payload = {
        "ok": True,
        "command": "delete-task",
        "taskId": args.task_id,
        "deleted": True,
        "forced": bool(args.force),
    }
    return 0
