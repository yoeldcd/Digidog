# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Consumer-only CLI adapter for resolving opaque avatar message references."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from brain.infrastructure.runtime.paths import get_workspace_root
from brain.presentation.avatar.communication.outbox.message_store import AvatarMessageStore


def handle(args: argparse.Namespace) -> int:
    """Read or acknowledge one opaque durable avatar message reference.

    Args:
        args (argparse.Namespace): Parsed command options selecting the message
            UUID, action, and output format.

    Returns:
        int: Zero when the requested operation succeeds, one for a missing message
            or failed acknowledgement, or two for invalid arguments.
    """
    store = AvatarMessageStore(get_workspace_root())
    action = str(args.action).casefold().strip()
    message_id = str(args.message_id or "").strip()

    # Identity validation: check canonical message or instance identifier
    if not message_id:
        print("Error: resolve-avatar-message requires a message UUID.")
        return 2

    # Exception safety: execute operation within protected error boundary
    try:
        # Conditional check: evaluate domain preconditions and invariants
        if action == "read":
            message = store.read(message_id)

            # Conditional check: evaluate domain preconditions and invariants
            if message is None:
                print(json.dumps({"messageId": message_id, "found": False}) if args.json else "Message not found.")
                return 1
            consumed = store.acknowledge_consumed(message_id)
            payload = {"found": True, "consumed": consumed, "message": message.as_mapping()}
            print(json.dumps(payload, ensure_ascii=False) if args.json else message.text)
            return 0

        # Conditional check: evaluate domain preconditions and invariants
        if action == "ack":
            changed = store.acknowledge_consumed(message_id)
            payload = {"messageId": message_id, "action": "ack", "changed": changed}
            print(json.dumps(payload) if args.json else "Consumed." if changed else "Message is not delivered.")
            return 0 if changed else 1

    # Validation handling: handle invalid input domain error
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2
    print("Error: resolve-avatar-message action must be read or ack.")
    return 2
