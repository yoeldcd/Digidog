# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Lazy memory-only voice synthesis daemon with a one-hour idle TTL."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import queue
import re
import sys
import threading
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

SOURCE_ROOT = Path(__file__).resolve().parents[3]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.infrastructure.voice.config import load_voice_config  # noqa: E402
from brain.infrastructure.voice.avatar_process import AvatarProcessSupervisor  # noqa: E402
from brain.infrastructure.voice.daemon_client import VOICE_DAEMON_HOST, VOICE_DAEMON_PORT, VOICE_DAEMON_URL  # noqa: E402
from brain.infrastructure.voice.engines import LocalPlayback, get_engine, play_audio_url  # noqa: E402
from brain.infrastructure.voice.process_lease import (  # noqa: E402
    ProcessLease,
    core_process_lease_name,
    core_runtime_id,
)
from brain.infrastructure.messages.models import MessageWriteDTO  # noqa: E402
from brain.infrastructure.messages.repository import MessageRepository, should_persist_message  # noqa: E402


IDLE_TTL_SECONDS = 60 * 60
MAX_MEMORY_MESSAGES = 128
DAEMON_INSTANCE_ID = uuid.uuid4().hex
CORE_RUNTIME_ID = core_runtime_id()


def bounded_prelude_seconds(value: object) -> float:
    """Parse the local presentation lead-in without trusting HTTP input."""
    try:
        return max(0, min(3, float(value)))
    except (TypeError, ValueError):
        return 0


def estimated_speech_seconds(text: str) -> float:
    """Estimate visual lifetime only when muted playback has no audio metadata."""
    word_count = max(1, len(text.split()))
    return max(2.0, min(180.0, word_count / 2.5))


