"""Action module to read a complete agent profile."""

from __future__ import annotations

import argparse
import json

from brain.presentation.terminal import render_markdown, render_placeholders, log_step
from brain.application.profiles.service import read_profile_entries, render_profile



def handle(args: argparse.Namespace) -> int:
    """Print a complete profile composed from all profile Markdown entries."""
    color_enabled = getattr(args, "color", False)
    try:
        log_step(args, "Reading profile...")
        entries = read_profile_entries(args.name)

        if args.json:
            records = [{"key": key, "content": content} for key, content in entries]
            print(json.dumps({"ok": True, "profile": args.name, "entries": records}, ensure_ascii=False, indent=2))
            return 0

        print(render_markdown(render_profile(args.name, entries), color_enabled), end="")
        return 0
    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
