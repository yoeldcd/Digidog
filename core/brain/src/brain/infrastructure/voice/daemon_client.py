"""Client and lifecycle launcher for the local voice daemon."""

from __future__ import annotations

import json
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from brain.infrastructure.voice.config import resolve_voice_daemon_endpoint
from brain.infrastructure.voice.process_lease import core_runtime_id

VOICE_DAEMON_HOST, VOICE_DAEMON_PORT = resolve_voice_daemon_endpoint()
VOICE_DAEMON_URL = f"http://{VOICE_DAEMON_HOST}:{VOICE_DAEMON_PORT}"
VOICE_CORE_ID = core_runtime_id()
VOICE_DAEMON_STARTUP_TIMEOUT_SECONDS = 10.0


def consumer_repository_path(start: Path | None = None) -> str:
    """Return the nearest repository root for the process issuing a speak."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return str(candidate)
    return str(current)


class VoiceDaemonClient:
    """Dispatch voice work and read in-memory outputs from one warm daemon."""

    def start(self) -> dict[str, Any]:
        """Idempotently start the daemon and return its ready status snapshot."""
        self._ensure_daemon()
        return self._request_json(path="/status")

    def speak(
        self,
        text: str,
        lang: str = "es",
        emotion: str = "",
        signal_key: str = "",
        display_text: str = "",
        consumer_path: str = "",
        codex_thread_id: str = "",
    ) -> None:
        """Enqueue one message after lazily ensuring the daemon exists."""
        self._ensure_daemon()
        payload = {
            "text": text,
            "displayText": display_text or text,
            "lang": lang,
            "emotion": emotion,
            "signalKey": signal_key,
            "consumerPath": consumer_path or consumer_repository_path(),
            "codexThreadId": codex_thread_id or os.environ.get("CODEX_THREAD_ID", ""),
        }
        self._request_json(path="/speak", method="POST", payload=payload)

    def set_ambient_state(self, state: str) -> dict[str, Any]:
        """Persist the avatar state to restore after transient voice activity."""
        self._ensure_daemon()
        return self._request_json(path="/ambient-state", method="POST", payload={"state": state})

    def replay(self, name: str | None = None) -> dict[str, Any]:
        """Replay one retained message directly without synthesizing it again."""
        self._ensure_daemon()
        return self._request_json(path="/replay", method="POST", payload={"name": name or ""})

    def pause(self) -> dict[str, Any]:
        """Stop active daemon playback without changing retained audio."""
        self._ensure_daemon()
        return self._request_json(path="/pause", method="POST", payload={})

    def messages(self) -> list[dict[str, Any]]:
        """Return current in-memory message metadata without starting a daemon."""
        try:
            payload = self._request_json(path="/messages")
        except (OSError, URLError):
            return []
        return payload.get("messages", [])

    def snapshot(self) -> dict[str, Any]:
        """Return retained speak jobs and synthesized messages."""
        try:
            return self._request_json(path="/messages")
        except (OSError, URLError):
            return {"ok": True, "speaks": [], "messages": []}

    def status_snapshot(self) -> dict[str, Any]:
        """Return daemon lifecycle state plus retained queue data without starting it."""
        if not self._is_healthy():
            return {"ok": False, "state": "stopped", "speaks": [], "messages": []}
        status = self._request_json(path="/status")
        status.update(self._request_json(path="/messages"))
        return status

    def stop(self) -> bool:
        """Request graceful shutdown without starting a missing daemon."""
        if not self._is_healthy():
            return False
        return bool(self._request_json(path="/stop", method="POST", payload={}).get("stopping"))

    def audio(self, name: str | None = None) -> bytes | None:
        """Return the latest or one named in-memory audio payload."""
        path = "/audio/latest" if name is None else f"/audio/name/{quote(name, safe='')}"
        try:
            with urlopen(f"{VOICE_DAEMON_URL}{path}", timeout=1.0) as response:
                return response.read()
        except (OSError, URLError):
            return None

    def _ensure_daemon(self) -> None:
        """Start the daemon once and wait only until its local socket is ready."""
        if self._is_healthy():
            return
        daemon_path = Path(__file__).with_name("daemon.py")
        process: subprocess.Popen[Any] | None = None
        if sys.platform == "win32":
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.executable,
                subprocess.list2cmdline([str(daemon_path)]),
                str(daemon_path.parent),
                0,
            )
            if result <= 32:
                raise RuntimeError(f"Elevated voice daemon launch failed with ShellExecute code {result}.")
        else:
            process = subprocess.Popen(
                [sys.executable, str(daemon_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
        deadline = time.monotonic() + VOICE_DAEMON_STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self._is_healthy():
                return
            if process is not None and process.poll() is not None:
                raise RuntimeError(f"Voice daemon exited during startup with code {process.returncode}.")
            time.sleep(0.025)
        raise RuntimeError("Voice daemon did not become ready.")

    def _is_healthy(self) -> bool:
        try:
            payload = self._request_json(path="/health")
            remote_core_id = str(payload.get("coreId", ""))
            return bool(payload.get("ok")) and (not remote_core_id or remote_core_id == VOICE_CORE_ID)
        except (OSError, URLError):
            return False

    @staticmethod
    def _request_json(path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{VOICE_DAEMON_URL}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=1.0) as response:
            return json.loads(response.read().decode("utf-8"))