class VoiceMemory:
    """Own queued requests and synthesized audio for the daemon lifetime."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.speaks: list[dict[str, Any]] = []
        self.requests: queue.Queue[dict[str, str]] = queue.Queue()
        self.playback_requests: queue.Queue[dict[str, Any]] = queue.Queue()
        self.persistence_requests: queue.Queue[dict[str, str]] = queue.Queue()
        self.persistence_errors: list[dict[str, str]] = []
        self.lock = threading.RLock()
        self.last_activity = time.monotonic()
        self.last_request: dict[str, str] | None = None
        self.stop_requested = False
        self.ambient_state = "awaiting"
        self.theme_mode = "light"
        self.state = "awaiting"
        self.active_text = ""
        self.active_display_text = ""
        self.active_emotion = ""
        self.muted = False
        self.playback: subprocess.Popen[bytes] | None = None
        self.replay_active = False
        self.pending_playback: tuple[str, str, str, str] | None = None
        self.active_speak_id = ""
        self.audio_by_hash: dict[str, bytes] = {}
        self.playback_natural_end_at = 0.0
        self.muted_visual_deadline = 0.0
        self.window_pids: list[int] = []

    def touch(self) -> None:
        with self.lock:
            self.last_activity = time.monotonic()

    def enqueue(
        self,
        text: str,
        lang: str,
        emotion: str = "",
        signal_key: str = "",
        prelude_seconds: float = 0,
        display_text: str = "",
        consumer_path: str = "",
        codex_thread_id: str = "",
        source_command: str = "",
        source_phase: str = "",
    ) -> str | None:
        with self.lock:
            # A newly arriving live message owns the audible channel. Historical
            # replay must never continue underneath it.
            if source_command.casefold().strip() != "historical-message-audio" and self.replay_active:
                self._stop_playback_locked()
            request = {
                "text": text,
                "displayText": display_text or text,
                "lang": lang,
                "emotion": emotion,
                "signalKey": signal_key,
                "preludeSeconds": str(bounded_prelude_seconds(prelude_seconds)),
                "consumerPath": consumer_path,
                "codexThreadId": codex_thread_id,
                "sourceCommand": source_command,
                "sourcePhase": source_phase,
            }
            if text:
                self.last_request = request
            elif self.last_request:
                request = dict(self.last_request)
                if emotion:
                    request["emotion"] = emotion
            else:
                return None
            speak_id = f"speak-{uuid.uuid4().hex[:12]}"
            request.update({"id": speak_id, "status": "QUEUED", "createdAt": datetime.now().astimezone().isoformat()})
            self.speaks.insert(0, request)
            del self.speaks[MAX_MEMORY_MESSAGES:]
            self.last_activity = time.monotonic()
            self.requests.put(request)
            return speak_id

    def set_speak_status(self, speak_id: str, status: str, error: str = "") -> None:
        with self.lock:
            speak = next((item for item in self.speaks if item["id"] == speak_id), None)
            if speak:
                speak["status"] = status
                speak["error"] = error

    def update_speak_text(self, speak_id: str, text: str) -> None:
        with self.lock:
            speak = next((item for item in self.speaks if item["id"] == speak_id), None)
            if speak:
                speak["text"] = text

    def set_state(self, state: str, text: str = "", emotion: str = "", display_text: str = "") -> None:
        with self.lock:
            self.state = self.ambient_state if state == "awaiting" else state
            self.active_text = text
            self.active_display_text = display_text or text
            self.active_emotion = emotion
            if state == "awaiting":
                self.active_speak_id = ""
                self.playback_natural_end_at = 0.0
                self.muted_visual_deadline = 0.0

    def set_ambient_state(self, state: str) -> str:
        """Set the persistent idle state without interrupting transient playback."""
        normalized = state.strip().lower()
        if normalized not in {"awaiting", "working"}:
            raise ValueError(f"Unsupported ambient avatar state: {state}")
        with self.lock:
            previous_ambient = self.ambient_state
            self.ambient_state = normalized
            if self.state in {"awaiting", "working"} or self.state == previous_ambient:
                self.state = normalized
                self.active_text = ""
                self.active_display_text = ""
                self.active_emotion = ""
            return self.state

    def set_theme_mode(self, mode: str) -> str:
        """Persist one supported presentation theme for attached avatar windows."""
        normalized = mode.strip().lower()
        if normalized not in {"dark", "light"}:
            raise ValueError(f"Unsupported avatar theme: {mode}")
        with self.lock:
            self.theme_mode = normalized
            return self.theme_mode

    def status(self) -> dict[str, Any]:
        with self.lock:
            self._expire_muted_visual(time.monotonic())
            remaining = max(0, int(IDLE_TTL_SECONDS - (time.monotonic() - self.last_activity)))
            window_pids = list(self.window_pids)
            return {
                "ok": True,
                "coreId": CORE_RUNTIME_ID,
                "instanceId": DAEMON_INSTANCE_ID,
                "daemonPid": os.getpid(),
                "windowPids": window_pids,
                "processRegistry": {"daemonPid": os.getpid(), "avatarPids": window_pids},
                "service": {"host": VOICE_DAEMON_HOST, "port": VOICE_DAEMON_PORT},
                "state": self.state,
                "ambientState": self.ambient_state,
                "themeMode": self.theme_mode,
                "text": self.active_text,
                "displayText": self.active_display_text,
                "emotion": self.active_emotion,
                "activeSpeakId": self.active_speak_id,
                "activeConsumerPath": next(
                    (
                        item.get("consumerPath", "")
                        for item in self.speaks
                        if item.get("id") == self.active_speak_id
                    ),
                    "",
                ),
                "activeCodexThreadId": next(
                    (
                        item.get("codexThreadId", "")
                        for item in self.speaks
                        if item.get("id") == self.active_speak_id
                    ),
                    "",
                ),
                "muted": self.muted,
                "queueDepth": self.requests.qsize(),
                "historyCount": len(self.speaks),
                "synthesisCacheEntries": len(self.audio_by_hash),
                "persistenceQueueDepth": self.persistence_requests.qsize(),
                "persistenceErrors": list(self.persistence_errors[-10:]),
                "visualRemainingSeconds": max(0, round(self.muted_visual_deadline - time.monotonic(), 2)),
                "ttlRemainingSeconds": remaining,
            }

    def store(self, audio: bytes, speak_id: str, text: str) -> dict[str, Any]:
        with self.lock:
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
        """Return retained paid synthesis bytes for one stable request hash."""
        with self.lock:
            return self.audio_by_hash.get(cache_key)

    def retain_cached_audio(self, cache_key: str, audio: bytes) -> None:
        """Retain one paid synthesis result for this daemon lifetime."""
        if not cache_key or not audio:
            return
        with self.lock:
            self.audio_by_hash[cache_key] = audio
            while len(self.audio_by_hash) > MAX_MEMORY_MESSAGES:
                self.audio_by_hash.pop(next(iter(self.audio_by_hash)))

    def metadata(self) -> list[dict[str, Any]]:
        with self.lock:
            return [{key: value for key, value in item.items() if key != "audio"} for item in self.messages]

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {"speaks": [dict(item) for item in self.speaks], "messages": self.metadata()}

    def find_audio(self, name: str | None = None) -> bytes | None:
        with self.lock:
            self.touch()
            if name is None:
                return self.messages[0]["audio"] if self.messages else None
            return next((item["audio"] for item in self.messages if item["name"] == name), None)

    def latest_message(self) -> dict[str, Any] | None:
        with self.lock:
            return self.messages[0] if self.messages else None

    def find_message(self, name: str | None = None) -> dict[str, Any] | None:
        """Return the latest or one named RAM-backed message."""
        with self.lock:
            if name is None:
                return self.messages[0] if self.messages else None
            return next((item for item in self.messages if item["name"] == name), None)

    def has_replayable_content(self) -> bool:
        """Return whether replay can expose text or audible RAM content."""
        with self.lock:
            return self.last_request is not None or bool(self.messages)

    def reveal_latest_request(self) -> bool:
        """Restore the latest request as a visual-only muted dialogue."""
        with self.lock:
            if self.last_request is None:
                return False
            self.state = "muted_replay"
            self.active_text = self.last_request.get("text", "")
            self.active_display_text = self.last_request.get("displayText", self.active_text)
            self.active_emotion = self.last_request.get("emotion", "")
            self.active_speak_id = self.last_request.get("id", "")
            return bool(self.active_text)

    def stop_playback(self) -> None:
        with self.lock:
            self._stop_playback_locked()

    def _stop_playback_locked(self) -> None:
        """Stop current audio while the caller owns the re-entrant lock."""
        if self.playback and self.playback.poll() is None:
            self.playback.terminate()
        self.playback = None
        self.replay_active = False
        self.state = self.ambient_state
        self.active_text = ""
        self.active_display_text = ""
        self.pending_playback = None
        self.active_speak_id = ""
        self.playback_natural_end_at = 0.0
        self.muted_visual_deadline = 0.0

    def toggle_muted(self) -> bool:
        """Toggle audible output while preserving the active message for the bubble."""
        with self.lock:
            self.muted = not self.muted
            if self.muted:
                now = time.monotonic()
                self.muted_visual_deadline = self.playback_natural_end_at
                if self.muted_visual_deadline <= now and self.active_text:
                    self.muted_visual_deadline = now + estimated_speech_seconds(self.active_text)
                if self.playback and self.playback.poll() is None:
                    self.playback.terminate()
                self.playback = None
                self.pending_playback = None
                self.state = "muted" if self.active_text else self.ambient_state
            elif self.state in {"muted", "muted_replay"}:
                self.state = self.ambient_state
                self.active_text = ""
                self.active_display_text = ""
                self.active_emotion = ""
                self.active_speak_id = ""
                self.muted_visual_deadline = 0.0
            return self.muted

    def show_muted_message(self, text: str, emotion: str, display_text: str = "", speak_id: str = "") -> None:
        """Expose a completed message visually without synthesizing audio."""
        with self.lock:
            self.state = "muted_replay"
            self.active_text = text
            self.active_display_text = display_text or text
            self.active_emotion = emotion
            self.active_speak_id = speak_id
            self.muted_visual_deadline = time.monotonic() + estimated_speech_seconds(text)

    def is_muted(self) -> bool:
        """Return the current in-memory audible-output preference."""
        with self.lock:
            return self.muted

    def prepare_playback(self, text: str, emotion: str, display_text: str = "", speak_id: str = "") -> None:
        with self.lock:
            self.pending_playback = (text, emotion, display_text or text, speak_id)
            self.last_activity = time.monotonic()
            self.playback_natural_end_at = 0.0
            self.muted_visual_deadline = 0.0

    def set_playback_duration(self, milliseconds: int) -> None:
        """Set the natural visual end time reported by the active media player."""
        bounded_seconds = max(0.1, min(60 * 60, int(milliseconds) / 1000))
        with self.lock:
            self.playback_natural_end_at = time.monotonic() + bounded_seconds

    def _expire_muted_visual(self, now: float) -> None:
        """Clear muted presentation after its natural or estimated deadline."""
        if not self.muted or not self.muted_visual_deadline or now < self.muted_visual_deadline:
            return
        self.state = self.ambient_state
        self.active_text = ""
        self.active_display_text = ""
        self.active_emotion = ""
        self.active_speak_id = ""
        self.muted_visual_deadline = 0.0

    def begin_playback_prelude(self) -> bool:
        """Expose the prepared emotion before audio without claiming playback."""
        with self.lock:
            if not self.pending_playback or self.muted:
                return False
            self.state = "preparing"
            (
                self.active_text,
                self.active_emotion,
                self.active_display_text,
                self.active_speak_id,
            ) = self.pending_playback
            return True

    def has_pending_playback(self) -> bool:
        """Return whether a prepared playback has not been cancelled."""
        with self.lock:
            return self.pending_playback is not None and not self.muted

    def mark_playback_started(self) -> None:
        with self.lock:
            if self.pending_playback and not self.muted:
                self.state = "speaking"
                (
                    self.active_text,
                    self.active_emotion,
                    self.active_display_text,
                    self.active_speak_id,
                ) = self.pending_playback
                self.pending_playback = None
                self.last_activity = time.monotonic()

    def begin_thinking(self, speak_id: str = "") -> None:
        with self.lock:
            if not self.playback or self.playback.poll() is not None:
                self.state = "thinking"
                self.active_text = "Pensando…"
                self.active_emotion = "thinking"
                self.active_display_text = self.active_text
                self.active_speak_id = speak_id
                self.last_activity = time.monotonic()

    def finish_thinking(self) -> None:
        with self.lock:
            if self.state == "thinking":
                self.state = self.ambient_state
                self.active_text = ""
                self.active_emotion = ""
                self.active_display_text = ""
                self.active_speak_id = ""

    def has_active_work(self) -> bool:
        """Return whether TTL shutdown would interrupt synthesis or playback."""
        with self.lock:
            playback_active = self.playback is not None and self.playback.poll() is None
            return bool(
                self.requests.unfinished_tasks
                or self.playback_requests.unfinished_tasks
                or self.pending_playback
                or playback_active
                or self.state in {"thinking", "preparing", "speaking"}
            )

    def idle_expired(self, now: float | None = None) -> bool:
        """Expire only after the idle TTL and after all active work has drained."""
        current = time.monotonic() if now is None else now
        return current - self.last_activity >= IDLE_TTL_SECONDS and not self.has_active_work()


MEMORY = VoiceMemory()


def paid_synthesis_cache_key(request: dict[str, str]) -> str:
    """Return a stable key for paid synthesis inputs, or empty for local engines."""
    config = load_voice_config()
    engine_name = str(config.get("active_voice_engine", "edge"))
    if engine_name not in {"openai", "elevenlabs"}:
        return ""
    engine_config = dict(config.get("voice_engines", {}).get(engine_name, {}))
    engine_config.pop("api_key", None)
    identity = {
        "engine": engine_name,
        "engineConfig": engine_config,
        "lang": request.get("lang", "es"),
        "text": request.get("text", ""),
    }
    serialized = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def synthesize(request: dict[str, str]) -> bytes | LocalPlayback:
    """Prepare one paid audio payload or deferred local playback request."""
    import requests

    config = load_voice_config()
    engine_name = config.get("active_voice_engine", "edge")
    engine_config = config.get("voice_engines", {}).get(engine_name, {})
    text = sanitize_engine_text(request["text"], engine_config)
    lang = request.get("lang", "es")
    if engine_name == "edge":
        configured_voice = str(engine_config.get("voices", {}).get(lang, "")).strip()
        if configured_voice:
            voice = configured_voice if configured_voice.endswith("Neural") else f"{configured_voice}Neural"
            try:
                return asyncio.run(
                    _synthesize_edge_audio(
                        text=text,
                        voice=voice,
                        rate=str(engine_config.get("rate", "+0%")),
                        volume=str(engine_config.get("volume", "+0%")),
                        pitch=str(engine_config.get("pitch", "+0Hz")),
                    )
                )
            except Exception:
                return get_engine(engine_name, engine_config).prepare(text=text, lang=lang)
    if engine_name == "elevenlabs":
        voice = engine_config.get("voices", {}).get(lang, engine_config.get("voice_id"))
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            headers={"xi-api-key": engine_config.get("api_key", ""), "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": engine_config.get("model_id", "eleven_multilingual_v2"),
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.content
    if engine_name == "openai":
        voice = engine_config.get("voices", {}).get(lang, engine_config.get("voice", "shimmer"))
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {engine_config.get('api_key', '')}", "Content-Type": "application/json"},
            json={"model": engine_config.get("model", "tts-1"), "input": text, "voice": voice},
            timeout=60,
        )
        response.raise_for_status()
        return response.content
    return get_engine(engine_name, engine_config).prepare(text=text, lang=lang)


def sanitize_engine_text(text: str, engine_config: dict[str, object]) -> str:
    """Apply an engine-owned Python regex only to its spoken projection."""
    pattern = str(engine_config.get("sanitization_regex", "")).strip()
    if not pattern:
        return text
    try:
        sanitized = re.sub(pattern, " ", text)
    except re.error:
        return text
    return re.sub(r"\s+", " ", sanitized).strip()


async def _synthesize_edge_audio(
    text: str,
    voice: str,
    rate: str = "+0%",
    volume: str = "+0%",
    pitch: str = "+0Hz",
) -> bytes:
    """Collect one Microsoft Edge Neural stream entirely in memory."""
    import edge_tts

    chunks: list[bytes] = []
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
    )
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            chunks.append(chunk["data"])
    audio = b"".join(chunks)
    if not audio:
        raise RuntimeError(f"Edge returned no audio for voice `{voice}`.")
    return audio


def synthesize_or_reuse(request: dict[str, str]) -> bytes | LocalPlayback:
    """Reuse paid audio by hash before issuing a provider synthesis request."""
    cache_key = paid_synthesis_cache_key(request)
    cached = MEMORY.cached_audio(cache_key) if cache_key else None
    if cached is not None:
        return cached
    result = synthesize(request)
    if isinstance(result, bytes) and cache_key:
        MEMORY.retain_cached_audio(cache_key, result)
    return result


def cohere_signal_text(request: dict[str, str]) -> str:
    """Use the configured text LLM to turn one CLI signal into natural Spanish."""
    original = request["text"].strip()
    if not request.get("signalKey") or not original:
        return original
    fallback = safe_signal_fallback(original=original, signal_key=request.get("signalKey", ""))
    try:
        from brain.application.querying.llm import request_query_json
        from brain.infrastructure.voice.narration_prompts import SPANISH_NARRATION_SYSTEM_PROMPT

        payload = request_query_json(
            system_prompt=SPANISH_NARRATION_SYSTEM_PROMPT,
            user_prompt=f"Tipo de señal: {request.get('signalKey')}\nBorrador factual: {original}",
            max_tokens=1200,
        )
        rewritten = str(payload.get("text", "")).strip()
        return rewritten if is_safe_refined_narration(rewritten, fallback=fallback) else fallback
    except Exception:
        return fallback


def cohere_signal_presentation(request: dict[str, str]) -> None:
    """Resolve one private CLI draft into safe spoken and visible prose."""
    request["text"] = cohere_signal_text(request)
    if request.get("signalKey"):
        request["displayText"] = request["text"]


def safe_signal_fallback(*, original: str, signal_key: str) -> str:
    """Extract a pre-rendered sentence for reviewed signals only."""
    if not signal_key.startswith("reviewed-template:"):
        return original
    fallback_line = next((line for line in original.splitlines() if line.startswith("Fallback seguro: ")), "")
    fallback = fallback_line.removeprefix("Fallback seguro: ").strip()
    return fallback or spanish_signal_fallback(signal_key)


def is_safe_refined_narration(text: str, fallback: str = "") -> bool:
    """Reject empty, structured, genericized, or envelope-leaking responses."""
    if not text or text.lstrip().startswith(("{", "[", "```")):
        return False
    technical_markers = (
        "comando:",
        "fase:",
        "plantilla aprobada:",
        "fallback seguro:",
        "argumentos reales:",
        "salida real:",
    )
    normalized = text.casefold()
    if any(marker in normalized for marker in technical_markers):
        return False
    generic_actions = (
        "completar la tarea",
        "completar la operación",
        "completado la tarea",
        "completado la operación",
    )
    fallback_normalized = fallback.casefold()
    return not any(action in normalized and action not in fallback_normalized for action in generic_actions)


def spanish_signal_fallback(signal_key: str) -> str:
    """Return a guaranteed Spanish sentence without unverified metadata."""
    spanish_fallbacks = {
        "task-added": "He registrado una nueva tarea.",
        "work-completed": "He completado la tarea.",
        "query-started": "Voy a consultar el conocimiento disponible.",
        "query-completed": "He terminado la consulta.",
        "logs-started": "Voy a revisar los registros anteriores.",
        "logs-completed": "He terminado de revisar los registros.",
        "logs-empty": "No encontré coincidencias en los registros.",
        "dream-started": "Voy a consolidar el conocimiento.",
        "dream-completed": "He terminado de consolidar el conocimiento.",
        "dream-failed": "La consolidación encontró un problema.",
    }
    return spanish_fallbacks.get(signal_key, "He procesado la señal.")


def consume_requests() -> None:
    """Synthesize continuously without waiting for earlier audio playback."""
    while True:
        request = MEMORY.requests.get()
        try:
            MEMORY.set_speak_status(request["id"], "WORKING")
            if request.get("signalKey"):
                MEMORY.begin_thinking(request["id"])
            cohere_signal_presentation(request)
            MEMORY.update_speak_text(request["id"], request["text"])
            enqueue_message_persistence(request=request)
            if MEMORY.is_muted():
                MEMORY.show_muted_message(
                    request["text"],
                    request.get("emotion", ""),
                    request.get("displayText", ""),
                    request["id"],
                )
                MEMORY.set_speak_status(request["id"], "DONE")
                continue
            synthesis = synthesize_or_reuse(request)
            if isinstance(synthesis, bytes):
                message = MEMORY.store(synthesis, speak_id=request["id"], text=request["text"])
                MEMORY.playback_requests.put({"request": request, "message": message})
            else:
                MEMORY.finish_thinking()
                MEMORY.playback_requests.put({"request": request, "localPlayback": synthesis})
        except Exception as exc:
            MEMORY.finish_thinking()
            MEMORY.set_speak_status(request["id"], "ERROR", error=str(exc))
        finally:
            MEMORY.requests.task_done()


def enqueue_message_persistence(request: dict[str, str]) -> None:
    """Queue selected message history without delaying synthesis or playback."""
    source_command: str = request.get("sourceCommand", "").casefold().strip()
    consumer_path: str = request.get("consumerPath", "").strip()
    if not consumer_path or not should_persist_message(source_command=source_command):
        return
    persisted_text: str = (
        request.get("text", "")
        if source_command
        else request.get("displayText", "") or request.get("text", "")
    )
    MEMORY.persistence_requests.put(
        {
            "id": request["id"],
            "createdAt": request["createdAt"],
            "text": persisted_text,
            "emotion": request.get("emotion", ""),
            "chatId": request.get("codexThreadId", ""),
            "language": request.get("lang", "es"),
            "consumerPath": consumer_path,
            "sourceType": "operation" if source_command else "speak",
            "sourceCommand": source_command,
            "sourcePhase": request.get("sourcePhase", ""),
        },
    )


def consume_persistence_requests() -> None:
    """Persist message jobs independently with bounded SQLite retries."""
    while True:
        request: dict[str, str] = MEMORY.persistence_requests.get()
        try:
            message_dto = MessageWriteDTO(
                id=request["id"],
                created_at=request["createdAt"],
                text=request["text"],
                emotion=request["emotion"],
                chat_id=request["chatId"],
                language=request["language"],
                source_type=request["sourceType"],
                source_command=request["sourceCommand"],
                source_phase=request["sourcePhase"],
            )
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    MessageRepository(consumer_path=request["consumerPath"]).append(message=message_dto)
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    time.sleep(0.05 * (attempt + 1))
            if last_error is not None:
                raise last_error
        except Exception as exc:
            with MEMORY.lock:
                MEMORY.persistence_errors.append(
                    {
                        "speakId": request.get("id", ""),
                        "consumerPath": request.get("consumerPath", ""),
                        "error": str(exc),
                    },
                )
                del MEMORY.persistence_errors[:-10]
        finally:
            MEMORY.persistence_requests.task_done()


def consume_playback_requests() -> None:
    """Play prepared RAM audio sequentially while synthesis continues ahead."""
    while True:
        job = MEMORY.playback_requests.get()
        request = job["request"]
        message = job.get("message")
        try:
            if MEMORY.is_muted():
                MEMORY.show_muted_message(
                    request["text"],
                    request.get("emotion", ""),
                    request.get("displayText", ""),
                    request["id"],
                )
                MEMORY.set_speak_status(request["id"], "DONE")
                continue
            MEMORY.prepare_playback(
                request["text"],
                request.get("emotion", ""),
                request.get("displayText", ""),
                request["id"],
            )
            if "localPlayback" in job:
                MEMORY.mark_playback_started()
                playback = job["localPlayback"].start()
            else:
                prelude_seconds = max(0, min(3, float(request.get("preludeSeconds", "0"))))
                playback = play_audio_url(
                    f"{VOICE_DAEMON_URL}/audio/name/{message['name']}",
                    f"{VOICE_DAEMON_URL}/playback-started",
                    f"{VOICE_DAEMON_URL}/playback-preparing" if prelude_seconds else "",
                    prelude_seconds,
                    f"{VOICE_DAEMON_URL}/playback-duration",
                )
            MEMORY.playback = playback
            playback.wait()
            MEMORY.set_speak_status(request["id"], "DONE")
        except Exception as exc:
            MEMORY.set_speak_status(request["id"], "ERROR", error=str(exc))
        finally:
            if not MEMORY.is_muted():
                MEMORY.set_state("awaiting")
            MEMORY.playback = None
            MEMORY.pending_playback = None
            MEMORY.playback_requests.task_done()


def replay_message(name: str | None = None) -> None:
    """Replay the latest or one named RAM-backed message without synthesis."""
    message = MEMORY.find_message(name=name)
    if not message:
        return
    if MEMORY.is_muted():
        MEMORY.show_muted_message(
            message["text"],
            message.get("emotion", ""),
            message.get("displayText", ""),
            message.get("speakId", ""),
        )
        return
    MEMORY.stop_playback()
    MEMORY.prepare_playback(
        message["text"],
        message.get("emotion", ""),
        message.get("displayText", ""),
        message.get("speakId", ""),
    )
    try:
        MEMORY.replay_active = True
        playback = play_audio_url(
            f"{VOICE_DAEMON_URL}/audio/name/{message['name']}",
            f"{VOICE_DAEMON_URL}/playback-started",
            duration_callback_url=f"{VOICE_DAEMON_URL}/playback-duration",
        )
        MEMORY.playback = playback
        playback.wait()
    finally:
        MEMORY.playback = None
        MEMORY.replay_active = False
        MEMORY.set_state("awaiting")


class VoiceDaemonHandler(BaseHTTPRequestHandler):
    """Expose the local queue and in-memory audio store."""

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"ok": True, "coreId": CORE_RUNTIME_ID, "ttlSeconds": IDLE_TTL_SECONDS})
            return
        if self.path == "/status":
            self._send_json(MEMORY.status())
            return
        if self.path == "/messages":
            self._send_json({"ok": True, **MEMORY.snapshot()})
            return
        if self.path == "/audio/latest":
            self._send_audio(MEMORY.find_audio())
            return
        if self.path.startswith("/audio/name/"):
            self._send_audio(MEMORY.find_audio(unquote(self.path.removeprefix("/audio/name/"))))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        MEMORY.touch()
        if self.path == "/stop":
            MEMORY.stop_playback()
            MEMORY.stop_requested = True
            self._send_json({"ok": True, "stopping": True}, status=HTTPStatus.ACCEPTED)
            return
        if self.path == "/playback-started":
            MEMORY.mark_playback_started()
            self._send_json({"ok": True, "state": "speaking"})
            return
        if self.path == "/playback-preparing":
            self._send_json({"ok": MEMORY.begin_playback_prelude(), "state": "preparing"})
            return
        if self.path == "/playback-duration":
            length = min(int(self.headers.get("Content-Length", "0")), 1_000)
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            MEMORY.set_playback_duration(int(payload.get("milliseconds", 0)))
            self._send_json({"ok": True})
            return
        if self.path == "/pause":
            MEMORY.stop_playback()
            self._send_json({"ok": True, "paused": True})
            return
        if self.path == "/mute":
            self._send_json({"ok": True, "muted": MEMORY.toggle_muted()})
            return
        if self.path == "/replay":
            length = min(int(self.headers.get("Content-Length", "0")), 4_000)
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            message_name = str(payload.get("name", "")).strip() or None
            replayable = MEMORY.find_message(name=message_name) is not None
            if replayable:
                threading.Thread(target=replay_message, args=(message_name,), daemon=True, name="voice-replay").start()
            self._send_json({"ok": replayable, "replaying": replayable}, status=HTTPStatus.ACCEPTED if replayable else HTTPStatus.NOT_FOUND)
            return
        if self.path == "/ambient-state":
            length = min(int(self.headers.get("Content-Length", "0")), 4_000)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            try:
                state = MEMORY.set_ambient_state(str(payload.get("state", "")))
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "state": state, "ambientState": MEMORY.ambient_state})
            return
        if self.path == "/theme":
            length = min(int(self.headers.get("Content-Length", "0")), 1_000)
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            try:
                mode = MEMORY.set_theme_mode(str(payload.get("mode", "")))
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "themeMode": mode})
            return
        if self.path != "/speak":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = min(int(self.headers.get("Content-Length", "0")), 64_000)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        speak_id = MEMORY.enqueue(
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
        )
        self._send_json({"ok": True, "queued": speak_id is not None, "speakId": speak_id}, status=HTTPStatus.ACCEPTED)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_audio(self, audio: bytes | None) -> None:
        if audio is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)


def main() -> int:
    """Serve until no request has touched the daemon for one hour."""
    process_lease = ProcessLease(core_process_lease_name("voice-daemon"))
    if not process_lease.acquire():
        return 0
    threading.Thread(target=consume_requests, daemon=True, name="voice-synthesis").start()
    threading.Thread(target=consume_playback_requests, daemon=True, name="voice-playback").start()
    threading.Thread(target=consume_persistence_requests, daemon=True, name="message-persistence").start()
    server = ThreadingHTTPServer((VOICE_DAEMON_HOST, VOICE_DAEMON_PORT), VoiceDaemonHandler)
    avatar_entrypoint = SOURCE_ROOT / "brain" / "presentation" / "avatar" / "window" / "main.py"
    avatar_supervisor = AvatarProcessSupervisor(avatar_entrypoint, DAEMON_INSTANCE_ID)
    MEMORY.window_pids = [avatar_supervisor.ensure_running()]
    server.timeout = 1.0
    try:
        while not MEMORY.stop_requested and not MEMORY.idle_expired():
            server.handle_request()
            MEMORY.window_pids = [avatar_supervisor.ensure_running()]
    finally:
        persistence_deadline = time.monotonic() + 5.0
        while MEMORY.persistence_requests.unfinished_tasks and time.monotonic() < persistence_deadline:
            time.sleep(0.025)
        server.server_close()
        avatar_supervisor.close()
        MEMORY.window_pids = []
        process_lease.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
