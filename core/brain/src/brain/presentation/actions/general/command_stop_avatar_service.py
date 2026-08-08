# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action for gracefully stopping the avatar service."""

from __future__ import annotations

import argparse

from brain.infrastructure.voice.daemon.daemon_client import VoiceDaemonClient


def handle(args: argparse.Namespace) -> int:
    """Request daemon shutdown and report whether it was running.

    Args:
        args (argparse.Namespace): Parsed CLI namespace receiving JSON payload.

    Returns:
        int: Zero after issuing the non-starting stop request.
    """
    stopped = VoiceDaemonClient().stop()
    print("Avatar service stopping." if stopped else "Avatar service is not running.")
    args.json_payload = {"ok": True, "command": "stop-avatar-service", "stopped": stopped}
    return 0
