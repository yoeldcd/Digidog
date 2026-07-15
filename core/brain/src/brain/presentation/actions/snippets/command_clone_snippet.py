"""Action module to clone snippets to the workspace."""

from __future__ import annotations

import argparse
import shutil
import os
from pathlib import Path
from brain.presentation.terminal import render_placeholders, log_step
from brain.infrastructure.runtime.paths import get_agent_home



def handle(args: argparse.Namespace) -> int:
    """Clone a snippet."""
    color_enabled = getattr(args, "color", False)
    try:
        snippet_name = args.name.strip()
        workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
        log_step(args, f"[1/2] Locating snippet '{snippet_name}'...")

        # Source path
        src_path = get_agent_home() / "snippets" / snippet_name
        if not src_path.exists() or src_path.name in ("brain", "core.py", "__pycache__"):
            msg = f"__RED__Error: Snippet '{snippet_name}' not found under the configured agent snippets.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        # Determine destination
        dest_rel = args.dest
        if not dest_rel:
            dest_dir = workspace_root / "$agent" / "scripts"
        else:
            dest_dir = workspace_root / dest_rel.strip()

        dest_path = dest_dir / snippet_name

        # Create parents
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Copy logic
        log_step(args, f"[2/2] Copying snippet to workspace...")
        if src_path.is_dir():
            if dest_path.exists():
                # Remove if it exists to overwrite cleanly
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
        else:
            shutil.copy2(src_path, dest_path)

        # Try to resolve relative path for nice print
        try:
            rel_dest = dest_path.relative_to(workspace_root)
            dest_display = f"./{rel_dest}"
        except ValueError:
            dest_display = str(dest_path)

        msg = f"__GREEN__Successfully cloned snippet__RESET__ '__CYAN__{snippet_name}__RESET__' to '__CYAN__{dest_display}__RESET__'."
        print(render_placeholders(msg, color_enabled))
        args.json_payload = {
            "ok": True,
            "command": "clone-snippet",
            "snippet": snippet_name,
            "source": src_path.as_posix(),
            "destination": dest_path.as_posix(),
            "kind": "folder" if src_path.is_dir() else "file",
        }
        return 0
    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
