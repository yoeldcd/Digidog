# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Synchronized active presentation state and public status projection."""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
import uuid
from typing import Final, Protocol, TypeAlias

from brain.infrastructure.avatar.process.avatar_process import AvatarProcessSupervisor
from brain.infrastructure.voice.daemon.daemon_client import VOICE_DAEMON_HOST, VOICE_DAEMON_PORT
from brain.infrastructure.voice.daemon.process_lease import core_runtime_id
from brain.infrastructure.voice.narration.markdown_narration import markdown_text_for_speech

IDLE_TTL_SECONDS: Final[int] = 60 * 60
MUTE_MODES: Final[tuple[str, str, str]] = ("off", "partial", "total")
PLAYBACK_STATES: Final[frozenset[str]] = frozenset({"preparing", "speaking"})
MUTED_PRESENTATION_STATES: Final[frozenset[str]] = frozenset({"muted", "muted_replay"})

DAEMON_INSTANCE_ID = uuid.uuid4().hex
CORE_RUNTIME_ID = core_runtime_id()


JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
VoiceRecord: TypeAlias = dict[str, JsonValue]


class _PlaybackProcess(Protocol):
    """Define terminal controls used by daemon playback state."""

    def poll(self) -> int | None:
        """Return the process state, or ``None`` while active."""

    def terminate(self) -> None:
        """Request terminal playback cancellation."""


class _ActiveSession(Protocol):
    """Define session identity used to reject stale playback callbacks."""

    speak_id: str
    generation: int
    cancelled: threading.Event

def estimated_speech_seconds(text: str) -> float:
    """Estimate a visual lifetime when muted playback lacks audio metadata.

    Args:
        text (str): Text displayed during muted playback.

    Returns:
        float: Bounded reading-time estimate in seconds.
    """
    word_count = max(1, len(markdown_text_for_speech(text).split()))
    return max(2.0, min(180.0, word_count / 2.5))


