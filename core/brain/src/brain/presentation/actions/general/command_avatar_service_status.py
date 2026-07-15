"""Render avatar service diagnostics."""
from __future__ import annotations
import argparse
from brain.infrastructure.voice.daemon_client import VoiceDaemonClient

BLUE, RED, CYAN, GREEN, RESET = "\033[94m", "\033[91m", "\033[96m", "\033[92m", "\033[0m"


def handle(args: argparse.Namespace) -> int:
    snapshot = VoiceDaemonClient().status_snapshot()
    color = bool(getattr(args, "color", False))
    paint = lambda value, tone: f"{tone}{value}{RESET}" if color else str(value)
    print(f"Service: {paint(snapshot.get('state', 'stopped'), GREEN if snapshot.get('ok') else RED)}")
    print(f"Service PID: {paint(snapshot.get('daemonPid', '-'), CYAN)}")
    window_pids = snapshot.get("windowPids", [])
    print(f"Window PIDs: {paint(', '.join(str(pid) for pid in window_pids) or '-', CYAN)}")
    print(f"Queue: {paint(snapshot.get('queueDepth', 0), CYAN)} | TTL: {snapshot.get('ttlRemainingSeconds', 0)}s")
    print("Messages:")
    for item in snapshot.get("messages", []):
        print(f"- {item['name']} {paint(chr(34) + item.get('text', '') + chr(34), BLUE)}")
    print("Speaks:")
    for speak in snapshot.get("speaks", []):
        print(f"- {speak['id']} [{speak['status']}] {paint(chr(34) + speak.get('text', '') + chr(34), BLUE)}")
        if speak.get("error"):
            print(f"  error: {paint(speak['error'], RED)}")
    args.json_payload = {"ok": bool(snapshot.get("ok")), "command": "avatar-service-status", "daemon": snapshot}
    return 0
