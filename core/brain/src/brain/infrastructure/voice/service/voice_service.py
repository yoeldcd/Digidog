# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Unified voice synthesis facade coordinating engines and speech dispatch.

Exposes a high-level API for presenting rich Markdown content and audio synthesis.
Handles synchronous or asynchronous dispatch, dialogue replay requests, and
voice catalog inspection without leaking engine details.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import replace
from typing import TypeAlias, cast

from brain.infrastructure.voice.catalog.voice_catalog import VoiceCatalogService
from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.contracts.instance_results import (
    InstanceEnqueueResult,
    InstanceTerminalResult,
    instance_id_from_payload,
)
from brain.infrastructure.voice.daemon.daemon_client import VoiceDaemonClient
from brain.infrastructure.voice.narration.markdown_narration import (
    markdown_text_for_speech,
    normalize_avatar_message_text,
)


VoiceServiceResponse: TypeAlias = Mapping[str, object]
"""Read-only mapping contract for daemon or catalog responses."""

VoiceEmissionResult: TypeAlias = InstanceEnqueueResult | InstanceTerminalResult | None
"""Typed result returned after asynchronous or synchronous voice dispatch."""


class VoiceService:
    """Provide engine-independent avatar presentation and speech operations.

    Attributes:
        _synchronous: Whether accepted emissions wait for terminal results.
        _timeout_seconds: Maximum bounded wait for one synchronous emission.
    """

    def __init__(
        self,
        *,
        synchronous: bool = False,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Configure whether this facade waits for each accepted emission.

        Args:
            synchronous: Whether each accepted request waits for its own terminal state.
            timeout_seconds: Maximum finite, non-negative wait for one synchronous request.

        Raises:
            ValueError: If the synchronous wait bound is invalid.
        """

        # Type validation: verify parameter data type
        if not isinstance(synchronous, bool):
            raise ValueError("Synchronous mode must be boolean.")

        # Timeout check: verify bounded wait duration
        if not isinstance(timeout_seconds, (int, float)) or isinstance(
            timeout_seconds, bool
        ):
            raise ValueError("Voice wait timeout must be numeric.")

        # Timeout check: verify bounded wait duration
        if not math.isfinite(float(timeout_seconds)) or timeout_seconds < 0:
            raise ValueError("Voice wait timeout must be finite and non-negative.")

        self._synchronous = synchronous
        self._timeout_seconds = timeout_seconds

    def speak(
        self,
        text: str,
        lang: str = "es",
        emotion: str = "",
        codex_thread_id: str = "",
    ) -> VoiceEmissionResult:
        """Speak text through the configured engine and voice map.

        Args:
            text: Spoken dialog, or an empty value to request replay of the last dialog.
            lang: Spoken language code.
            emotion: Avatar emotion applied during playback.
            codex_thread_id: Optional Codex reply target identifier.

        Returns:
            VoiceEmissionResult: Typed enqueue or terminal result, or ``None``
            when the normalized message contains no narrable text.
        """

        # An empty text value asks the daemon to replay the last dialog.

        # Replay shortcut: trigger repeat of last dialogue if text is empty
        if not text:
            return self.repeat_last(emotion=emotion, codex_thread_id=codex_thread_id)

        # Text normalization: clean display and speech text
        display_text = normalize_avatar_message_text(text)
        cleaned_text = clean_text_for_speech(display_text)

        # Content check: validate message text payload
        if not cleaned_text:
            return None

        request = AvatarSpeakRequest(
            text=cleaned_text,
            display_text=display_text,
            lang=lang,
            emotion=emotion,
            codex_thread_id=codex_thread_id,
        )

        return self.present(request)

    def present(self, request: AvatarSpeakRequest) -> VoiceEmissionResult:
        """Enqueue one visual and spoken projection without exposing an engine.

        Args:
            request: Immutable avatar projection and speech request.

        Returns:
            VoiceEmissionResult: Typed terminal result in synchronous mode, or
            typed enqueue result in asynchronous mode.

        Raises:
            ValueError: If the daemon acknowledgement has a non-boolean
            queued field.
        """

        normalized_text = normalize_avatar_message_text(request.text)
        display_source = request.display_text or request.text
        normalized_display_text = normalize_avatar_message_text(display_source)
        normalized_request = replace(
            request,
            text=normalized_text,
            display_text=normalized_display_text,
        )

        # Daemon client dispatch: route request to synchronous or asynchronous client
        voice_daemon_client = VoiceDaemonClient()

        # Conditional check: evaluate domain preconditions and invariants
        if self._synchronous:
            return voice_daemon_client.speak_and_wait(
                normalized_request,
                timeout_seconds=self._timeout_seconds,
            )

        acknowledgement = voice_daemon_client.speak(normalized_request)

        # Type validation: verify parameter data type
        if not isinstance(acknowledgement, dict):
            return None

        queued = acknowledgement.get("queued", True)

        # Type validation: verify parameter data type
        if not isinstance(queued, bool):
            raise ValueError("Daemon queue acknowledgement must be boolean.")

        # Conditional check: evaluate domain preconditions and invariants
        if not queued:
            return None

        # Exception safety: execute operation within error boundary
        try:
            instance_id = instance_id_from_payload(acknowledgement)

        # Validation error handling: convert invalid input to domain exception
        except ValueError:
            return None

        return InstanceEnqueueResult(instance_id=instance_id, queued=queued)

    def repeat_last(
        self,
        emotion: str = "",
        codex_thread_id: str = "",
    ) -> VoiceEmissionResult:
        """Ask the daemon to replay its last in-memory dialogue.

        Args:
            emotion: Optional emotion override.
            codex_thread_id: Optional Codex reply target identifier.

        Returns:
            VoiceEmissionResult: Result for the replay emission.
        """

        replay_request = AvatarSpeakRequest(
            text="",
            lang="es",
            emotion=emotion,
            codex_thread_id=codex_thread_id,
        )

        return self.present(replay_request)

    def list_voices(self, engine_name: str = "") -> VoiceServiceResponse:
        """Return a requested catalog or resolve the active engine.

        Args:
            engine_name: Engine name, or empty for the active engine.

        Returns:
            Normalized voices, models, and engine metadata.
        """

        voice_catalog_service = VoiceCatalogService()
        catalog = voice_catalog_service.list_catalog(engine_name=engine_name)

        return cast(VoiceServiceResponse, catalog)

    def set_ambient_state(self, state: str) -> VoiceServiceResponse:
        """Update persistent avatar state through the service boundary.

        Args:
            state: Canonical ambient state name.

        Returns:
            Daemon acknowledgement and resulting state.
        """

        voice_daemon_client = VoiceDaemonClient()
        response = voice_daemon_client.set_ambient_state(state=state)

        return cast(VoiceServiceResponse, response)

    def snapshot(self) -> VoiceServiceResponse:
        """Return retained avatar presentation jobs.

        Args:
            None.

        Returns:
            Current speak jobs and synthesized messages.
        """

        voice_daemon_client = VoiceDaemonClient()
        response = voice_daemon_client.snapshot()

        return cast(VoiceServiceResponse, response)


def clean_text_for_speech(text: str) -> str:
    """Project a rich Markdown message into narrable semantic text.

    Args:
        text: Rich avatar message.

    Returns:
        Plain semantic narration text.
    """

    narration_text = markdown_text_for_speech(text)

    return narration_text
