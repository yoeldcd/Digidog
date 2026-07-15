"""Execute the core-owned Documentation Utils CLI through Brain."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from brain.infrastructure.runtime.paths import (
    get_documentation_utility_cli_path,
    get_workspace_root,
)
from brain.presentation.terminal import log_step


def handle(args: argparse.Namespace) -> int:
    """Run one checked Documentation Utils operation."""
    if args.mode not in {"check", "generate", "serve"}:
        error: str = f"Unsupported wiki mode `{args.mode}`. Use check, generate, or serve."
        args.json_payload = {"ok": False, "command": "wiki", "error": error}
        print(f"Error: {error}")
        return 1
    utility_path: Path = get_documentation_utility_cli_path()
    node_path: str | None = shutil.which("node")
    documentation_path: Path = _resolve_documentation_path(args.documentation_path)
    command: list[str] = _build_command(
        node_path=node_path,
        utility_path=utility_path,
        mode=args.mode,
        documentation_path=documentation_path,
        log_domain=args.log_domain,
        host=args.host,
        port=args.port,
    )
    error: str | None = _validate_runtime(node_path=node_path, utility_path=utility_path)
    if error is not None:
        args.json_payload = {"ok": False, "command": "wiki", "error": error}
        print(f"Error: {error}")
        return 1

    if args.mode == "serve" and getattr(args, "json", False):
        args.json_payload = {
            "ok": True,
            "command": "wiki",
            "mode": "serve",
            "documentationPath": documentation_path.as_posix(),
            "host": args.host,
            "port": args.port,
            "started": False,
        }
        return 0

    log_step(args, f"Running core wiki utility in {args.mode} mode...")
    if args.mode == "serve":
        return subprocess.call(command, cwd=get_workspace_root())

    result = subprocess.run(
        command,
        cwd=get_workspace_root(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stdout: str = result.stdout.strip()
    stderr: str = result.stderr.strip()
    if not getattr(args, "json", False):
        if stdout:
            print(stdout)
        if stderr:
            print(stderr)
    args.json_payload = {
        "ok": result.returncode == 0,
        "command": "wiki",
        "mode": args.mode,
        "documentationPath": documentation_path.as_posix(),
        "exitCode": result.returncode,
        "output": stdout,
        "error": stderr,
    }
    return result.returncode


def _resolve_documentation_path(raw_path: str) -> Path:
    """Resolve a documentation path relative to the current workspace."""
    candidate: Path = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = get_workspace_root() / candidate
    return candidate.resolve()


def _validate_runtime(node_path: str | None, utility_path: Path) -> str | None:
    """Return a diagnostic when the utility runtime is unavailable."""
    if node_path is None:
        return "Node.js is required to run Documentation Utils."
    if not utility_path.is_file():
        return f"Documentation Utils entrypoint does not exist: {utility_path}"
    return None


def _build_command(
    node_path: str | None,
    utility_path: Path,
    mode: str,
    documentation_path: Path,
    log_domain: str | None,
    host: str,
    port: int,
) -> list[str]:
    """Build the deterministic Documentation Utils subprocess command."""
    command: list[str] = [node_path or "node", str(utility_path), mode, str(documentation_path)]
    if log_domain and mode in {"check", "generate"}:
        command.extend(["--log-domain", log_domain])
    if mode == "serve":
        command.extend(["--host", host, "--port", str(port)])
    return command
