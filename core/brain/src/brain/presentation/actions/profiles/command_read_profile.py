# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to read a complete agent profile."""

from __future__ import annotations

import argparse
import json

from brain.application.profiles.service import (
    read_profile_entries,
    render_profile,
    render_profile_template_variables,
)
from brain.presentation.terminal import log_step, render_markdown, render_placeholders


def handle(args: argparse.Namespace) -> int:
    """Render one profile composed from its persisted Markdown entries.

    Args:
        args (argparse.Namespace): Parsed command options containing the profile
            name and output format.

    Returns:
        int: Zero when the profile is rendered; otherwise one after reporting an
            error.
    """
    color_enabled = getattr(args, "color", False)
    try:
        log_step(args, "Reading profile...")
        raw_entries = read_profile_entries(args.name)
        entries = [
            (key, render_profile_template_variables(content))
            for key, content in raw_entries
        ]

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
