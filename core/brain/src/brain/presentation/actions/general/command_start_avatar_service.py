"""Action for explicitly starting the avatar service."""

from __future__ import annotations

import argparse

from brain.infrastructure.voice.daemon_client import VoiceDaemonClient


def handle(args: argparse.Namespace) -> int:
    """Start or reuse the daemon and report its live process identifiers."""
    snapshot = VoiceDaemonClient().start()
    window_pids = ", ".join(str(pid) for pid in snapshot.get("windowPids", [])) or "-"
    print(f"Avatar service ready. PID: {snapshot.get('daemonPid', '-')} | Window PIDs: {window_pids}")
    args.json_payload = {"ok": True, "command": "start-avatar-service", "daemon": snapshot}
    return 0
