# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to list available agent profiles."""

from __future__ import annotations

import argparse
import json

from brain.presentation.terminal import render_markdown, render_placeholders, log_step
from brain.application.profiles.service import discover_profile_names, profile_summaries



def handle(args: argparse.Namespace) -> int:
    """List the available agent profiles for human or JSON consumers.

    Args:
        args (argparse.Namespace): Parsed command options controlling output
            formatting and activity logging.

    Returns:
        int: Zero when profiles are listed; otherwise one after reporting an
            error.
    """
    color_enabled = getattr(args, "color", False)
    try:
        log_step(args, "Loading available profiles...")
        profile_names = discover_profile_names()

        if args.json:
            print(json.dumps({"ok": True, "profiles": profile_summaries()}, ensure_ascii=False, indent=2))
            return 0

        if not profile_names:
            print(render_placeholders("__YELLOW__No profiles found.__RESET__", color_enabled))
            return 0

        output = ["# Available Profiles", ""]
        output.extend(f"- **{name}**" for name in profile_names)
        output.append("")
        output.append("Helper: read a complete profile with `read-profile <NAME>`.")
        output.append("Example: `read-profile developer`")

        print(render_markdown("\n".join(output), color_enabled))
        return 0
    except Exception as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
