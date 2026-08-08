# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Toolkit-neutral state projected by the avatar presentation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AvatarRuntimeState(StrEnum):
    """Daemon lifecycle states understood by every avatar backend.

    Attributes:
        AWAITING (str): Idle state with no active presentation.
        THINKING (str): Model inference is in progress.
        WORKING (str): A delegated task is actively running.
        PREPARING (str): A message is being prepared for presentation.
        SPEAKING (str): Audible playback is active.
        MUTED (str): A message is visible without audible playback.
        MUTED_REPLAY (str): A muted message is being replayed.
    """

    AWAITING = "awaiting"
    THINKING = "thinking"
    WORKING = "working"
    PREPARING = "preparing"
    SPEAKING = "speaking"
    MUTED = "muted"
    MUTED_REPLAY = "muted_replay"


_ACTIVE_PRESENTATION_STATES = frozenset({
    AvatarRuntimeState.PREPARING,
    AvatarRuntimeState.SPEAKING,
    AvatarRuntimeState.MUTED,
    AvatarRuntimeState.MUTED_REPLAY,
})


@dataclass(frozen=True, slots=True)
class ProjectedMessageState:
    """One daemon snapshot normalized for toolkit presentation.

    The state owns presentation policy only. Widgets decide how values are
    painted, and transports decide how commands reach the daemon.

    Attributes:
        runtime_state (AvatarRuntimeState): Current daemon lifecycle state.
        active_speak_id (str): Stable identity of the visible message.
        display_text (str): Text currently shown in the bubble.
        emotion (str): Emotion name selected for the visible message.
        consumer_path (str): Active consumer identity.
        codex_thread_id (str): Associated Codex conversation identifier.
        mute_mode (str): Effective mute policy.
        playback_active (bool): Whether the current message is playing.
        progressive_playback_active (bool): Whether batch playback is advancing.
        processing (bool): Whether synthesis or another processing task remains.
        processing_emotion (str): Emotion shown while processing.
        queue_depth (int): Number of messages waiting behind the active one.
        history_count (int): Number of retained display messages.
        visual_remaining_seconds (float): Remaining visible-session duration.
        has_embedded_file (bool): Whether the active message embeds a file.
        manual_speech (bool): Whether speech was manually requested.
    """

    runtime_state: AvatarRuntimeState = AvatarRuntimeState.AWAITING
    active_speak_id: str = ""
    display_text: str = ""
    emotion: str = ""
    consumer_path: str = ""
    codex_thread_id: str = ""
    mute_mode: str = "off"
    playback_active: bool = False
    progressive_playback_active: bool = False
    processing: bool = False
    processing_emotion: str = ""
    queue_depth: int = 0
    history_count: int = 0
    visual_remaining_seconds: float = 0.0
    has_embedded_file: bool = False
    manual_speech: bool = False

    @property
    def owns_active_presentation(self) -> bool:
        """Return whether one logical message owns STOP and the visible session.

        Returns:
            bool: True when a visible or playing message is active.
        """
        return bool(self.active_speak_id) and (
            self.playback_active
            or self.progressive_playback_active
            or self.runtime_state in _ACTIVE_PRESENTATION_STATES
        )

    @property
    def speaking_animation_active(self) -> bool:
        """Return whether audible playback, rather than synthesis, owns speaking.

        Returns:
            bool: True only while playback and the speaking state are active.
        """
        return self.playback_active and self.runtime_state is AvatarRuntimeState.SPEAKING

    @property
    def processing_indicator_active(self) -> bool:
        """Return whether TTS or another declared processing task remains active.

        Returns:
            bool: True while the daemon reports active processing.
        """
        return self.processing
