# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Lifecycle supervision for the voice daemon avatar child process."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class AvatarProcessSupervisor:
    """Maintain exactly one live avatar child for a daemon instance."""

    def __init__(self, entrypoint: Path, instance_id: str) -> None:
        """Initialize an unstarted avatar process supervisor."""
        self._entrypoint = entrypoint
        self._instance_id = instance_id
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def pid(self) -> int | None:
        """Return the live child PID, excluding exited children."""
        if self._process is None or self._process.poll() is not None:
            return None
        return self._process.pid

    def ensure_running(self) -> int:
        """Return the existing live PID or start one replacement child."""
        live_pid = self.pid
        if live_pid is not None:
            return live_pid
        environment = os.environ.copy()
        environment["BRAIN_VOICE_DAEMON_INSTANCE_ID"] = self._instance_id
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self._process = subprocess.Popen(
            [sys.executable, str(self._entrypoint)],
            env=environment,
            creationflags=creation_flags,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=sys.platform != "win32",
        )
        return self._process.pid

    def close(self) -> None:
        """Terminate the owned child and wait briefly for process cleanup."""
        if self._process is None or self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=2)
