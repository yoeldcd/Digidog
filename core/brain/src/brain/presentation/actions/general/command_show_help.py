# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""CLI action for displaying command help."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from brain.presentation.views.help.rendering import get_command_help_text, get_help_text, get_short_help_text


def _json_safe_schema_value(value: object) -> object:
    """Convert command-schema values into stable JSON-compatible data.

    Args:
        value: Recursive value produced by ``dataclasses.asdict``.

    Returns:
        JSON-safe primitives, mappings, and sequences with type objects named.
    """
    if isinstance(value, type):
        return value.__name__
    if isinstance(value, dict):
        return {str(key): _json_safe_schema_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_schema_value(item) for item in value]
    return value


def handle(args: argparse.Namespace) -> int:
    """Render general, short, or topic-specific CLI usage instructions.

    Args:
        args (argparse.Namespace): Parsed help topic, output mode, and color flags.

    Returns:
        int: Zero after rendering help and its JSON payload.
    """
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
        commands.append(_json_safe_schema_value(asdict(schema)))
    args.json_payload = {
        "ok": True,
        "command": "help",
        "topic": topic,
        "short": short_enabled,
        "count": len(commands),
        "commands": commands,
    }
    return 0
