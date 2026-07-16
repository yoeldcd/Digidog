# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Persistent JSON-RPC client for Codex account rate limits."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from brain.infrastructure.runtime.paths import get_agent_home


@dataclass(frozen=True)
class CodexQuotaSnapshot:
    """Used percentages for Codex's five-hour and weekly windows."""

    five_hour_percent: int
    weekly_percent: int
    five_hour_resets_at: int
    weekly_resets_at: int


class CodexQuotaClient:
    """Keep one local Codex App Server process for lightweight quota reads."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._stdin: TextIO | None = None
        self._stdout: TextIO | None = None
        self._request_id = 0
        self._lock = threading.Lock()

    def read(self) -> CodexQuotaSnapshot | None:
        """Return the current quota snapshot, or `None` when unavailable."""
        with self._lock:
            try:
                self._ensure_started()
                payload = self._request("account/rateLimits/read", None)
                return self._parse_snapshot(payload)
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
                self.close()
                return None

    def close(self) -> None:
        """Terminate the owned App Server process without touching Codex Desktop."""
        process = self._process
        self._process = None
        self._stdin = None
        self._stdout = None
        if process is not None and process.poll() is None:
            process.terminate()

    def _ensure_started(self) -> None:
        """Start and initialize one authenticated stdio App Server."""
        if self._process is not None and self._process.poll() is None:
            return
        executable = self._find_executable()
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(self._codex_home())
        process_kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.DEVNULL,
            "text": True,
            "encoding": "utf-8",
            "bufsize": 1,
            "env": environment,
            "cwd": str(self._runtime_directory()),
        }
        if sys.platform == "win32":
            process_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        self._process = subprocess.Popen([str(executable), "app-server", "--stdio"], **process_kwargs)
        self._stdin = self._process.stdin
        self._stdout = self._process.stdout
        self._request(
            "initialize",
            {"clientInfo": {"name": "angi-avatar", "title": "Angi Avatar", "version": "1.0"}},
        )
        self._send({"method": "initialized"})

    def _request(self, method: str, params: Any) -> dict[str, Any]:
        """Send one request and ignore unrelated server notifications."""
        self._request_id += 1
        request_id = self._request_id
        self._send({"id": request_id, "method": method, "params": params})
        if self._stdout is None:
            raise RuntimeError("Codex App Server stdout is unavailable")
        while True:
            line = self._stdout.readline()
            if not line:
                raise RuntimeError("Codex App Server closed its output")
            message = json.loads(line)
            if message.get("id") != request_id:
                continue
            if message.get("error"):
                raise RuntimeError(str(message["error"].get("message", "Codex App Server error")))
            return dict(message.get("result") or {})

    def _send(self, message: dict[str, Any]) -> None:
        """Write one compact JSON-RPC message."""
        if self._stdin is None:
            raise RuntimeError("Codex App Server stdin is unavailable")
        self._stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self._stdin.flush()

    @staticmethod
    def _parse_snapshot(payload: dict[str, Any]) -> CodexQuotaSnapshot:
        """Classify rate-limit windows by duration and degrade missing five-hour data."""
        limits = dict(payload.get("rateLimits") or {})
        primary = dict(limits.get("primary") or {})
        secondary = dict(limits.get("secondary") or {})
        required_fields = {"usedPercent", "resetsAt"}
        complete_windows = [
            (position, window)
            for position, window in (("primary", primary), ("secondary", secondary))
            if required_fields.issubset(window)
        ]
        five_hour: dict[str, Any] | None = None
        weekly: dict[str, Any] | None = None
        if any("windowDurationMins" in window for _, window in complete_windows):
            for _, window in complete_windows:
                duration = int(window.get("windowDurationMins", 0))
                if duration >= 24 * 60:
                    weekly = window
                elif duration > 0:
                    five_hour = window
        else:
            five_hour = primary if required_fields.issubset(primary) else None
            weekly = secondary if required_fields.issubset(secondary) else None
        if weekly is None:
            raise ValueError("Codex weekly rate-limit payload is incomplete")
        return CodexQuotaSnapshot(
            five_hour_percent=max(0, min(100, int(five_hour["usedPercent"]))) if five_hour else 0,
            weekly_percent=max(0, min(100, int(weekly["usedPercent"]))),
            five_hour_resets_at=int(five_hour["resetsAt"]) if five_hour else 0,
            weekly_resets_at=int(weekly["resetsAt"]),
        )

    @staticmethod
    def _find_executable() -> Path:
        """Resolve the newest user-readable Codex executable."""
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = list((local_app_data / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
        if not candidates:
            raise RuntimeError("Codex executable was not found")
        return max(candidates, key=lambda path: path.stat().st_mtime_ns)

    @staticmethod
    def _codex_home() -> Path:
        """Resolve the signed-in user's Codex home without session-file reads."""
        configured = os.environ.get("CODEX_HOME")
        if configured:
            return Path(configured)
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        return local_app_data.parent.parent / ".codex"

    @staticmethod
    def _runtime_directory() -> Path:
        """Return a stable private cwd so App Server never inherits a consumer."""
        agent_home = get_agent_home()
        runtime_directory = agent_home / "$agent" / ".tmp" / "codex-app-server"
        runtime_directory.mkdir(parents=True, exist_ok=True)
        return runtime_directory
