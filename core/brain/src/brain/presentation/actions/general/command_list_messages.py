# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action for listing temporary voice daemon state."""

from __future__ import annotations

import argparse
import json

from brain.infrastructure.voice.daemon_client import VoiceDaemonClient


def handle(args: argparse.Namespace) -> int:
    """Print retained speak jobs and synthesized voice messages."""
    snapshot = VoiceDaemonClient().snapshot()
    if getattr(args, "json", False):
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0
    print("# Voice Messages")
    print("\n## Speaks")
    for speak in snapshot.get("speaks", []):
        print(f"- {speak['id']} [{speak['status']}] {speak.get('text', '')}")
    print("\n## Retained Audio")
    for message in snapshot.get("messages", []):
        print(f"- {message['id']} <- {message['speakId']} | {message['name']} | {message['sizeBytes']} bytes")
    return 0
