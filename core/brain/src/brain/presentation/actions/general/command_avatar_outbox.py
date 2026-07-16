# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""CLI adapter for the durable avatar-to-Codex outbox."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from brain.presentation.avatar.communication.outbox import AvatarOutboxRepository


def handle(args: argparse.Namespace) -> int:
    repository = AvatarOutboxRepository(Path.cwd())
    action = str(args.action).casefold().strip()
    if action == "list":
        messages = [message.as_mapping() for message in repository.pending(args.limit)]
        payload = {"pending": messages, "count": len(messages)}
        print(json.dumps(payload, ensure_ascii=False) if args.json else _render(messages))
        return 0
    if action == "claim":
        claim_token, claimed = repository.claim(args.limit, args.lease_seconds)
        messages = [message.as_mapping() for message in claimed]
        payload = {"claimToken": claim_token, "claimed": messages, "count": len(messages)}
        print(json.dumps(payload, ensure_ascii=False) if args.json else _render(messages))
        return 0
    if action in {"ack", "release"}:
        message_id = str(args.message_id or "").strip()
        claim_token = str(args.claim_token or "").strip()
        if not message_id or not claim_token:
            print(f"Error: avatar-outbox {action} requires message_id and --claim-token.")
            return 2
        changed = (
            repository.acknowledge(message_id, claim_token)
            if action == "ack"
            else repository.release(message_id, claim_token)
        )
        payload = {"messageId": message_id, "action": action, "changed": changed}
        print(json.dumps(payload) if args.json else f"{action.title()}: {message_id}" if changed else "Lease mismatch.")
        return 0 if changed else 1
    print("Error: avatar-outbox action must be list, claim, ack, or release.")
    return 2


def _render(messages: list[dict[str, object]]) -> str:
    if not messages:
        return "No pending avatar references."
    return "\n".join(
        f"{message['message_id']} -> {message['thread_id']}@{message['host_id']}"
        for message in messages
    )
