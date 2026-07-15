"""Action module to search or list available snippets."""

from __future__ import annotations

import argparse
from pathlib import Path
from brain.presentation.terminal import render_placeholders, log_step
from brain.infrastructure.runtime.paths import get_agent_home



def handle(args: argparse.Namespace) -> int:
    """List snippets directory."""
    color_enabled = getattr(args, "color", False)
    try:
        log_step(args, 'Scanning available snippets...')
        # Support both --filter and direct positional query
        query = getattr(args, "filter", None) or getattr(args, "query", None)
        snippets_dir = get_agent_home() / "snippets"

        if not snippets_dir.exists():
            msg = "__RED__Error: Snippets directory does not exist.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        # Collect top-level items, ignoring brain and core.py
        items = []
        for p in snippets_dir.iterdir():
            if p.name in ("brain", "core.py", "__pycache__"):
                continue
            if query:
                if query.lower() in p.name.lower():
                    items.append(p)
            else:
                items.append(p)

        # Sort items
        items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

        if not items:
            if query:
                print(f"No snippets found matching filter '{query}'.")
            else:
                print("No snippets available.")
            args.json_payload = {"ok": True, "command": "list-snippets", "filter": query, "count": 0, "snippets": []}
            return 0

        output = ["# Available Snippets", ""]
        snippets = []
        for p in items:
            t_type = "Folder" if p.is_dir() else "File"
            desc = ""
            # Try to read a description if it's a folder with a README.md or script header
            if p.is_dir():
                readme = p / "README.md"
                if readme.exists():
                    lines = readme.read_text(encoding="utf-8").splitlines()
                    # get first non-empty header or line
                    for line in lines:
                        if line.strip() and not line.startswith("#"):
                            desc = f" - {line.strip()}"
                            break
            else:
                # Try to read first comment/docstring line
                try:
                    lines = p.read_text(encoding="utf-8").splitlines()
                    for line in lines:
                        clean = line.strip().strip("#").strip('"').strip("'").strip()
                        if clean:
                            desc = f" - {clean}"
                            break
                except Exception:
                    pass
            output.append(f"- **{p.name}** ({t_type}){desc}")
            snippets.append({
                "name": p.name,
                "kind": t_type.lower(),
                "description": desc.removeprefix(" - "),
                "path": p.as_posix(),
            })

        print("\n".join(output))
        args.json_payload = {
            "ok": True,
            "command": "list-snippets",
            "filter": query,
            "count": len(snippets),
            "snippets": snippets,
        }
        return 0
    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
