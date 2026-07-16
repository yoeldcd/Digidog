# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Display the workspace backlog, optionally filtered by domain."""

from __future__ import annotations

import os
from pathlib import Path

from brain.presentation.terminal import render_placeholders
from brain.application.backlog.rendering import render_tree
from brain.application.backlog.service import build_task_tree, list_backlog_tasks



def handle(args) -> int:
    workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
    color_enabled = getattr(args, "color", False)

    show_all = getattr(args, "all", False)
    tasks = list_backlog_tasks(workspace_root=workspace_root, domain=args.task_domain, show_all=show_all)
    root = build_task_tree(tasks)
    tree_str = render_tree(root, domain_filter=args.task_domain, color_enabled=color_enabled)
    print(render_placeholders(tree_str, color_enabled))
    pending_tasks = [task for task in tasks if not task.done]
    args.narration_task_count = len(pending_tasks)
    args.narration_task_list = [
        {"title": task.title, "priority": task.priority}
        for task in pending_tasks
    ]
    args.json_payload = {
        "ok": True,
        "command": "show-backlog",
        "domain": args.task_domain,
        "includeDone": show_all,
        "count": len(tasks),
        "tasks": [{**task.as_mapping(), "domain": task.domain} for task in tasks],
    }
    return 0
