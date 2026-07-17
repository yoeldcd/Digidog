# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Unified voice synthesis facade coordinating engines and speech dispatch."""

from __future__ import annotations

from typing import Any

from brain.infrastructure.voice.catalog import VoiceCatalogService
from brain.infrastructure.voice.daemon_client import VoiceDaemonClient
from brain.infrastructure.voice.markdown_narration import markdown_text_for_speech


class VoiceService:
    """Engine-independent avatar presentation and speech facade."""

    def speak(
        self,
        text: str,
        lang: str = "es",
        emotion: str = "",
        codex_thread_id: str = "",
    ) -> None:
        """
        Speak the given text using the configured active engine and voice map.

        Args:
            text (str): Spoken text dialog.
            lang (str): Spoken language ("es", "en", etc.).
            emotion (str): Avatar emotion applied during playback.
            codex_thread_id (str): Optional Codex reply target UUID.
        """
        # A empty/None text means repeat last dialog
        if not text:
            self.repeat_last(emotion=emotion, codex_thread_id=codex_thread_id)
            return

        cleaned_text = clean_text_for_speech(text)
        if not cleaned_text:
            return

        self.present(
            text=cleaned_text,
            display_text=text,
            lang=lang,
            emotion=emotion,
            codex_thread_id=codex_thread_id,
        )

    def present(
        self,
        text: str,
        display_text: str = "",
        lang: str = "es",
        emotion: str = "",
        signal_key: str = "",
        codex_thread_id: str = "",
        source_command: str = "",
        source_phase: str = "",
    ) -> None:
        """Enqueue one visual and spoken projection without exposing an engine."""
        VoiceDaemonClient().speak(
            text=text,
            display_text=display_text or text,
            lang=lang,
            emotion=emotion,
            signal_key=signal_key,
            codex_thread_id=codex_thread_id,
            source_command=source_command,
            source_phase=source_phase,
        )

    def repeat_last(self, emotion: str = "", codex_thread_id: str = "") -> None:
        """Ask the daemon to replay its last in-memory dialogue."""
        VoiceDaemonClient().speak(
            text="",
            lang="es",
            emotion=emotion,
            codex_thread_id=codex_thread_id,
        )

    def list_voices(self, engine_name: str = "") -> dict[str, Any]:
        """Return one requested catalog or resolve the active engine when omitted."""
        return VoiceCatalogService().list_catalog(engine_name=engine_name)

    def set_ambient_state(self, state: str) -> dict[str, Any]:
        """Update persistent avatar state through the service boundary."""
        return VoiceDaemonClient().set_ambient_state(state=state)

    def snapshot(self) -> dict[str, Any]:
        """Return retained avatar presentation jobs."""
        return VoiceDaemonClient().snapshot()


def clean_text_for_speech(text: str) -> str:
    """Return the narrable semantic projection of a rich Markdown message."""
    return markdown_text_for_speech(text)
