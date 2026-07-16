# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""CLI action to register a workspace project root."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from brain.infrastructure.runtime.paths import register_project_path, get_workspace_root
from brain.presentation.terminal import log_step, render_placeholders


def handle(args: argparse.Namespace) -> int:
    """
    Register a local project workspace root path to brain_mirrors.json.

    Args:
        args: Parsed CLI arguments.

    Returns:
        int: Process exit code.
    """
    path_value = getattr(args, "path", "")
    if not path_value:
        # Default to current WORKSPACE_ROOT
        project_path = get_workspace_root()
    else:
        project_path = Path(path_value).resolve()

    if not project_path.exists():
        print(f"Error: Target path '{project_path}' does not exist.", file=sys.stderr)
        return 1

    if not project_path.is_dir():
        print(f"Error: Target path '{project_path}' is not a directory.", file=sys.stderr)
        return 1

    color_enabled = getattr(args, "color", False)
    log_step(args, f"Registering project workspace: {project_path.name}...")
    try:
        register_project_path(project_path)
        msg = f"__GREEN__[SUCCESS] Successfully registered project '__CYAN__{project_path.name}__RESET__' at: {project_path}__RESET__"
        print(render_placeholders(msg, color_enabled))
        args.json_payload = {
            "ok": True,
            "command": getattr(args, "command", "register-project"),
            "project": {"name": project_path.name, "path": project_path.as_posix(), "registered": True},
        }
        return 0
    except Exception as exc:
        print(f"Error: Failed to register project: {exc}", file=sys.stderr)
        return 1
