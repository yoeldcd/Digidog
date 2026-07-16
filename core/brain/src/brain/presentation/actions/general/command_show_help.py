# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""CLI action for displaying command help."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from brain.presentation.views.help.rendering import get_command_help_text, get_help_text, get_short_help_text

def handle(args: argparse.Namespace) -> int:
    """Print CLI usage instructions."""
    color_enabled = getattr(args, "color", False)
    topic = getattr(args, "topic", None)
    short_enabled = bool(getattr(args, "short", False))
    if short_enabled:
        print(get_short_help_text(topic=topic, color=color_enabled))
    elif topic:
        print(get_command_help_text(topic, color_enabled))
    else:
        print(get_help_text(color_enabled))
    from brain.presentation.commands.registry import COMMAND_MODULES

    commands = []
    for module in COMMAND_MODULES:
        schema = module.SCHEMA
        if topic and topic not in {schema.name, *schema.aliases, schema.domain}:
            continue
        commands.append(asdict(schema))
    args.json_payload = {
        "ok": True,
        "command": "help",
        "topic": topic,
        "short": short_enabled,
        "count": len(commands),
        "commands": commands,
    }
    return 0
