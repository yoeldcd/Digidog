# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""CLI action for displaying command help.

Parses topic and presentation options to render general or command-specific
usage documentation, filtering listed commands by caller authority permissions.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict

from brain.presentation.views.help.rendering import (
    _get_authorized_schema_entries,
    get_command_help_text,
    get_help_text,
    get_short_help_text,
)


def _json_safe_schema_value(value: object) -> object:
    """Convert command-schema values into stable JSON-compatible data.

    Recursively converts dataclass schemas and type labels into plain dictionaries,
    lists, and strings suitable for JSON serialization. Ensures schema objects can
    be serialized directly to JSON output without type reflection errors.

    Args:
        value: Recursive value produced by dataclasses.asdict.

    Returns:
        object: JSON-safe primitives, mappings, and sequences with type names.
    """

    # Type check: format raw type object as class name string

    if isinstance(value, type):
        return value.__name__

    # Dict conversion: recursively sanitize mapping keys and item values

    if isinstance(value, dict):
        return {str(key): _json_safe_schema_value(item) for key, item in value.items()}

    # Sequence conversion: recursively sanitize list or tuple items

    if isinstance(value, (list, tuple)):
        return [_json_safe_schema_value(item) for item in value]

    return value


def handle(args: argparse.Namespace) -> int:
    """Render general, short, or topic-specific CLI usage instructions.

    Filters available commands based on the caller authority provided in args,
    rendering either terminal formatted help text or structured JSON payloads.

    Args:
        args: Parsed help topic, output mode, color, and authority flags.

    Returns:
        int: Zero after rendering help and its JSON payload.
    """
    color_enabled = getattr(args, "color", False)
    topic = getattr(args, "topic", None)
    short_enabled = bool(getattr(args, "short", False))
    authority = getattr(args, "authority", None)
    authority_is_valid = isinstance(authority, str) and bool(authority.strip())

    # Presentation mode: select help document layout based on user flags

    if short_enabled:
        short_topic = topic if authority_is_valid else None
        print(
            get_short_help_text(
                topic=short_topic,
                color=color_enabled,
                authority=authority,
            )
        )

    elif topic and authority_is_valid:
        print(get_command_help_text(topic, color_enabled, authority=authority))

    else:
        print(get_help_text(color_enabled, authority=authority))

    commands: list[object] = []

    # Iteration: collect command schemas authorized for the caller

    for schema, access_status in _get_authorized_schema_entries(authority):

        # Topic check: filter commands matching requested topic name or domain

        if topic and topic not in {schema.name, *schema.aliases, schema.domain}:
            continue

        schema_payload = _json_safe_schema_value(asdict(schema))

        if access_status == "request_password" and isinstance(schema_payload, dict):
            schema_payload["requires_password"] = True

        commands.append(schema_payload)

    args.json_payload = {
        "ok": True,
        "command": "help",
        "topic": topic,
        "short": short_enabled,
        "count": len(commands),
        "commands": commands,
    }

    return 0
