# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""CLI adapter for the durable avatar-to-Codex outbox."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from brain.infrastructure.runtime.paths import get_workspace_root
from brain.presentation.avatar.communication.outbox.repository import AvatarOutboxRepository


def handle(args: argparse.Namespace) -> int:
    """List, claim, acknowledge, or release durable avatar outbox messages.

    Args:
        args (argparse.Namespace): Parsed command options selecting the outbox
            action, message ID, lease token, limit, and output format.

    Returns:
        int: Zero when the action succeeds, one for an unmatched lease or absent
            message, or two for invalid arguments.
    """
    repository = AvatarOutboxRepository(get_workspace_root())
    action = str(args.action).casefold().strip()

    # Conditional check: evaluate domain preconditions and invariants
    if action == "list":
        messages = [message.as_mapping() for message in repository.pending(args.limit)]
        payload = {"pending": messages, "count": len(messages)}
        print(json.dumps(payload, ensure_ascii=False) if args.json else _render(messages))
        return 0

    # Conditional check: evaluate domain preconditions and invariants
    if action == "claim":
        claim_token, claimed = repository.claim(args.limit, args.lease_seconds)
        messages = [message.as_mapping() for message in claimed]
        payload = {"claimToken": claim_token, "claimed": messages, "count": len(messages)}
        print(json.dumps(payload, ensure_ascii=False) if args.json else _render(messages))
        return 0

    # Conditional check: evaluate domain preconditions and invariants
    if action in {"ack", "release"}:
        message_id = str(args.message_id or "").strip()
        claim_token = str(args.claim_token or "").strip()

        # Identity validation: check canonical message or instance identifier
        if not message_id or not claim_token:
            print(f"Error: avatar-outbox {action} requires message_id and --claim-token.")
            return 2
        changed = (
            repository.acknowledge(message_id, claim_token)

            # Conditional check: evaluate domain preconditions and invariants
            if action == "ack"
            else repository.release(message_id, claim_token)
        )
        payload = {"messageId": message_id, "action": action, "changed": changed}
        print(json.dumps(payload) if args.json else f"{action.title()}: {message_id}" if changed else "Lease mismatch.")
        return 0 if changed else 1
    print("Error: avatar-outbox action must be list, claim, ack, or release.")
    return 2


def _render(messages: list[dict[str, object]]) -> str:
    """Render a list of pending avatar outbox messages as a text list.

    Formats each pending message into a readable string showing its message ID,
    associated Codex thread identifier, and host process identifier.

    Args:
        messages (list[dict[str, object]]): List of pending outbox message records.

    Returns:
        str: Formatted multi-line text listing message targets, or fallback text.
    """
    # Conditional check: evaluate domain preconditions and invariants
    if not messages:
        return "No pending avatar references."
    return "\n".join(
        f"{message['message_id']} -> {message['thread_id']}@{message['host_id']}"

        # Iteration: process collection elements sequentially
        for message in messages
    )
