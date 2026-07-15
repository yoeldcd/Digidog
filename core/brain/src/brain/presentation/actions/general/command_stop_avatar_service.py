"""Action for gracefully stopping the avatar service."""

from __future__ import annotations

import argparse

from brain.infrastructure.voice.daemon_client import VoiceDaemonClient


def handle(args: argparse.Namespace) -> int:
    """Request daemon shutdown and report whether it was running."""
    stopped = VoiceDaemonClient().stop()
    print("Avatar service stopping." if stopped else "Avatar service is not running.")
    args.json_payload = {"ok": True, "command": "stop-avatar-service", "stopped": stopped}
    return 0
