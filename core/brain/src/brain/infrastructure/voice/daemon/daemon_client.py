# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Client and lifecycle launcher for the local voice daemon."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from brain.infrastructure.avatar.configuration.avatar_config import resolve_voice_daemon_endpoint
from brain.infrastructure.voice.daemon.process_lease import core_runtime_id
from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest

VOICE_DAEMON_HOST, VOICE_DAEMON_PORT = resolve_voice_daemon_endpoint()
VOICE_DAEMON_URL = f"http://{VOICE_DAEMON_HOST}:{VOICE_DAEMON_PORT}"
VOICE_CORE_ID = core_runtime_id()
VOICE_DAEMON_STARTUP_TIMEOUT_SECONDS = 10.0


def consumer_repository_path(start: Path | None = None) -> str:
    """Find the nearest repository root for the process issuing speech.

    Args:
        start (Path | None): Search origin, or ``None`` for the working directory.

    Returns:
        str: Nearest ancestor containing ``.git``, or the resolved origin.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return str(candidate)
    return str(current)


def runs_inside_codex_sandbox() -> bool:
    """Detect whether Windows assigned the process to a Codex sandbox account.

    Returns:
        bool: ``True`` for a Windows Codex sandbox account.
    """
    username = os.environ.get("USERNAME", "")
    return sys.platform == "win32" and username.casefold().startswith("codexsandbox")


class VoiceDaemonClient:
    """Dispatch voice work and read in-memory outputs from one warm daemon."""

    def start(self, mode: str = "light") -> dict[str, Any]:
        """Idempotently start the daemon and apply an avatar theme.

        Args:
            mode (str): Initial ``light`` or ``dark`` theme.

        Returns:
            dict[str, Any]: Ready daemon status snapshot.

        Raises:
            ValueError: If ``mode`` is unsupported.
        """
        if mode not in {"dark", "light"}:
            raise ValueError(f"Unsupported avatar theme: {mode}")
        self._ensure_daemon()
        self._request_json(path="/theme", method="POST", payload={"mode": mode})
        return self._request_json(path="/status")

    def speak(self, request: AvatarSpeakRequest) -> dict[str, Any]:
        """Enqueue one message after lazily ensuring the daemon exists.

        Args:
            text (str): Narration text or refinement draft.
            lang (str): Narration language code.
            emotion (str): Avatar emotion for the message.
            signal_key (str): Optional refinement signal identity.
            display_text (str): Rich text rendered in the avatar window.
            consumer_path (str): Canonical message consumer path.
            codex_thread_id (str): Optional Codex reply target identifier.
            source_command (str): CLI command that created the message.
            source_phase (str): Command lifecycle phase that created it.
            has_embedded_file (bool): Whether the message contains an embedded file.
            manual_speech (bool): Whether narration requires an explicit user request.

        Returns:
            dict[str, Any]: Daemon enqueue acknowledgement and speak metadata.
        """
        self._ensure_daemon()
        payload = request.to_payload()
        payload["consumerPath"] = request.consumer_path or consumer_repository_path()
        payload["codexThreadId"] = request.codex_thread_id or os.environ.get("CODEX_THREAD_ID", "")
        return self._request_json(path="/speak", method="POST", payload=payload)

    def narrate_active_file(self) -> dict[str, Any]:
        """Request narration of the active embedded-file message."""
        self._ensure_daemon()
        return self._request_json(path="/narrate-active-file", method="POST", payload={})

    def set_ambient_state(self, state: str) -> dict[str, Any]:
        """Persist the avatar state restored after transient voice activity.

        Args:
            state (str): Canonical ambient state name.

        Returns:
            dict[str, Any]: Daemon acknowledgement and resulting state.
        """
        self._ensure_daemon()
        return self._request_json(path="/ambient-state", method="POST", payload={"state": state})

    def replay(self, name: str | None = None, speak_id: str | None = None) -> dict[str, Any]:
        """Replay projected or latest eligible speech without new logical history."""
        self._ensure_daemon()
        return self._request_json(
            path="/replay",
            method="POST",
            payload={"name": name or "", "speakId": speak_id or ""},
        )

    def stop_current_message(self) -> dict[str, Any]:
        """Terminally cancel audible or muted current speak and advance its FIFO."""
        self._ensure_daemon()
        return self._request_json(path="/stop-current-message", method="POST", payload={})

    def dismiss(self) -> dict[str, Any]:
        """Dismiss the active muted presentation and continue the queue."""
        self._ensure_daemon()
        return self._request_json(path="/dismiss", method="POST", payload={})

    def pause(self) -> dict[str, Any]:
        """Invoke the legacy pause route, which terminally cancels the current speak.

        The route name remains only for compatibility; paused state and resume do not exist.
        """
        self._ensure_daemon()
        return self._request_json(path="/pause", method="POST", payload={})

    def messages(self) -> list[dict[str, Any]]:
        """Read in-memory message metadata without starting a daemon.

        Returns:
            list[dict[str, Any]]: Retained message metadata, or an empty list
            when the daemon is unavailable.
        """
        try:
            payload = self._request_json(path="/messages")
        except (OSError, URLError):
            return []
        return payload.get("messages", [])

    def snapshot(self) -> dict[str, Any]:
        """Return retained speak jobs and synthesized messages.

        Returns:
            dict[str, Any]: Queue snapshot, or an empty successful snapshot when
            the daemon is unavailable.
        """
        try:
            return self._request_json(path="/messages")
        except (OSError, URLError):
            return {"ok": True, "speaks": [], "messages": []}

    def status_snapshot(self) -> dict[str, Any]:
        """Read daemon lifecycle state and queue data without starting it.

        Returns:
            dict[str, Any]: Combined status and queue snapshot.
        """
        if not self._is_healthy():
            return {"ok": False, "state": "stopped", "speaks": [], "messages": []}
        status = self._request_json(path="/status")
        status.update(self._request_json(path="/messages"))
        return status

    def status(self) -> dict[str, Any]:
        """Read the last daemon-owned playback state without starting it.

        Returns:
            dict[str, Any]: Playback status or a stopped-state fallback.
        """
        if not self._is_healthy():
            return {"ok": False, "state": "stopped", "activeSpeakId": ""}
        return self._request_json(path="/status")

    def stop(self) -> bool:
        """Request graceful shutdown without starting a missing daemon.

        Returns:
            bool: Whether a running daemon accepted the shutdown request.
        """
        if not self._is_healthy():
            return False
        return bool(self._request_json(path="/stop", method="POST", payload={}).get("stopping"))

    def audio(self, name: str | None = None) -> bytes | None:
        """Read the latest or a named in-memory audio payload.

        Args:
            name (str | None): Message identifier, or ``None`` for the latest.

        Returns:
            bytes | None: Audio bytes, or ``None`` when unavailable.
        """
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
        if runs_inside_codex_sandbox():
            raise RuntimeError(
                "The avatar service is not running. Start it once from the interactive user CLI with "
                "py '.\\$agent\\scripts\\brain.py' start-avatar-service --json. "
                "Brain will not create an invisible GUI inside the Codex sandbox desktop."
            )
        popen_kwargs: dict[str, Any] = {
            "cwd": str(daemon_path.parent),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NO_WINDOW
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
            )
        else:
            popen_kwargs["start_new_session"] = True
        process = subprocess.Popen([sys.executable, str(daemon_path)], **popen_kwargs)
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
