# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Toolkit-neutral PLAY, REPLAY, STOP, and reaction policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, Protocol

from brain.presentation.avatar.interactivity.presentation_state import ProjectedMessageState


class AvatarControlIntent(StrEnum):
    """Semantic intent emitted by avatar controls.

    Attributes:
        PLAY (str): Request playback of the selected visible message.
        REPLAY (str): Request replay of a retained message.
        STOP (str): Stop the active message and close its bubble.
        REACTION (str): Request an idle double-click reaction.
    """

    PLAY = "play"
    REPLAY = "replay"
    STOP = "stop"
    REACTION = "reaction"


@dataclass(frozen=True, slots=True)
class AvatarCommand:
    """Transport-neutral daemon command selected by interaction policy.

    Attributes:
        intent (AvatarControlIntent): Semantic action to execute.
        endpoint (str): Daemon endpoint associated with the action.
        payload (Mapping[str, object]): Endpoint-specific JSON-compatible values.
    """

    intent: AvatarControlIntent
    endpoint: str
    payload: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReplayTarget:
    """Identity of the message currently projected by a toolkit adapter.

    Attributes:
        speak_id (str): Stable retained speech identifier.
        audio_name (str): Optional generated audio asset name.
        has_embedded_file (bool): Whether a file is visible in the bubble.
        manual_speech (bool): Whether the file was manually requested.
        browsing_history (bool): Whether the bubble shows a historical item.
    """

    speak_id: str = ""
    audio_name: str = ""
    has_embedded_file: bool = False
    manual_speech: bool = False
    browsing_history: bool = False


@dataclass(frozen=True, slots=True)
class ReactionIntent:
    """Complete reaction request emitted after an idle double-click.

    Attributes:
        text (str): Reaction text sent to the daemon.
        emotion (str): Emotion state used for the reaction.
        language (str): Speech language code.
        prelude_seconds (int): Optional reaction lead-in duration.
    """

    text: str
    emotion: str = "reacting"
    language: str = "es"
    prelude_seconds: int = 1

    def command(self) -> AvatarCommand:
        """Build the queue-cleaning reaction command.

        Returns:
            AvatarCommand: Reaction command that preserves speak messages only.
        """
        return AvatarCommand(
            intent=AvatarControlIntent.REACTION,
            endpoint="/speak",
            payload={
                "text": self.text,
                "lang": self.language,
                "emotion": self.emotion,
                "preludeSeconds": self.prelude_seconds,
                "keepSpeaksOnly": True,
                "clearQueueBefore": True,
            },
        )


class AvatarCommandPort(Protocol):
    """Execute one semantic avatar command through an adapter."""

    def execute(self, command: AvatarCommand) -> None:
        """Deliver a selected command without changing its semantics.

        Args:
            command (AvatarCommand): Semantic command selected by policy.

        Returns:
            None: The adapter completes delivery or raises its transport error.
        """
        ...


class InteractionController:
    """Own the single/double-click command decision once for Qt and Tk."""

    @staticmethod
    def primary_click(
        presentation: ProjectedMessageState,
        target: ReplayTarget = ReplayTarget(),
    ) -> AvatarCommand:
        """Return terminal STOP for active ownership, otherwise PLAY or REPLAY.

        Args:
            presentation (ProjectedMessageState): Current daemon presentation state.
            target (ReplayTarget): Message projected by the toolkit adapter.

        Returns:
            AvatarCommand: Semantic command for the primary click.
        """
        if presentation.owns_active_presentation:
            return AvatarCommand(AvatarControlIntent.STOP, "/stop-current-message")

        if target.has_embedded_file and target.manual_speech and not target.browsing_history:
            return AvatarCommand(AvatarControlIntent.PLAY, "/narrate-active-file")

        if target.speak_id:
            return AvatarCommand(
                AvatarControlIntent.REPLAY,
                "/replay",
                {"speakId": target.speak_id},
            )

        if target.audio_name:
            return AvatarCommand(
                AvatarControlIntent.REPLAY,
                "/replay",
                {"name": target.audio_name},
            )

        return AvatarCommand(AvatarControlIntent.PLAY, "/replay")

    @staticmethod
    def double_click(
        presentation: ProjectedMessageState,
        reaction: ReactionIntent,
    ) -> AvatarCommand:
        """Stop an active message once; react only while presentation is idle.

        Args:
            presentation (ProjectedMessageState): Current daemon presentation state.
            reaction (ReactionIntent): Reaction to enqueue when idle.

        Returns:
            AvatarCommand: STOP command for active ownership or reaction command when idle.
        """
        if presentation.owns_active_presentation:
            return AvatarCommand(AvatarControlIntent.STOP, "/stop-current-message")

        return reaction.command()
