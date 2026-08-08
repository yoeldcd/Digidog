# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Unified voice synthesis facade coordinating engines and speech dispatch."""

from __future__ import annotations

from dataclasses import replace
from typing import TypeAlias, cast

from brain.infrastructure.voice.catalog.voice_catalog import VoiceCatalogService
from brain.infrastructure.voice.daemon.daemon_client import VoiceDaemonClient
from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.narration.markdown_narration import (
    markdown_text_for_speech,
    normalize_avatar_message_text,
)


VoiceServiceResponse: TypeAlias = dict[str, object]
"""Mutable daemon or catalog response forwarded by the voice service facade."""


class VoiceService:
    """Provide engine-independent avatar presentation and speech operations."""

    def speak(
        self,
        text: str,
        lang: str = "es",
        emotion: str = "",
        codex_thread_id: str = "",
    ) -> None:
        """Speak text through the configured engine and voice map.

        Args:
            text: Spoken dialog, or an empty value to request replay of the last dialog.
            lang: Spoken language code.
            emotion: Avatar emotion applied during playback.
            codex_thread_id: Optional Codex reply target identifier.
        """

        # An empty text value asks the daemon to replay the last dialog.
        if not text:
            self.repeat_last(emotion=emotion, codex_thread_id=codex_thread_id)
            return

        display_text = normalize_avatar_message_text(text)
        cleaned_text = clean_text_for_speech(display_text)

        if not cleaned_text:
            return

        request = AvatarSpeakRequest(
            text=cleaned_text,
            display_text=display_text,
            lang=lang,
            emotion=emotion,
            codex_thread_id=codex_thread_id,
        )

        self.present(request)

    def present(self, request: AvatarSpeakRequest) -> None:
        """Enqueue one visual and spoken projection without exposing an engine.

        Args:
            request: Immutable avatar projection and speech request.
        """

        normalized_text = normalize_avatar_message_text(request.text)
        display_source = request.display_text or request.text
        normalized_display_text = normalize_avatar_message_text(display_source)
        normalized_request = replace(
            request,
            text=normalized_text,
            display_text=normalized_display_text,
        )

        voice_daemon_client = VoiceDaemonClient()
        voice_daemon_client.speak(normalized_request)

    def repeat_last(self, emotion: str = "", codex_thread_id: str = "") -> None:
        """Ask the daemon to replay its last in-memory dialogue.

        Args:
            emotion: Optional emotion override.
            codex_thread_id: Optional Codex reply target identifier.
        """

        replay_request = AvatarSpeakRequest(
            text="",
            lang="es",
            emotion=emotion,
            codex_thread_id=codex_thread_id,
        )
        voice_daemon_client = VoiceDaemonClient()
        voice_daemon_client.speak(replay_request)

    def list_voices(self, engine_name: str = "") -> VoiceServiceResponse:
        """Return a requested catalog or resolve the active engine.

        Args:
            engine_name (str): Engine name, or empty for the active engine.

        Returns:
            Normalized voices, models, and engine metadata.
        """

        voice_catalog_service = VoiceCatalogService()
        catalog = voice_catalog_service.list_catalog(engine_name=engine_name)

        return cast(VoiceServiceResponse, catalog)

    def set_ambient_state(self, state: str) -> VoiceServiceResponse:
        """Update persistent avatar state through the service boundary.

        Args:
            state (str): Canonical ambient state name.

        Returns:
            Daemon acknowledgement and resulting state.
        """

        voice_daemon_client = VoiceDaemonClient()
        response = voice_daemon_client.set_ambient_state(state=state)

        return cast(VoiceServiceResponse, response)

    def snapshot(self) -> VoiceServiceResponse:
        """Return retained avatar presentation jobs.

        Returns:
            Current speak jobs and synthesized messages.
        """

        voice_daemon_client = VoiceDaemonClient()
        response = voice_daemon_client.snapshot()

        return cast(VoiceServiceResponse, response)


def clean_text_for_speech(text: str) -> str:
    """Project a rich Markdown message into narrable semantic text.

    Args:
        text (str): Rich avatar message.

    Returns:
        Plain semantic narration text.
    """

    narration_text = markdown_text_for_speech(text)

    return narration_text