class RuntimeStateMixin:
    """Own synchronized voice presentation state for the daemon composition.

    Attributes:
        messages: Retained public message history.
        speaks: Retained logical speech-job history.
        lock: Re-entrant lock guarding the runtime state.
        mute_mode: Current audible output policy.
        active_speak_id: Identifier of the currently presented speech job.
    """

    def __init__(self) -> None:
        """Initialize synchronized queues, playback state, and window lifecycle data."""

        self.messages: list[VoiceRecord] = []
        self.speaks: list[VoiceRecord] = []
        self.requests: queue.Queue[VoiceRecord] = queue.Queue()
        self.persistence_requests: queue.Queue[dict[str, str]] = queue.Queue()
        self.persistence_errors: list[dict[str, str]] = []
        self.supervision_errors: list[str] = []
        self.processing_speak_ids: set[str] = set()
        self.processing_emotions: dict[str, str] = {}
        self.progressive_speak_ids: set[str] = set()
        self.lock = threading.RLock()
        self.last_activity = time.monotonic()
        self.last_request: VoiceRecord | None = None
        self.stop_requested = False
        self.ambient_state = "awaiting"
        self.theme_mode = "light"
        self.state = "awaiting"
        self.active_text = ""
        self.active_display_text = ""
        self.active_emotion = ""
        self.mute_mode = "off"
        self.muted = False
        self.playback: _PlaybackProcess | None = None
        self.replay_active = False
        self.pending_playback: tuple[str, str, str, str] | None = None
        self.active_speak_id = ""
        self.audio_by_hash: dict[str, bytes] = {}
        self.progressive_audio: dict[str, bytes] = {}
        self.playback_natural_end_at = 0.0
        self.muted_visual_deadline = 0.0
        self.presentation_cancel_event = threading.Event()
        self.window_pids: list[int] = []
        self.active_session: _ActiveSession | None = None
        self._session_generation = 0
        self._replay_pending = False
        # Unit-level memories are ready by default. ``main`` clears this before
        # spawning Qt, so the real FIFO cannot project or synthesize the first
        # message until the window explicitly acknowledges ``/window-ready``.
        self.window_ready = threading.Event()
        self.window_ready.set()
        self.window_wait_cancelled = threading.Event()
        self.awaiting_window_speak_id = ""
        self.window_supervisor: AvatarProcessSupervisor | None = None
        self.window_generation = 0
        self.current_window_pid: int | None = None
        self.ready_window_pid: int | None = None
    def touch(self) -> None:
        """Record interaction time for idle shutdown accounting."""
        with self.lock:
            self.last_activity = time.monotonic()
    def set_state(self, state: str, text: str = "", emotion: str = "", display_text: str = "") -> None:
        """Set transient presentation state and content.

        Args:
            state (str): New playback or ambient state.
            text (str): Narration text.
            emotion (str): Avatar emotion.
            display_text (str): Rich visible text.
        """
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
        """Set persistent idle state without interrupting transient playback.

        Args:
            state (str): ``awaiting`` or ``working``.

        Returns:
            str: Validated active state.

        Raises:
            ValueError: If the state is unsupported.
        """
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
        """Persist a supported theme for attached avatar windows.

        Args:
            mode (str): ``dark`` or ``light`` theme name.

        Returns:
            str: Validated theme mode.

        Raises:
            ValueError: If the theme is unsupported.
        """
        normalized = mode.strip().lower()
        if normalized not in {"dark", "light"}:
            raise ValueError(f"Unsupported avatar theme: {mode}")
        with self.lock:
            self.theme_mode = normalized
            return self.theme_mode
    def status(self) -> VoiceRecord:
        """Build the current daemon lifecycle and presentation snapshot.

        Returns:
            VoiceRecord: State, queue, timing, and connected-window metadata.
        """
        with self.lock:
            now = time.monotonic()
            self._expire_muted_visual(now)
            remaining = max(0, int(IDLE_TTL_SECONDS - (now - self.last_activity)))
            presentation_deadline = max(self.muted_visual_deadline, self.playback_natural_end_at)
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
                "readyWindowPid": self.ready_window_pid,
                "windowGeneration": self.window_generation,
                "text": self.active_text,
                "displayText": self.active_display_text,
                "emotion": self.active_emotion,
                "hasEmbeddedFile": next(
                    (
                        bool(item.get("hasEmbeddedFile", False))
                        for item in self.speaks
                        if item.get("id") == self.active_speak_id
                    ),
                    False,
                ),
                "manualSpeech": next(
                    (
                        bool(item.get("manualSpeech", False))
                        for item in self.speaks
                        if item.get("id") == self.active_speak_id
                    ),
                    False,
                ),
                "activeSpeakId": self.active_speak_id,
                "playbackActive": self.state in PLAYBACK_STATES,
                "progressivePlaybackActive": self.active_speak_id in self.progressive_speak_ids,
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
                "muteMode": self.mute_mode,
                # Only logical messages waiting behind the active session count.
                # Private TTS batches never appear in this public meter.
                "queueDepth": len(
                    {
                        str(item.get("id", ""))
                        for item in self.speaks
                        if item.get("status") == "QUEUED"
                        and item.get("id") != self.active_speak_id
                    }
                ),
                "historyCount": len(self.speaks),
                "synthesisCacheEntries": len(self.audio_by_hash),
                "persistenceQueueDepth": self.persistence_requests.qsize(),
                "persistenceErrors": list(self.persistence_errors[-10:]),
                "supervisionErrors": list(self.supervision_errors[-10:]),
                "processing": bool(self.processing_speak_ids),
                "processingEmotion": next(iter(self.processing_emotions.values()), ""),
                "visualRemainingSeconds": max(0, round(presentation_deadline - now, 2)),
                "ttlRemainingSeconds": remaining,
            }
    def has_replayable_content(self) -> bool:
        """Determine whether replay can expose text or RAM audio.

        Returns:
            bool: Whether a request or retained message can be replayed.
        """
        with self.lock:
            return self.last_request is not None or bool(self.messages)
    def reveal_latest_request(self) -> bool:
        """Restore the latest request as a visual-only muted dialogue.

        Returns:
            bool: Whether non-empty text was restored.
        """
        with self.lock:
            if self.last_request is None:
                return False
            self.state = "muted_replay"
            self.active_text = self.last_request.get("text", "")
            self.active_display_text = self.last_request.get("displayText", self.active_text)
            self.active_emotion = self.last_request.get("emotion", "")
            self.active_speak_id = self.last_request.get("id", "")
            return bool(self.active_text)
    def show_manual_file(self, request: VoiceRecord) -> None:
        """Expose a stable embedded-file message without entering playback state."""
        with self.lock:
            self.state = self.ambient_state
            self.active_text = str(request.get("text", ""))
            self.active_display_text = str(request.get("displayText", self.active_text))
            self.active_emotion = str(request.get("emotion", ""))
            self.active_speak_id = str(request.get("id", ""))
            self.pending_playback = None
            self.playback_natural_end_at = 0.0
            self.muted_visual_deadline = 0.0
    def stop_playback(self) -> None:
        """Stop active playback and clear its transient presentation state."""
        with self.lock:
            self._stop_playback_locked()
    def _stop_playback_locked(self) -> None:
        """Stop current audio while the caller owns the re-entrant lock."""
        self.presentation_cancel_event.set()
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
    def toggle_muted(self) -> str:
        """Cycle audible output through `off`, `partial`, and `total` modes.

        Returns:
            str: The newly active mute mode.
        """
        with self.lock:
            next_mode_index = (MUTE_MODES.index(self.mute_mode) + 1) % len(MUTE_MODES)
            self.mute_mode = MUTE_MODES[next_mode_index]
            self.muted = self.mute_mode != "off"

            active_speak = next(
                (item for item in self.speaks if item.get("id") == self.active_speak_id),
                {},
            )
            active_is_narrated = bool(active_speak.get("sourceCommand"))
            total_mute_selected = self.mute_mode == "total"
            narrated_partial_mute_selected = self.mute_mode == "partial" and active_is_narrated
            must_stop_active = total_mute_selected or narrated_partial_mute_selected
            if must_stop_active:
                now = time.monotonic()
                self.muted_visual_deadline = self.playback_natural_end_at
                if self.muted_visual_deadline <= now and self.active_text:
                    self.muted_visual_deadline = now + estimated_speech_seconds(self.active_text)
                if self.playback and self.playback.poll() is None:
                    self.playback.terminate()
                self.playback = None
                self.pending_playback = None
                self.state = "muted" if self.active_text else self.ambient_state
            elif self.mute_mode == "off" and self.state in MUTED_PRESENTATION_STATES:
                self.state = self.ambient_state
                self.active_text = ""
                self.active_display_text = ""
                self.active_emotion = ""
                self.active_speak_id = ""
                self.muted_visual_deadline = 0.0
            return self.mute_mode
    def show_muted_message(self, text: str, emotion: str, display_text: str = "", speak_id: str = "") -> None:
        """Expose a completed message visually without synthesizing audio.

        Args:
            text (str): Narration text.
            emotion (str): Avatar emotion.
            display_text (str): Rich visible text.
            speak_id (str): Source speak-job identifier.
        """
        with self.lock:
            self.presentation_cancel_event.clear()
            self.state = "muted_replay"
            self.active_text = text
            self.active_display_text = display_text or text
            self.active_emotion = emotion
            self.active_speak_id = speak_id
            self.muted_visual_deadline = time.monotonic() + estimated_speech_seconds(text)
    def wait_for_muted_presentation(self, duration_seconds: float) -> bool:
        """Wait for a muted visual turn, returning whether the user cancelled it.

        Args:
            duration_seconds (float): Natural bounded reading-time duration.

        Returns:
            bool: ``True`` when pause or dismissal cancelled the active turn.
        """
        bounded_duration = max(0.0, duration_seconds)
        return self.presentation_cancel_event.wait(timeout=bounded_duration)
    def is_muted(self, request: dict[str, str] | None = None) -> bool:
        """Return whether the active mute level suppresses one voice request.

        Args:
            request (dict[str, str] | None): Optional voice request carrying
                CLI narration provenance.

        Returns:
            bool: ``True`` for every request in total mode, or narrated CLI output
            in partial mode.
        """
        with self.lock:
            request_disables_speech = request is not None and not bool(request.get("speakMessage", True))
            if request_disables_speech:
                return True

            total_mute_selected = self.mute_mode == "total"
            if total_mute_selected:
                return True

            partial_mute_selected = self.mute_mode == "partial"
            if not partial_mute_selected or request is None:
                return False

            is_narrated_command = bool(request.get("sourceCommand"))
            is_informative = request.get("messageLevel", "informative") == "informative"
            return is_narrated_command and is_informative

    def prepare_playback(self, text: str, emotion: str, display_text: str = "", speak_id: str = "") -> None:
        """Stage a message for playback without marking it audible.

        Args:
            text (str): Narration text.
            emotion (str): Avatar emotion.
            display_text (str): Rich visible text.
            speak_id (str): Source speak-job identifier.
        """
        with self.lock:
            self.pending_playback = (text, emotion, display_text or text, speak_id)
            self.last_activity = time.monotonic()
            self.playback_natural_end_at = 0.0
            self.muted_visual_deadline = 0.0
    def set_playback_duration(self, milliseconds: int) -> None:
        """Set visual end time reported by the active media player.

        Args:
            milliseconds (int): Natural audio duration in milliseconds.
        """
        bounded_seconds = max(0.1, min(60 * 60, int(milliseconds) / 1000))
        with self.lock:
            self.playback_natural_end_at = time.monotonic() + bounded_seconds
    def _playback_callback_owns_active_session(self, speak_id: str, generation: int) -> bool:
        """Return whether a media callback still owns the current message session."""
        session = self.active_session
        return bool(
            session is not None
            and session.speak_id == speak_id
            and session.generation == generation
            and not session.cancelled.is_set()
        )
    def begin_playback_prelude_for(self, speak_id: str, generation: int) -> bool:
        """Accept a preparing callback only from the current player generation."""
        with self.lock:
            if not self._playback_callback_owns_active_session(speak_id, generation):
                return False
            return self.begin_playback_prelude()
    def mark_playback_started_for(self, speak_id: str, generation: int) -> bool:
        """Enter speaking only when the current media player reports audio start."""
        with self.lock:
            if not self._playback_callback_owns_active_session(speak_id, generation):
                return False
            self.mark_playback_started()
            return self.state == "speaking" and self.active_speak_id == speak_id
    def set_playback_duration_for(self, speak_id: str, generation: int, milliseconds: int) -> bool:
        """Accept natural media duration only from the current player generation."""
        with self.lock:
            if not self._playback_callback_owns_active_session(speak_id, generation):
                return False
            self.set_playback_duration(milliseconds)
            return True
    def _expire_muted_visual(self, now: float) -> None:
        """Clear muted presentation after its natural or estimated deadline."""

        mute_mode_is_off = self.mute_mode == "off"
        if mute_mode_is_off:
            return

        has_no_visual_deadline = not self.muted_visual_deadline
        if has_no_visual_deadline:
            return

        visual_deadline_has_not_elapsed = now < self.muted_visual_deadline
        if visual_deadline_has_not_elapsed:
            return
        self.state = self.ambient_state
        self.active_text = ""
        self.active_display_text = ""
        self.active_emotion = ""
        self.active_speak_id = ""
        self.muted_visual_deadline = 0.0

    def begin_playback_prelude(self) -> bool:
        """Expose prepared emotion before audio without claiming playback.

        Returns:
            bool: Whether a prelude was made active.
        """
        with self.lock:
            has_no_pending_playback = not self.pending_playback
            total_mute_selected = self.mute_mode == "total"
            if has_no_pending_playback or total_mute_selected:
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
        """Determine whether prepared playback has not been cancelled.

        Returns:
            bool: Whether an audible pending playback exists.
        """
        with self.lock:
            has_pending_playback = self.pending_playback is not None
            total_mute_selected = self.mute_mode == "total"
            return has_pending_playback and not total_mute_selected

    def mark_playback_started(self) -> None:
        """Transition a prepared playback into its audible state."""
        with self.lock:
            has_pending_playback = self.pending_playback is not None
            total_mute_selected = self.mute_mode == "total"
            if has_pending_playback and not total_mute_selected:
                self.state = "speaking"
                (
                    self.active_text,
                    self.active_emotion,
                    self.active_display_text,
                    self.active_speak_id,
                ) = self.pending_playback
                self.pending_playback = None
                self.last_activity = time.monotonic()
