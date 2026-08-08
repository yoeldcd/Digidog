# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""HTTP request adaptation for the local voice daemon."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import TypeAlias
from urllib.parse import unquote

from brain.infrastructure.voice.messaging.message_queue import bounded_prelude_seconds


HttpPayload: TypeAlias = dict[str, object]
"""Mutable JSON-compatible payload exchanged with local daemon clients."""


class VoiceHttpHandler(BaseHTTPRequestHandler):
    """Adapt local HTTP requests to the composed voice-runtime boundary."""

    memory_provider = staticmethod(lambda: None)
    replay_callback = staticmethod(lambda name=None, speak_id=None: False)
    core_runtime_id = ""
    idle_ttl_seconds = 0

    @property
    def memory(self) -> object:
        """Return the composition-root supplied runtime.

        Returns:
            Runtime object configured by the daemon composition root.
        """
        return self.memory_provider()

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default HTTP request logging from the local daemon.

        Args:
            format: Base HTTP server format string.
            *args: Format values supplied by the HTTP server.
        """
        return

    def do_GET(self) -> None:
        """Serve daemon health, status, message metadata, or audio resources."""
        if self.path == "/health":
            self._send_json({"ok": True, "coreId": self.core_runtime_id, "ttlSeconds": self.idle_ttl_seconds})
            return
        if self.path == "/status":
            self._send_json(self.memory.status())
            return
        if self.path == "/messages":
            self._send_json({"ok": True, **self.memory.snapshot()})
            return
        if self.path == "/audio/latest":
            self._send_audio(self.memory.find_audio())
            return
        if self.path.startswith("/audio/name/"):
            self._send_audio(self.memory.find_audio(unquote(self.path.removeprefix("/audio/name/"))))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        """Handle local daemon lifecycle, queue, and presentation commands."""
        self.memory.touch()
        if self.path == "/stop":
            self.memory.stop_playback()
            self.memory.request_daemon_stop()
            self._send_json({"ok": True, "stopping": True}, status=HTTPStatus.ACCEPTED)
            return
        if self.path == "/window-ready":
            length = min(int(self.headers.get("Content-Length", "0")), 1_000)
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            try:
                pid = int(payload.get("pid"))
            except (TypeError, ValueError):
                pid = None
            accepted = self.memory.mark_window_ready(pid)
            self._send_json(
                {"ok": accepted, "windowReady": accepted, "pid": pid},
                status=HTTPStatus.OK if accepted else HTTPStatus.CONFLICT,
            )
            return
        if self.path in {"/playback-started", "/playback-preparing", "/playback-duration"}:
            length = min(int(self.headers.get("Content-Length", "0")), 1_000)
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            speak_id = str(payload.get("speakId", ""))
            try:
                generation = int(payload.get("generation", -1))
            except (TypeError, ValueError):
                generation = -1
            if self.path == "/playback-started":
                accepted = self.memory.mark_playback_started_for(speak_id, generation)
            elif self.path == "/playback-preparing":
                accepted = self.memory.begin_playback_prelude_for(speak_id, generation)
            else:
                try:
                    milliseconds = int(payload.get("milliseconds", 0))
                except (TypeError, ValueError):
                    milliseconds = 0
                accepted = self.memory.set_playback_duration_for(speak_id, generation, milliseconds)
            self._send_json(
                {"ok": accepted, "state": self.memory.status()["state"]},
                status=HTTPStatus.OK if accepted else HTTPStatus.CONFLICT,
            )
            return
        if self.path == "/stop-current-message":
            speak_id = self.memory.stop_active_speak()
            self._send_json(
                {"ok": speak_id is not None, "stopped": speak_id is not None, "speakId": speak_id},
                status=HTTPStatus.ACCEPTED if speak_id else HTTPStatus.NOT_FOUND,
            )
            return
        if self.path == "/dismiss":
            self.memory.stop_playback()
            self._send_json({"ok": True, "dismissed": True})
            return
        # Compatibility only: the former route is intentionally terminal STOP.
        # No paused state, retained position, or resume operation exists.
        if self.path == "/pause":
            speak_id = self.memory.stop_active_speak()
            self._send_json(
                {"ok": speak_id is not None, "stopped": speak_id is not None, "speakId": speak_id},
                status=HTTPStatus.ACCEPTED if speak_id else HTTPStatus.NOT_FOUND,
            )
            return
        if self.path == "/mute":
            mute_mode = self.memory.toggle_muted()
            self._send_json({"ok": True, "muted": mute_mode != "off", "muteMode": mute_mode})
            return
        if self.path == "/replay":
            length = min(int(self.headers.get("Content-Length", "0")), 4_000)
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            message_name = str(payload.get("name", "")).strip() or None
            speak_id = str(payload.get("speakId", "")).strip() or None
            replayable = self.replay_callback(name=message_name, speak_id=speak_id)
            self._send_json(
                {"ok": replayable, "replaying": replayable, "queued": replayable},
                status=HTTPStatus.ACCEPTED if replayable else HTTPStatus.NOT_FOUND,
            )
            return
        if self.path == "/ambient-state":
            length = min(int(self.headers.get("Content-Length", "0")), 4_000)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            try:
                state = self.memory.set_ambient_state(str(payload.get("state", "")))
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "state": state, "ambientState": self.memory.ambient_state})
            return
        if self.path == "/theme":
            length = min(int(self.headers.get("Content-Length", "0")), 1_000)
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            try:
                mode = self.memory.set_theme_mode(str(payload.get("mode", "")))
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "themeMode": mode})
            return
        if self.path == "/narrate-active-file":
            speak_id = self.memory.enqueue_active_file_narration()
            self._send_json(
                {"ok": speak_id is not None, "queued": speak_id is not None, "speakId": speak_id},
                status=HTTPStatus.ACCEPTED if speak_id else HTTPStatus.NOT_FOUND,
            )
            return
        if self.path == "/cancel-processing":
            cancelled = self.memory.cancel_processing()
            self._send_json({"ok": True, "cancelled": cancelled})
            return
        if self.path != "/speak":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        speak_id = self.memory.enqueue(
            text=str(payload.get("text", "")),
            display_text=str(payload.get("displayText", "")),
            lang=str(payload.get("lang", "es")),
            emotion=str(payload.get("emotion", "")),
            signal_key=str(payload.get("signalKey", "")),
            prelude_seconds=bounded_prelude_seconds(payload.get("preludeSeconds", 0)),
            consumer_path=str(payload.get("consumerPath", "")),
            codex_thread_id=str(payload.get("codexThreadId", "")),
            source_command=str(payload.get("sourceCommand", "")),
            source_phase=str(payload.get("sourcePhase", "")),
            keep_speaks_only=bool(payload.get("keepSpeaksOnly", False)),
            clear_queue_before=bool(payload.get("clearQueueBefore", False)),
            has_embedded_file=bool(payload.get("hasEmbeddedFile", False)),
            manual_speech=bool(payload.get("manualSpeech", False)),
            show_message=bool(payload.get("showMessage", True)),
            speak_message=bool(payload.get("speakMessage", True)),
            hide_when_muted=bool(payload.get("hideWhenMuted", False)),
            message_level=str(payload.get("messageLevel", "informative")),
            pre_processor=str(payload.get("preProcessor", "<default>")),
        )
        self._send_json({"ok": True, "queued": speak_id is not None, "speakId": speak_id}, status=HTTPStatus.ACCEPTED)

    def _send_json(self, payload: HttpPayload, status: HTTPStatus = HTTPStatus.OK) -> None:
        """Serialize and send one JSON response with its exact byte length.

        Args:
            payload: JSON-compatible response body.
            status: HTTP status code sent with the response.
        """

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_audio(self, audio: bytes | None) -> None:
        """Send audio bytes or preserve the existing missing-resource response.

        Args:
            audio: Encoded audio payload, or ``None`` when no resource exists.
        """

        if audio is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)
