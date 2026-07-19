"""Manage picture recognition guidance in the unified brain configuration."""

from __future__ import annotations

import argparse
import json

from brain.application.pictures.guidance import (
    delete_picture_guidance_entry,
    list_picture_guidance,
    set_picture_guidance_entry,
)
from brain.infrastructure.pictures.guidance_graph import project_character_guidance


def handle(args: argparse.Namespace) -> int:
    """Execute one list, set, or delete picture-guidance command."""
    command = str(getattr(args, "command", ""))
    try:
        if command == "list-picture-guidance":
            guidance = list_picture_guidance(section=str(getattr(args, "section", "") or ""))
            payload = {"ok": True, "command": command, "guidance": guidance}
        elif command == "set-picture-guidance":
            entry = set_picture_guidance_entry(
                section=str(args.section),
                name=str(args.name),
                description=str(args.description),
            )
            graph = (
                project_character_guidance(name=entry["name"], description=entry["description"])
                if entry["section"] == "characters"
                else None
            )
            payload = {"ok": True, "command": command, "entry": entry, "graph": graph}
        elif command == "delete-picture-guidance":
            entry = delete_picture_guidance_entry(section=str(args.section), name=str(args.name))
            payload = {"ok": True, "command": command, "deleted": entry}
        else:
            raise ValueError(f"Unsupported picture guidance command `{command}`.")
        exit_code = 0
    except Exception as exc:
        payload = {"ok": False, "command": command, "error": str(exc)}
        exit_code = 1
    args.json_payload = payload
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload["ok"]:
        _print_success(payload=payload)
    else:
        print(f"Error: {payload['error']}")
    return exit_code


def _print_success(payload: dict[str, object]) -> None:
    """Render concise human output for one successful guidance operation."""
    command = str(payload["command"])
    if command == "list-picture-guidance":
        guidance = payload["guidance"]
        assert isinstance(guidance, dict)
        for section, entries in guidance.items():
            print(f"{section}:")
            for name, description in entries.items():
                print(f"  {name}: {description}")
        return
    entry_key = "entry" if command == "set-picture-guidance" else "deleted"
    entry = payload[entry_key]
    assert isinstance(entry, dict)
    verb = "Updated" if command == "set-picture-guidance" else "Deleted"
    print(f"{verb} picture guidance {entry['section']} entry: {entry['name']}")
