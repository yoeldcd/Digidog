"""Consumer-only CLI adapter for resolving opaque avatar message references."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from brain.presentation.avatar.communication.message_store import AvatarMessageStore


def handle(args: argparse.Namespace) -> int:
    store = AvatarMessageStore(Path.cwd())
    action = str(args.action).casefold().strip()
    message_id = str(args.message_id or "").strip()
    if not message_id:
        print("Error: resolve-avatar-message requires a message UUID.")
        return 2
    try:
        if action == "read":
            message = store.read(message_id)
            if message is None:
                print(json.dumps({"messageId": message_id, "found": False}) if args.json else "Message not found.")
                return 1
            consumed = store.acknowledge_consumed(message_id)
            payload = {"found": True, "consumed": consumed, "message": message.as_mapping()}
            print(json.dumps(payload, ensure_ascii=False) if args.json else message.text)
            return 0
        if action == "ack":
            changed = store.acknowledge_consumed(message_id)
            payload = {"messageId": message_id, "action": "ack", "changed": changed}
            print(json.dumps(payload) if args.json else "Consumed." if changed else "Message is not delivered.")
            return 0 if changed else 1
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2
    print("Error: resolve-avatar-message action must be read or ack.")
    return 2
