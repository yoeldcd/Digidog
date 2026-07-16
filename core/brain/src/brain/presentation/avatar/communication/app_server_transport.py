# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Stdio JSON-RPC transport for Codex App Server."""

from __future__ import annotations

# Standard Libraries Imports
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from typing import Any


class CodexAppServerError(RuntimeError):
    """Describe one rejected or unavailable App Server operation."""



def resolve_codex_executable(configured: str | None = None) -> str:
    """Resolve an executable Codex CLI outside protected Desktop package paths."""
    explicit = configured or os.environ.get("CODEX_EXECUTABLE", "")
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return str(candidate)
        raise CodexAppServerError(f"La ruta CODEX_EXECUTABLE no existe: {candidate}")

    home = Path.home()
    patterns = (
        ".antigravity-ide/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe",
        ".vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe",
        ".vscode-insiders/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe",
    )
    extension_candidates = sorted(
        (candidate for pattern in patterns for candidate in home.glob(pattern)),
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )
    if extension_candidates:
        return str(extension_candidates[0])
    discovered = shutil.which("codex")
    if discovered and "WindowsApps" not in discovered:
        return discovered
    raise CodexAppServerError(
        "No encontré un Codex CLI ejecutable. Configura CODEX_EXECUTABLE con una instalación de codex-cli; "
        "la copia interna de Codex Desktop está protegida por Windows y no puede iniciarse desde el avatar."
    )


class StdioCodexAppServerTransport:
    """Own one initialized `codex app-server` stdio process."""

    def __init__(self, executable: str | None = None) -> None:
        """Configure the executable without starting a process eagerly."""
        self._configured_executable = executable
        self._executable = ""
        self._process: subprocess.Popen[str] | None = None
        self._request_id = 0
        self._lock = threading.RLock()

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send one JSON-RPC request and wait for its matching response."""
        with self._lock:
            self._ensure_started()
            self._request_id += 1
            request_id = self._request_id
            self._write({"method": method, "id": request_id, "params": params})
            while True:
                response = self._read()
                if response.get("id") != request_id:
                    continue
                error = response.get("error")
                if error:
                    raise CodexAppServerError(str(error.get("message") or error))
                result = response.get("result", {})
                return result if isinstance(result, dict) else {"value": result}

    def notify(self, method: str, params: dict[str, Any]) -> None:
        """Send one JSON-RPC notification."""
        with self._lock:
            self._ensure_started()
            self._write({"method": method, "params": params})

    def close(self) -> None:
        """Terminate the owned process without affecting the Codex desktop host."""
        with self._lock:
            if self._process is None:
                return
            self._process.terminate()
            self._process = None

    def _ensure_started(self) -> None:
        """Start and initialize App Server exactly once."""
        if self._process is not None and self._process.poll() is None:
            return
        if not self._executable:
            self._executable = resolve_codex_executable(self._configured_executable)
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self._process = subprocess.Popen(
                [self._executable, "app-server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                creationflags=creation_flags,
            )
        except OSError as exc:
            raise CodexAppServerError(f"Codex App Server could not start: {exc}") from exc
        self._request_id += 1
        request_id = self._request_id
        client_info = {
            "name": "angi_avatar",
            "title": "Angi Avatar",
            "version": "0.1.0",
        }
        self._write({"method": "initialize", "id": request_id, "params": {"clientInfo": client_info}})
        response = self._read()
        if response.get("id") != request_id or response.get("error"):
            raise CodexAppServerError(f"Codex App Server initialization failed: {response}")
        self._write({"method": "initialized", "params": {}})

    def _write(self, payload: dict[str, Any]) -> None:
        """Write one compact JSONL frame to the child process."""
        if self._process is None or self._process.stdin is None:
            raise CodexAppServerError("Codex App Server stdin is unavailable.")
        self._process.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._process.stdin.flush()

    def _read(self) -> dict[str, Any]:
        """Read one JSONL frame or raise when the process exits."""
        if self._process is None or self._process.stdout is None:
            raise CodexAppServerError("Codex App Server stdout is unavailable.")
        line = self._process.stdout.readline()
        if not line:
            stderr = self._process.stderr.read().strip() if self._process.stderr else ""
            raise CodexAppServerError(stderr or "Codex App Server closed the transport.")
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise CodexAppServerError("Codex App Server returned a non-object frame.")
        return payload
