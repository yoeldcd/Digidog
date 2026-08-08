# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Typed projection of the voice daemon status payload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from brain.presentation.avatar.interactivity.presentation_state import (
    AvatarRuntimeState,
    ProjectedMessageState,
)


@dataclass(frozen=True, slots=True)
class DaemonStatusProjection:
    """Validated status values consumed by presentation controllers.

    Attributes:
        instance_id (str): Voice daemon instance identifier.
        runtime_state (AvatarRuntimeState): Normalized lifecycle state.
        active_speak_id (str): Stable identity of the active message.
        display_text (str): Text currently shown in the bubble.
        emotion (str): Active message emotion.
        consumer_path (str): Active consumer identity.
        codex_thread_id (str): Associated Codex conversation identifier.
        mute_mode (str): Effective mute policy.
        playback_active (bool): Whether audible playback is active.
        progressive_playback_active (bool): Whether batch playback is active.
        processing (bool): Whether synthesis or processing remains active.
        processing_emotion (str): Emotion shown while processing.
        queue_depth (int): Number of messages waiting behind the active one.
        history_count (int): Number of retained display messages.
        visual_remaining_seconds (float): Remaining visible-session duration.
        has_embedded_file (bool): Whether the active message embeds a file.
        manual_speech (bool): Whether speech was manually requested.
        theme_mode (str): Active light or dark presentation theme.
    """

    instance_id: str
    runtime_state: AvatarRuntimeState
    active_speak_id: str
    display_text: str
    emotion: str
    consumer_path: str
    codex_thread_id: str
    mute_mode: str
    playback_active: bool
    progressive_playback_active: bool
    processing: bool
    processing_emotion: str
    queue_depth: int
    history_count: int
    visual_remaining_seconds: float
    has_embedded_file: bool
    manual_speech: bool
    theme_mode: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "DaemonStatusProjection":
        """Normalize an untrusted JSON status mapping without toolkit imports.

        Args:
            payload (Mapping[str, Any]): Raw daemon status mapping.

        Returns:
            DaemonStatusProjection: Validated, toolkit-neutral status projection.
        """
        raw_state = str(payload.get("state", AvatarRuntimeState.AWAITING.value))

        try:
            runtime_state = AvatarRuntimeState(raw_state)
        except ValueError:
            runtime_state = AvatarRuntimeState.AWAITING

        mute_mode = str(payload.get("muteMode", "total" if payload.get("muted") else "off"))

        if mute_mode not in {"off", "partial", "total"}:
            mute_mode = "off"

        theme_mode = str(payload.get("themeMode", "light"))

        if theme_mode not in {"light", "dark"}:
            theme_mode = "light"

        return cls(
            instance_id=str(payload.get("instanceId", "")),
            runtime_state=runtime_state,
            active_speak_id=str(payload.get("activeSpeakId", "")),
            display_text=str(payload.get("displayText", payload.get("text", ""))),
            emotion=str(payload.get("emotion", "")),
            consumer_path=str(payload.get("activeConsumerPath", "")),
            codex_thread_id=str(payload.get("activeCodexThreadId", "")),
            mute_mode=mute_mode,
            playback_active=bool(payload.get("playbackActive", False)),
            progressive_playback_active=bool(payload.get("progressivePlaybackActive", False)),
            processing=bool(payload.get("processing", False)),
            processing_emotion=str(payload.get("processingEmotion", "")),
            queue_depth=_non_negative_int(payload.get("queueDepth", 0)),
            history_count=_non_negative_int(payload.get("historyCount", 0)),
            visual_remaining_seconds=_non_negative_float(payload.get("visualRemainingSeconds", 0)),
            has_embedded_file=bool(payload.get("hasEmbeddedFile", False)),
            manual_speech=bool(payload.get("manualSpeech", False)),
            theme_mode=theme_mode,
        )

    def presentation(self) -> ProjectedMessageState:
        """Map transport data into the shared presentation state.

        Returns:
            ProjectedMessageState: Toolkit-neutral message presentation state.
        """
        emotion = self.emotion or (
            "happy" if self.runtime_state is AvatarRuntimeState.SPEAKING else ""
        )

        return ProjectedMessageState(
            runtime_state=self.runtime_state,
            active_speak_id=self.active_speak_id,
            display_text=self.display_text,
            emotion=emotion,
            consumer_path=self.consumer_path,
            codex_thread_id=self.codex_thread_id,
            mute_mode=self.mute_mode,
            playback_active=self.playback_active,
            progressive_playback_active=self.progressive_playback_active,
            processing=self.processing,
            processing_emotion=self.processing_emotion if self.processing else "",
            queue_depth=self.queue_depth,
            history_count=self.history_count,
            visual_remaining_seconds=self.visual_remaining_seconds,
            has_embedded_file=self.has_embedded_file,
            manual_speech=self.manual_speech,
        )


def _non_negative_int(value: Any) -> int:
    """Convert an untrusted value to a non-negative integer.

    Args:
        value (Any): Raw status value.

    Returns:
        int: Non-negative integer, or zero when conversion fails.
    """
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _non_negative_float(value: Any) -> float:
    """Convert an untrusted value to a non-negative float.

    Args:
        value (Any): Raw status value.

    Returns:
        float: Non-negative float, or zero when conversion fails.
    """
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0
