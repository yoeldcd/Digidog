"""Manage the in-memory message FIFO and speak request lifecycle.

This module owns request enqueueing, replay selection, pending-request cleanup,
and retained speak-record state transitions for the voice runtime.
"""

# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

from __future__ import annotations

import queue
import time
import uuid
from datetime import datetime
from typing import Final, TypeAlias

from brain.infrastructure.voice.narration.markdown_narration import normalize_avatar_message_text

SpeakRequest: TypeAlias = dict[str, object]
"""Mutable internal payload for one queued or retained speak request."""

MAX_MEMORY_MESSAGES: Final[int] = 128
"""Maximum number of retained speak records kept in memory."""


def bounded_prelude_seconds(value: object) -> float:
    """Parse a bounded presentation lead-in from untrusted input.

    Args:
        value (object): Candidate HTTP value.

    Returns:
        float: Prelude duration clamped to zero through three seconds.
    """
    try:
        return max(0, min(3, float(value)))
    except (TypeError, ValueError):
        return 0


class MessageQueueMixin:
    """Provide FIFO mutation and retained speak-record lifecycle operations.

    The host runtime supplies synchronization, queue, history, session, mute,
    and progressive-audio state used by these behavior-preserving methods.
    """

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
        keep_speaks_only: bool = False,
        clear_queue_before: bool = False,
        has_embedded_file: bool = False,
        manual_speech: bool = False,
        show_message: bool = True,
        speak_message: bool = True,
        hide_when_muted: bool = False,
        message_level: str = "informative",
        pre_processor: str = "<default>",
    ) -> str | None:
        """Queue a synthesis request and return its identifier.

        Args:
            text (str): Narration source text.
            lang (str): Narration language code.
            emotion (str): Avatar emotion for the request.
            signal_key (str): Optional refinement signal identity.
            prelude_seconds (float): Visual lead-in duration.
            display_text (str): Rich text shown by the avatar.
            consumer_path (str): Canonical message consumer path.
            codex_thread_id (str): Optional Codex reply target identifier.
            source_command (str): Command that produced the request.
            source_phase (str): Lifecycle phase that produced the request.
            has_embedded_file (bool): Whether the message contains an embedded file.
            manual_speech (bool): Whether narration requires an explicit user request.
            show_message (bool): Whether the avatar should display the message.
            speak_message (bool): Whether the voice service should synthesize speech.
            hide_when_muted (bool): Whether muted messages remain hidden.
            message_level (str): Avatar presentation severity or category.
            pre_processor (str): Preprocessing identity for the narration request.

        Returns:
            str | None: New speak-job identifier, or ``None`` without text to
            replay.
        """
        with self.lock:
            normalized_text = normalize_avatar_message_text(text)
            display_source_text = display_text or normalized_text
            normalized_display_text = normalize_avatar_message_text(display_source_text)
            request: SpeakRequest = {
                "text": normalized_text,
                "displayText": normalized_display_text,
                "lang": lang,
                "emotion": emotion,
                "signalKey": signal_key,
                "preludeSeconds": str(bounded_prelude_seconds(prelude_seconds)),
                "consumerPath": consumer_path,
                "codexThreadId": codex_thread_id,
                "sourceCommand": source_command,
                "sourcePhase": source_phase,
                "hasEmbeddedFile": has_embedded_file,
                "manualSpeech": manual_speech,
                "showMessage": show_message,
                "speakMessage": speak_message,
                "hideWhenMuted": hide_when_muted,
                "messageLevel": message_level,
                "preProcessor": pre_processor,
            }
            if clear_queue_before:
                self.clear_pending_for_reaction()
            if keep_speaks_only:
                for queued in self.speaks:
                    is_queued = queued.get("status") == "QUEUED"
                    has_source_command = bool(queued.get("sourceCommand"))

                    if is_queued and has_source_command:
                        queued["deprecated"] = "true"
                        queued["status"] = "DEPRECATED"

            should_deprecate_partial_mute_speaks = self.mute_mode == "partial" and not source_command

            if should_deprecate_partial_mute_speaks:
                for queued in self.speaks:
                    is_queued = queued.get("status") == "QUEUED"
                    has_source_command = bool(queued.get("sourceCommand"))
                    is_output_phase = queued.get("sourcePhase") == "output"

                    if is_queued and has_source_command and is_output_phase:
                        queued["deprecated"] = "true"
                        queued["status"] = "DEPRECATED"

            if normalized_text:
                self.last_request = request
            elif self.last_request:
                request = dict(self.last_request)
                if emotion:
                    request["emotion"] = emotion
            else:
                return None
            speak_id = f"speak-{uuid.uuid4().hex[:12]}"
            request.update(
                {
                    "id": speak_id,
                    "status": "QUEUED",
                    "createdAt": datetime.now().astimezone().isoformat(),
                }
            )
            self.speaks.insert(0, request)
            del self.speaks[MAX_MEMORY_MESSAGES:]
            self.last_activity = time.monotonic()
            self.requests.put(request)
            return speak_id


    def clear_pending_for_reaction(self) -> int:
        """Atomically leave no pending message ahead of an idle reaction.

        History records remain terminally marked for diagnostics, while the
        physical FIFO is drained so its next item is exactly the reaction that
        ``enqueue`` appends after this method returns.

        Returns:
            int: Number of queued or working speak records cancelled.
        """
        with self.lock:
            cleared_ids = {
                str(item.get("id", ""))
                for item in self.speaks
                if item.get("status") in {"QUEUED", "WORKING"}
                and item.get("id") != self.active_speak_id
            }
            for item in self.speaks:
                if item.get("id") in cleared_ids:
                    item["deprecated"] = "true"
                    item["status"] = "CANCELLED"
            retained_requests: list[SpeakRequest] = []
            while True:
                try:
                    queued = self.requests.get_nowait()
                except queue.Empty:
                    break
                else:
                    self.requests.task_done()
                    if str(queued.get("id", "")) not in cleared_ids:
                        retained_requests.append(queued)
            for queued in retained_requests:
                self.requests.put(queued)
            for speak_id in cleared_ids:
                self.processing_speak_ids.discard(speak_id)
                self.processing_emotions.pop(speak_id, None)
                self.clear_progressive_audio(speak_id)
            self._replay_pending = False
            return len(cleared_ids)


    def enqueue_active_file_narration(self) -> str | None:
        """Queue narration for the completed active embedded-file request.

        Returns:
            str | None: Requeued speak-job identifier, or ``None`` when no
                eligible active request exists.
        """
        with self.lock:
            active = next(
                (
                    item
                    for item in self.speaks
                    if item.get("id") == self.active_speak_id
                    and item.get("hasEmbeddedFile")
                    and item.get("manualSpeech")
                    and item.get("status") not in {"QUEUED", "WORKING"}
                ),
                None,
            )
            if active is None:
                return None
            active["status"] = "QUEUED"
            active["error"] = ""
            request = dict(active)
            request["manualSpeech"] = False
            request["createdAt"] = datetime.now().astimezone().isoformat()
            self.last_activity = time.monotonic()
            self.requests.put(request)
            return str(active["id"])


    def enqueue_replay(self, name: str | None = None, speak_id: str | None = None) -> bool:
        """Queue replay of an existing identity without duplicating history.

        Replay is a logical FIFO turn, never a playback batch. The original
        speakId is preserved and persistence is skipped by ``internalReplay``.

        Args:
            name: Optional retained-message name used for selection.
            speak_id: Optional retained speak-job identifier used for selection.

        Returns:
            bool: ``True`` when one eligible replay request is queued.
        """
        with self.lock:
            has_active_session = self.active_session is not None
            has_pending_replay = self._replay_pending
            has_unfinished_requests = bool(self.requests.unfinished_tasks)

            if has_active_session or has_pending_replay or has_unfinished_requests:
                return False

            message = self.find_message(name=name) if name else None
            selected = (
                next((item for item in self.speaks if item.get("id") == speak_id), None)
                if speak_id
                else None
            )
            if selected is None and message is not None:
                selected = next(
                    (item for item in self.speaks if item.get("id") == message.get("speakId")),
                    None,
                )

            should_select_latest_replayable = selected is None and not speak_id and not name

            if should_select_latest_replayable:
                selected = next(
                    (
                        item
                        for item in self.speaks
                        if item.get("status") not in {"DEPRECATED", "ERROR"}
                        and not self.is_muted(request=item)
                    ),
                    None,
                )

            selected_is_unreplayable = (
                selected is None or selected.get("status") in {"DEPRECATED", "ERROR"}
            )

            if selected_is_unreplayable:
                return False

            if message is None:
                message = next(
                    (item for item in self.messages if item.get("speakId") == selected.get("id")),
                    None,
                )

            request = dict(selected)
            request.update(
                {
                    "id": str(selected["id"]),
                    "sourceCommand": "",
                    "sourcePhase": "replay",
                    "manualSpeech": False,
                    "replayName": str(message.get("name", "")) if message else "",
                    "internalReplay": True,
                    "status": "QUEUED",
                    "error": "",
                    "deprecated": "false",
                    "createdAt": datetime.now().astimezone().isoformat(),
                }
            )
            selected["status"] = "QUEUED"
            selected["error"] = ""
            selected["deprecated"] = "false"
            self._replay_pending = True
            self.last_activity = time.monotonic()
            self.requests.put(request)
            return True


    def begin_processing(self, speak_id: str, emotion: str = "") -> None:
        """Mark a synthesis job as actively processing.

        Args:
            speak_id (str): Speak-job identifier.
            emotion (str): Avatar emotion associated with the job.
        """
        with self.lock:
            self.processing_speak_ids.add(speak_id)
            self.processing_emotions[speak_id] = emotion
            self.last_activity = time.monotonic()


    def finish_processing(self, speak_id: str) -> None:
        """Clear a synthesis job without affecting concurrent work.

        Args:
            speak_id (str): Speak-job identifier to clear.
        """
        with self.lock:
            self.processing_speak_ids.discard(speak_id)
            self.processing_emotions.pop(speak_id, None)


    def set_speak_status(self, speak_id: str, status: str, error: str = "") -> None:
        """Update a retained speak job's lifecycle status.

        Args:
            speak_id (str): Speak-job identifier.
            status (str): New lifecycle status.
            error (str): Optional failure detail.
        """
        with self.lock:
            speak = next((item for item in self.speaks if item["id"] == speak_id), None)
            if speak:
                speak["status"] = status
                speak["error"] = error


    def update_speak_text(self, speak_id: str, text: str) -> None:
        """Replace retained visible text for a speak job.

        Args:
            speak_id (str): Speak-job identifier.
            text (str): Updated narration text.
        """
        with self.lock:
            speak = next((item for item in self.speaks if item["id"] == speak_id), None)

            if speak:
                speak["text"] = text
