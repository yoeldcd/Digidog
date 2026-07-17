# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action for listing persisted workspace avatar messages."""

from __future__ import annotations

import argparse
import json

from brain.infrastructure.messages.repository import MessageRepository
from brain.infrastructure.runtime.paths import get_workspace_root


def handle(args: argparse.Namespace) -> int:
    """Print persisted messages using bounded workspace-local filters."""
    repository = MessageRepository(consumer_path=get_workspace_root(), require_registered=False)
    messages = repository.list_messages(
        query=str(getattr(args, "query", "")),
        chat_id=str(getattr(args, "chat_id", "")),
        emotion=str(getattr(args, "emotion", "")),
        source_command=str(getattr(args, "source_command", "")),
        limit=int(getattr(args, "limit", 100)),
        offset=int(getattr(args, "offset", 0)),
    )
    payload = {
        "ok": True,
        "command": "list-messages",
        "database": repository.database_path.as_posix(),
        "count": len(messages),
        "total": repository.count(),
        "messages": [message.as_mapping() for message in messages],
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("# Avatar Message History")
    for message in messages:
        operation = f" {message.source_command}:{message.source_phase}" if message.source_command else ""
        print(f"- {message.created_at} [{message.emotion or 'neutral'}]{operation} {message.text}")
    return 0
