"""Immutable request crossing the avatar-to-voice daemon boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


AvatarSpeakPayload: TypeAlias = dict[str, object]
"""Mutable daemon wire payload produced from an immutable speech request."""


@dataclass(frozen=True, slots=True)
class AvatarSpeakRequest:
    """Carry one complete avatar presentation and speech request.

    Attributes:
        text: Narration source text.
        display_text: Rich text rendered by the avatar.
        lang: Base or regional TTS language code.
        emotion: Avatar animation identity or GIF filename.
        signal_key: Optional reviewed narration identity.
        consumer_path: Repository that owns the message.
        codex_thread_id: Optional Codex conversation target.
        source_command: CLI command that produced the message.
        source_phase: Command lifecycle phase.
        has_embedded_file: Whether the display contains an attached file.
        manual_speech: Whether speech requires an explicit user action.
        show_message: Whether the avatar renders the message.
        speak_message: Whether the voice engine narrates the message.
        hide_when_muted: Whether mute also hides the visual projection.
        message_level: Mute priority, important or informative.
        pre_processor: Raw, default, or custom output processing rule.
    """

    text: str
    display_text: str = ""
    lang: str = "es"
    emotion: str = ""
    signal_key: str = ""
    consumer_path: str = ""
    codex_thread_id: str = ""
    source_command: str = ""
    source_phase: str = ""
    has_embedded_file: bool = False
    manual_speech: bool = False
    show_message: bool = True
    speak_message: bool = True
    hide_when_muted: bool = False
    message_level: str = "informative"
    pre_processor: str = "<default>"

    def to_payload(self) -> AvatarSpeakPayload:
        """Return the daemon's camel-case wire representation.

        Returns:
            Mutable transport payload owned by the caller.
        """
        display_text = self.display_text or self.text

        return {
            "text": self.text,
            "displayText": display_text,
            "lang": self.lang,
            "emotion": self.emotion,
            "signalKey": self.signal_key,
            "consumerPath": self.consumer_path,
            "codexThreadId": self.codex_thread_id,
            "sourceCommand": self.source_command,
            "sourcePhase": self.source_phase,
            "hasEmbeddedFile": self.has_embedded_file,
            "manualSpeech": self.manual_speech,
            "showMessage": self.show_message,
            "speakMessage": self.speak_message,
            "hideWhenMuted": self.hide_when_muted,
            "messageLevel": self.message_level,
            "preProcessor": self.pre_processor,
        }
