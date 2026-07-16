# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Execute the core-owned agent prompt propagator through Brain."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from brain.infrastructure.runtime.paths import (
    get_instruction_mirrors_registry_path,
    get_prompt_propagator_path,
    get_workspace_root,
)
from brain.presentation.terminal import log_step


def handle(args: argparse.Namespace) -> int:
    """Propagate or inspect canonical prompt mirrors through the core utility."""
    utility_path: Path = get_prompt_propagator_path()
    if not utility_path.is_file():
        error: str = f"Prompt propagator entrypoint does not exist: {utility_path}"
        args.json_payload = {"ok": False, "command": "propagate-agent-prompt", "error": error}
        print(f"Error: {error}")
        return 1

    command: list[str] = [sys.executable, str(utility_path), "--json"]
    if args.source:
        command.extend(["--source", args.source])
    mirrors_file: str = args.mirrors_file or str(get_instruction_mirrors_registry_path(create=False))
    command.extend(["--mirrors-file", mirrors_file])
    if args.dry_run:
        command.append("--dry-run")

    log_step(args, "Running core prompt propagator...")
    result = subprocess.run(
        command,
        cwd=get_workspace_root(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    payload: dict[str, Any] = _parse_payload(result.stdout, result.stderr)
    payload["command"] = "propagate-agent-prompt"
    payload["dryRun"] = bool(args.dry_run)
    args.json_payload = payload

    if not getattr(args, "json", False):
        for mirror in payload.get("mirrors", []):
            print(f"[{mirror.get('status', 'unknown')}] {mirror.get('destination', '')} - {mirror.get('message', '')}")
        if payload.get("error"):
            print(f"Error: {payload['error']}")
    return result.returncode


def _parse_payload(stdout: str, stderr: str) -> dict[str, Any]:
    """Parse the propagator JSON contract with a stable error fallback."""
    try:
        payload: object = json.loads(stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": stderr.strip() or stdout.strip() or "Prompt propagator returned no JSON."}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "Prompt propagator returned a non-object JSON payload."}
    return payload
