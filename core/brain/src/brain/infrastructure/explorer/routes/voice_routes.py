# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Voice message routes for the Brain Explorer."""

from __future__ import annotations

import re
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from brain.infrastructure.explorer.contracts import ApiRouteError
from brain.infrastructure.runtime.paths import get_avatar_storage_dir
from brain.infrastructure.voice.daemon_client import VoiceDaemonClient
from brain.infrastructure.messages.repository import MessageRepository
from brain.infrastructure.runtime.paths import get_workspace_root


VOICE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._~-]+\.mp3$")


class VoiceRoutesMixin:
    """List and stream validated stored voice messages."""

    def _voice_messages(self, query: dict[str, str] | None = None) -> dict[str, Any]:
        """Return the message session tree and an optional selected session."""
        query = query or {}
        snapshot = VoiceDaemonClient().snapshot()
        messages = list(snapshot.get("messages", []))
        for audio_file in self._voice_directory().glob("*.mp3"):
            if not audio_file.is_file() or not VOICE_FILENAME_PATTERN.fullmatch(audio_file.name):
                continue
            stat = audio_file.stat()
            messages.append(
                {
                    "name": audio_file.name,
                    "sizeBytes": stat.st_size,
                    "createdAt": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                    "source": "legacy-disk",
                }
            )
        messages.sort(key=lambda item: item["createdAt"], reverse=True)
        repository = MessageRepository(
            consumer_path=get_workspace_root(),
            require_registered=False,
        )
        selected_date = str(query.get("date", "")).strip()
        selected_chat_id = str(query.get("chatId", "")).strip()
        history = [
            record.as_mapping()
            for record in repository.list_messages(
                limit=500,
                date=selected_date,
                chat_id_exact=selected_chat_id,
            )
        ] if selected_date else []
        sessions = repository.list_session_summaries()
        return {
            "ok": True,
            "data": {
                "speaks": snapshot.get("speaks", []),
                "messages": messages,
                "history": history,
                "historyTotal": repository.count(),
                "sessions": sessions,
                "selectedSession": {
                    "date": selected_date,
                    "chatId": selected_chat_id,
                } if selected_date else None,
                "database": repository.database_path.as_posix(),
            },
        }

    def _voice_status(self) -> dict[str, Any]:
        """Return the daemon-confirmed playback identity used by UI polling."""
        status = VoiceDaemonClient().status()
        return {
            "ok": bool(status.get("ok")),
            "data": {
                "state": str(status.get("state", "stopped")),
                "activeSpeakId": str(status.get("activeSpeakId", "")),
                "muted": bool(status.get("muted")),
            },
        }

    def _voice_replay(self) -> dict[str, Any]:
        """Replay one retained daemon message without requesting synthesis."""
        payload = self._read_json_body()
        name = str(payload.get("name", "")).strip()
        if not VOICE_FILENAME_PATTERN.fullmatch(name):
            return {"ok": False, "error": "A valid retained voice message name is required."}
        result = VoiceDaemonClient().replay(name=name)
        return {"ok": bool(result.get("replaying")), "data": result}

    def _voice_pause(self) -> dict[str, Any]:
        """Stop active daemon replay while retaining the message."""
        result = VoiceDaemonClient().pause()
        return {"ok": bool(result.get("paused")), "data": result}

    def _voice_synthesize(self) -> dict[str, Any]:
        """Generate and play audio for one persisted historical message."""
        payload = self._read_json_body()
        message_id = str(payload.get("messageId", "")).strip()
        repository = MessageRepository(
            consumer_path=get_workspace_root(),
            require_registered=False,
        )
        record = repository.get_message(message_id=message_id)
        if record is None:
            raise ApiRouteError(HTTPStatus.NOT_FOUND, "Persisted message not found.")
        queued = VoiceDaemonClient().speak(
            text=record.text,
            display_text=record.text,
            lang=record.language,
            emotion=record.emotion,
            consumer_path=str(get_workspace_root()),
            codex_thread_id=record.chat_id,
            source_command="historical-message-audio",
            source_phase="replay",
        )
        return {
            "ok": True,
            "data": {
                "messageId": record.id,
                "queued": bool(queued.get("queued")),
                "speakId": str(queued.get("speakId", "")),
            },
        }

    def _handle_voice_audio(self, method: str, path: str) -> None:
        """Stream the latest or one explicitly named stored MP3."""
        if method != "GET":
            self._send_json(status=HTTPStatus.METHOD_NOT_ALLOWED, payload={"ok": False, "error": "GET only."})
            return

        if path == "/api/voice/latest":
            memory_audio = VoiceDaemonClient().audio()
            if memory_audio is not None:
                self._send_audio_bytes(audio=memory_audio)
                return
            candidates = sorted(self._voice_directory().glob("*.mp3"), key=lambda item: item.stat().st_mtime, reverse=True)
            audio_file = next((item for item in candidates if item.is_file()), None)
        else:
            filename = unquote(path.removeprefix("/api/voice/messages/"))
            memory_audio = VoiceDaemonClient().audio(name=filename)
            if memory_audio is not None:
                self._send_audio_bytes(audio=memory_audio)
                return
            audio_file = self._resolve_voice_file(filename=filename)

        if audio_file is None or not audio_file.is_file():
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": "Voice message not found."})
            return
        self._send_audio_file(audio_file=audio_file)

    def _resolve_voice_file(self, filename: str) -> Path | None:
        """Resolve one safe MP3 filename within the voice directory."""
        if not VOICE_FILENAME_PATTERN.fullmatch(filename):
            return None
        voice_directory = self._voice_directory().resolve()
        candidate = (voice_directory / filename).resolve()
        return candidate if candidate.parent == voice_directory else None

    def _send_audio_file(self, audio_file: Path) -> None:
        """Send one validated MP3 response."""
        self._send_audio_bytes(audio=audio_file.read_bytes())

    def _send_audio_bytes(self, audio: bytes) -> None:
        """Send an MP3 already loaded from disk or daemon memory."""
        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)

    @staticmethod
    def _voice_directory() -> Path:
        """Return the persistent paid-voice message directory."""
        return get_avatar_storage_dir() / "dialogs"
