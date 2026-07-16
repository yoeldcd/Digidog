# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Add a task under a specified domain path in the workspace."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from brain.presentation.terminal import render_placeholders, log_step
from brain.application.backlog.service import create_backlog_task



def handle(args) -> int:
    # Resolve title and description from positional or flag forms
    title = args.title if args.title is not None else args.title_pos
    description = args.description if args.description is not None else args.description_pos

    if not title:
        print("Error: title must be provided via --title or positional form.", file=sys.stderr)
        return 1

    priority = (args.priority or "LOW").upper()
    if priority not in ("HIGH", "MEDIUM", "LOW"):
        print("Error: priority must be HIGH, MEDIUM, or LOW.", file=sys.stderr)
        return 1

    workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
    color_enabled = getattr(args, "color", False)

    log_step(args, f"Adding task under domain '{args.task_domain}' with priority {priority}...")
    try:
        task = create_backlog_task(workspace_root, args.task_domain, title, description or "", priority=priority)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    msg = f"__GREEN__[SUCCESS] Added task #{task.task_id} ({priority}): {title}__RESET__"
    print(render_placeholders(msg, color_enabled))
    args.narration_task_id = task.task_id
    args.narration_title = task.title
    args.narration_description = task.description
    args.json_payload = {"ok": True, "command": "add-task", "task": {**task.as_mapping(), "domain": task.domain}}
    return 0
