# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""RAM audio retention, synthesis cache, and progressive batch artifacts."""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

MAX_MEMORY_MESSAGES = 128


class AudioStoreMixin:
    """Behavioral identity extracted from the voice runtime composition."""

    def store(self, audio: bytes, speak_id: str, text: str) -> dict[str, Any]:
        """Retain generated audio and allocate a display-safe message name.

        Args:
            audio (bytes): In-memory MP3 bytes.
            speak_id (str): Source speak-job identifier.
            text (str): Synthesized narration text.

        Returns:
            dict[str, Any]: Retained message metadata including its unique name.
        """
        with self.lock:
            existing = next((item for item in self.messages if item.get("speakId") == speak_id), None)
            if existing is not None:
                existing["audio"] = audio
                existing["sizeBytes"] = len(audio)
                existing["text"] = text
                self.last_activity = time.monotonic()
                return existing
            timestamp = datetime.now().astimezone()
            base_name = timestamp.strftime("%d-%m-%y~%H-%M")
            existing_names = {item["name"] for item in self.messages}
            name = f"{base_name}.mp3"
            collision = 2
            while name in existing_names:
                name = f"{base_name}~{collision:02d}.mp3"
                collision += 1
            message = {
                "id": uuid.uuid4().hex,
                "name": name,
                "sizeBytes": len(audio),
                "createdAt": timestamp.isoformat(),
                "speakId": speak_id,
                "text": text,
                "displayText": next((item.get("displayText", text) for item in self.speaks if item["id"] == speak_id), text),
                "emotion": next((item.get("emotion", "") for item in self.speaks if item["id"] == speak_id), ""),
                "hasEmbeddedFile": next(
                    (bool(item.get("hasEmbeddedFile", False)) for item in self.speaks if item["id"] == speak_id),
                    False,
                ),
                "manualSpeech": next(
                    (bool(item.get("manualSpeech", False)) for item in self.speaks if item["id"] == speak_id),
                    False,
                ),
                "consumerPath": next(
                    (item.get("consumerPath", "") for item in self.speaks if item["id"] == speak_id),
                    "",
                ),
                "codexThreadId": next(
                    (item.get("codexThreadId", "") for item in self.speaks if item["id"] == speak_id),
                    "",
                ),
                "audio": audio,
            }
            self.messages.insert(0, message)
            del self.messages[MAX_MEMORY_MESSAGES:]
            self.last_activity = time.monotonic()
            return message
    def cached_audio(self, cache_key: str) -> bytes | None:
        """Read retained paid synthesis bytes for a stable request hash.

        Args:
            cache_key (str): Stable paid-synthesis request hash.

        Returns:
            bytes | None: Cached audio, or ``None`` on a cache miss.
        """
        with self.lock:
            return self.audio_by_hash.get(cache_key)
    def retain_cached_audio(self, cache_key: str, audio: bytes) -> None:
        """Retain a paid synthesis result for the daemon lifetime.

        Args:
            cache_key (str): Stable paid-synthesis request hash.
            audio (bytes): In-memory synthesized audio.
        """
        if not cache_key or not audio:
            return
        with self.lock:
            self.audio_by_hash[cache_key] = audio
            while len(self.audio_by_hash) > MAX_MEMORY_MESSAGES:
                self.audio_by_hash.pop(next(iter(self.audio_by_hash)))
    def metadata(self) -> list[dict[str, Any]]:
        """Return retained message metadata without embedded audio bytes.

        Returns:
            list[dict[str, Any]]: Safe metadata for retained messages.
        """
        with self.lock:
            return [{key: value for key, value in item.items() if key != "audio"} for item in self.messages]
    def snapshot(self) -> dict[str, Any]:
        """Return queued speak jobs and safe retained-message metadata.

        Returns:
            dict[str, Any]: Current speaks and messages.
        """
        with self.lock:
            return {"speaks": [dict(item) for item in self.speaks], "messages": self.metadata()}
    def find_audio(self, name: str | None = None) -> bytes | None:
        """Find latest or named retained audio.

        Args:
            name (str | None): Retained name, or ``None`` for the newest audio.

        Returns:
            bytes | None: Audio payload, or ``None`` when absent.
        """
        with self.lock:
            self.touch()
            if name is None:
                return self.messages[0]["audio"] if self.messages else None
            retained = next((item["audio"] for item in self.messages if item["name"] == name), None)
            return retained if retained is not None else self.progressive_audio.get(name)
    def latest_message(self) -> dict[str, Any] | None:
        """Return the most recently retained message.

        Returns:
            dict[str, Any] | None: Latest message or ``None`` if none exists.
        """
        with self.lock:
            return self.messages[0] if self.messages else None
    def find_message(self, name: str | None = None) -> dict[str, Any] | None:
        """Return the latest or one named RAM-backed message.

        Args:
            name (str | None): Retained message name, or ``None`` for latest.

        Returns:
            dict[str, Any] | None: Retained message or ``None`` when absent.
        """
        with self.lock:
            if name is None:
                return self.messages[0] if self.messages else None
            return next((item for item in self.messages if item["name"] == name), None)
    def retain_progressive_audio(self, speak_id: str, chunk_index: int, audio: bytes) -> dict[str, Any]:
        """Retain internal chunk audio without creating navigable message history."""
        with self.lock:
            name = f"{speak_id}~chunk-{chunk_index:04d}.mp3"
            self.progressive_audio[name] = audio
            return {"name": name, "speakId": speak_id, "sizeBytes": len(audio)}
    def mark_progressive_speak(self, speak_id: str, chunk_count: int) -> None:
        """Track progressive playback internally without exposing chunk jobs."""
        if chunk_count > 1:
            with self.lock:
                self.progressive_speak_ids.add(speak_id)
    def clear_progressive_audio(self, speak_id: str) -> None:
        """Discard every internal chunk buffer owned by one logical speak."""
        with self.lock:
            prefix = f"{speak_id}~chunk-"
            for name in [name for name in self.progressive_audio if name.startswith(prefix)]:
                self.progressive_audio.pop(name, None)
            self.progressive_speak_ids.discard(speak_id)
