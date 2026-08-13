"""Run the memory-only voice synthesis daemon with a one-hour idle TTL."""

from __future__ import annotations

import queue
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Protocol, Required, TypeAlias, TypedDict, cast

SOURCE_ROOT = Path(__file__).resolve().parents[4]


if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.infrastructure.avatar.configuration.avatar_config import load_avatar_config
from brain.infrastructure.avatar.process import avatar_supervision
from brain.infrastructure.avatar.process.avatar_process import AvatarProcessSupervisor
from brain.infrastructure.voice.audio import synthesis_pipeline as tts_pipeline, voice_persistence
from brain.infrastructure.voice.audio.audio_store import AudioStoreMixin
from brain.infrastructure.voice.audio.engines import LocalPlayback, play_audio_url
from brain.infrastructure.voice.daemon import http_api
from brain.infrastructure.voice.daemon.daemon_client import (
    VOICE_DAEMON_HOST,
    VOICE_DAEMON_PORT,
    VOICE_DAEMON_URL,
)
from brain.infrastructure.voice.daemon.process_lease import (
    ProcessLease,
    core_process_lease_name,
)
from brain.infrastructure.voice.daemon.runtime_state import (
    CORE_RUNTIME_ID,
    DAEMON_INSTANCE_ID,
    IDLE_TTL_SECONDS,
    RuntimeStateMixin,
    estimated_speech_seconds,
)
from brain.infrastructure.voice.messaging.message_queue import (
    MessageQueueMixin,
    bounded_prelude_seconds,
)
from brain.infrastructure.voice.messaging.message_session import (
    ActiveMessageSession,
    MessageSessionMixin,
)

semantic_speech_chunks = tts_pipeline.semantic_speech_chunks
supervise_loop = avatar_supervision.run_avatar_supervision
supervise_window = avatar_supervision.supervise_avatar_window
consume_persistence = voice_persistence.consume_persistence_requests
enqueue_persistence = voice_persistence.enqueue_message_persistence

EngineConfigValue: TypeAlias = str | int | float | bool | None


class _VoiceRequest(TypedDict, total=False):
    """Describe the daemon-owned request fields read by this module."""

    id: Required[str]
    text: Required[str]
    displayText: str
    emotion: str
    signalKey: str
    sourceCommand: str
    sourcePhase: str
    deprecated: str
    internalReplay: bool
    hideWhenMuted: bool
    manualSpeech: bool
    showMessage: bool
    preludeSeconds: float | str
    replayName: str


class _RetainedAudioMessage(TypedDict):
    """Describe the retained audio identity required for URL playback."""

    name: str


class _TtsBatch(TypedDict, total=False):
    """Describe one private TTS producer-to-player batch."""

    request: _VoiceRequest
    message: _RetainedAudioMessage
    localPlayback: LocalPlayback
    error: str


class _TtsBatchPublisher(Protocol):
    """Define the batch-publishing capability used by the producer.

    This narrow local contract keeps payload construction separate from the
    session lifecycle owner without exposing that owner publicly.
    """

    def accepts(self, token: int) -> bool:
        """Return whether this owner accepts the specified generation.

        Args:
            token: Generation that wants to publish or store a batch.

        Returns:
            bool: Whether this owner still accepts the generation.
        """

    def publish(self, batch: _TtsBatch, token: int) -> bool:
        """Publish one synthesized batch for the active generation.

        Args:
            batch: Batch payload selected for playback.
            token: Generation that owns the batch.

        Returns:
            bool: Whether the batch was accepted by the owner.
        """


class _PlaybackHandle(Protocol):
    """Define the wait capability shared by registered playback handles."""

    def wait(self) -> int:
        """Wait until playback completes or stops.

        Args:
            No arguments are accepted beyond the playback handle instance.

        Returns:
            int: Playback process result or completion status.
        """


@dataclass(frozen=True)
class _PlaybackPlan:
    """Describe the already-selected starter for one playback batch.

    Attributes:
        is_local_playback: Whether the batch owns a local playback handle.
        starter: Deferred operation that registers and starts playback.
    """

    is_local_playback: bool
    starter: Callable[[], _PlaybackHandle]


class VoiceMemory(
    RuntimeStateMixin, MessageQueueMixin, MessageSessionMixin, AudioStoreMixin
):
    """Compose runtime state, FIFO, session, and audio-store experts."""


MEMORY = VoiceMemory()


def paid_synthesis_cache_key(request: dict[str, str]) -> str:
    """Return the cache key used by the delegated synthesis policy.

    Args:
        request: Voice request whose synthesis settings determine its cache key.

    Returns:
        str: Stable cache key for the request.
    """

    return tts_pipeline.paid_synthesis_cache_key(
        request,
        config_loader=load_avatar_config,
    )


def synthesize(request: dict[str, str]) -> bytes | LocalPlayback:
    """Synthesize one request through the configured voice provider.

    Args:
        request: Voice request containing text and provider settings.

    Returns:
        bytes | LocalPlayback: Audio bytes or a local playback handle.
    """

    return tts_pipeline.synthesize(
        request,
        config_loader=load_avatar_config,
        edge_synthesizer=_synthesize_edge_audio,
    )


def sanitize_engine_text(text: str, engine_config: dict[str, EngineConfigValue]) -> str:
    """Sanitize text using the delegated engine policy.

    Args:
        text: Text to sanitize before synthesis.
        engine_config: Provider configuration used by the sanitizer.

    Returns:
        str: Sanitized synthesis text.
    """

    return tts_pipeline.sanitize_engine_text(text, engine_config)


_synthesize_edge_audio = tts_pipeline._synthesize_edge_audio


def synthesize_or_reuse(request: dict[str, str]) -> bytes | LocalPlayback:
    """Synthesize a request or reuse its runtime-owned cached audio.

    Args:
        request: Voice request whose audio may already be cached.

    Returns:
        bytes | LocalPlayback: Cached or newly synthesized playback value.
    """

    return tts_pipeline.synthesize_or_reuse(
        MEMORY,
        request,
        synthesize_fn=synthesize,
        config_loader=load_avatar_config,
    )


def _display_text_contains_markdown_table(display_text: str) -> bool:
    """Return whether visible text already contains a Markdown table separator.

    Args:
        display_text: Candidate visible message text.

    Returns:
        bool: Whether the text contains the table separator used by the daemon.
    """

    return "\n| ---" in display_text


def cohere_signal_text(request: dict[str, str]) -> str:
    """Refine an approved CLI signal into safe natural Spanish.

    Args:
        request (dict[str, str]): Voice request with an optional signal key.

    Returns:
        str: Safe refined narration or a deterministic fallback.
    """

    original = request["text"].strip()
    pre_processor = request.get("preProcessor", "<default>")

    # Guard clause: verify required entity presence
    if pre_processor == "<none>" or not original:
        return original

    # Conditional check: evaluate domain preconditions and invariants
    if pre_processor == "<default>" and not request.get("signalKey"):
        return original

    fallback = safe_signal_fallback(
        original=original,
        signal_key=request.get("signalKey", ""),
    )

    # Exception safety: execute operation within error boundary
    try:
        from brain.application.querying.llm import request_query_json
        from brain.infrastructure.voice.narration.narration_prompts import (
            SPANISH_NARRATION_SYSTEM_PROMPT,
        )

        # Conditional check: evaluate domain preconditions and invariants
        if pre_processor == "<default>":
            signal_key = request.get("signalKey", "")
            user_prompt = f"Tipo de señal: {signal_key}\nBorrador factual: {original}"

        else:
            user_prompt = pre_processor.replace("{OUTPUT}", original)

        payload = request_query_json(
            system_prompt=SPANISH_NARRATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=1200,
        )
        rewritten = str(payload.get("text", "")).strip()

        # Conditional check: evaluate domain preconditions and invariants
        if is_safe_refined_narration(rewritten, fallback=fallback):
            return rewritten

        return fallback

    # Failure recovery: handle execution or transport exception
    except Exception:
        return fallback


def cohere_signal_presentation(request: dict[str, str]) -> None:
    """Resolve a private CLI draft into safe spoken and visible prose.

    Args:
        request (dict[str, str]): Mutable canonical voice request.

    Returns:
        None: The request is updated in place.
    """
    request["text"] = cohere_signal_text(request)

    has_signal = bool(request.get("signalKey"))
    current_display = request.get("displayText", "")
    preserves_table = _display_text_contains_markdown_table(current_display)

    # Conditional check: evaluate domain preconditions and invariants
    if has_signal and not preserves_table:
        request["displayText"] = request["text"]


def safe_signal_fallback(*, original: str, signal_key: str) -> str:
    """Extract a reviewed fallback sentence for a signal.

    Args:
        original (str): Original reviewed draft.
        signal_key (str): Signal identity used to select the fallback.

    Returns:
        str: Explicit safe line, a canonical fallback, or the original text.
    """

    # Conditional check: evaluate domain preconditions and invariants
    if not signal_key.startswith("reviewed-template:"):
        return original

    fallback_line = next(
        (
            line

            # Iteration: loop over collection elements
            for line in original.splitlines()

            # Conditional check: evaluate domain preconditions and invariants
            if line.startswith("Fallback seguro: ")
        ),
        "",
    )
    fallback = fallback_line.removeprefix("Fallback seguro: ").strip()

    return fallback or spanish_signal_fallback(signal_key)


def is_safe_refined_narration(text: str, fallback: str = "") -> bool:
    """Validate that refined narration does not expose internal structure.

    Args:
        text (str): Candidate refined narration.
        fallback (str): Deterministic approved fallback.

    Returns:
        bool: Whether the candidate is safe to present.
    """

    # Content check: validate message text payload
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

    # Conditional check: evaluate domain preconditions and invariants
    if any(marker in normalized for marker in technical_markers):
        return False

    generic_actions = (
        "completar la tarea",
        "completar la operación",
        "completado la tarea",
        "completado la operación",
    )
    fallback_normalized = fallback.casefold()

    return not any(
        action in normalized and action not in fallback_normalized

        # Iteration: loop over collection elements
        for action in generic_actions
    )


def spanish_signal_fallback(signal_key: str) -> str:
    """Return a guaranteed Spanish sentence without unverified metadata.

    Args:
        signal_key (str): Signal identity selecting a template.

    Returns:
        str: Deterministic Spanish notification.
    """
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
    """Run the daemon-owned logical FIFO one session at a time.

    Args:
        No arguments are accepted.

    Returns:
        None: The consumer runs until the daemon process exits.
    """

    # Loop execution: process until boundary condition is satisfied
    while True:
        request = MEMORY.get_next_request()

        # Exception safety: execute operation within error boundary
        try:
            process_message_request(request)

        finally:
            MEMORY.requests.task_done()


def _request_is_terminal(
    request: _VoiceRequest,
    speak_id: str,
    is_internal_replay: bool,
) -> bool:
    """Resolve terminal requests before any processing-side-effects occur.

    Args:
        request: Canonical queue request currently being considered.
        speak_id: Identity passed through the runtime state unchanged.
        is_internal_replay: Original replay flag whose truthiness controls reset.

    Returns:
        bool: Whether the FIFO consumer must stop handling this request.
    """

    # Conditional check: evaluate domain preconditions and invariants
    if is_internal_replay:
        # Concurrency control: acquire lock for thread-safe state mutation
        with MEMORY.lock:
            MEMORY._replay_pending = False

        return False

    # Identity check: verify instance ID invariants
    if not MEMORY.is_speak_terminal(speak_id):
        return False

    return True


def _prepare_external_message_presentation(
    request: _VoiceRequest,
    speak_id: str,
    signal_key: str,
    display_text: str,
) -> None:
    """Prepare and persist the visible form of one non-replay request.

    Args:
        request: Mutable canonical queue request.
        speak_id: Identity used for presentation state updates.
        signal_key: Optional signal identity governing presentation behavior.
        display_text: Existing visible text that may preserve a Markdown table.

    Returns:
        None: The request and runtime presentation state are updated in place.
    """
    has_signal = bool(signal_key)
    preserves_table = _display_text_contains_markdown_table(display_text)

    # Conditional check: evaluate domain preconditions and invariants
    if has_signal and not preserves_table:
        MEMORY.begin_thinking(speak_id)

    is_partial_command = MEMORY.mute_mode == "partial" and bool(
        request.get("sourceCommand")
    )
    is_partial_command_output = (
        is_partial_command and request.get("sourcePhase") == "output"
    )

    # Conditional check: evaluate domain preconditions and invariants
    if is_partial_command_output:
        request["text"] = safe_signal_fallback(
            original=request["text"],
            signal_key=signal_key,
        )

    else:
        cohere_signal_presentation(request)

    MEMORY.update_speak_text(speak_id, request["text"])
    enqueue_message_persistence(request=request)


def _open_message_session(
    request: _VoiceRequest,
    speak_id: str,
) -> ActiveMessageSession | None:
    """Wait for a current window and open one active message session.

    Args:
        request: Canonical queue request awaiting a window lease.
        speak_id: Identity checked for terminal state between lease attempts.

    Returns:
        ActiveMessageSession | None: Active session, or no session when stopped.
    """
    is_internal_replay = bool(request.get("internalReplay"))

    # Loop execution: process until boundary condition is satisfied
    while True:
        window_lease = MEMORY.wait_for_window(request)

        # Conditional check: evaluate domain preconditions and invariants
        if window_lease is None:
            return None

        session = MEMORY.begin_message_session(request, window_lease)

        # Conditional check: evaluate domain preconditions and invariants
        if session is not None:
            return session

        # Identity check: verify instance ID invariants
        if not is_internal_replay and MEMORY.is_speak_terminal(str(speak_id)):
            return None


def _complete_muted_message_session(
    session: ActiveMessageSession,
    request: _VoiceRequest,
) -> None:
    """Keep a muted message visible for its original estimated duration.

    Args:
        session: Active muted session that owns visual state.
        request: Canonical request containing mute-display behavior.

    Returns:
        None: The muted session remains visible for its configured duration.
    """

    # Conditional check: evaluate domain preconditions and invariants
    if request.get("hideWhenMuted", False):
        MEMORY.close_message_session(session, "DONE")

        return

    visual_seconds = estimated_speech_seconds(request["text"])
    MEMORY.muted_visual_deadline = time.monotonic() + visual_seconds
    session.presentation_done.wait(timeout=visual_seconds)

    # Conditional check: evaluate domain preconditions and invariants
    if session.cancelled.is_set():
        muted_status = "CANCELLED"

    else:
        muted_status = "DONE"

    MEMORY.close_message_session(session, muted_status)


def process_message_request(request: _VoiceRequest) -> None:
    """Consume one logical message through readiness, presentation, and TTS.

    The Qt readiness gate is crossed before active identity, bubble, mute
    decision, or synthesis exists. Once active, STOP owns terminal cancellation
    and the FIFO caller may move to its next message only after this returns.

    Args:
        request: Canonical queue request consumed by the single FIFO worker.

    Returns:
        None: The request completes, is cancelled, or records an error.
    """
    session: ActiveMessageSession | None = None
    preserve_visual = False
    speak_id = request["id"]
    is_internal_replay = request.get("internalReplay")
    signal_key = request.get("signalKey", "")
    display_text = request.get("displayText", "")

    # Exception safety: execute operation within error boundary
    try:
        # Identity check: verify instance ID invariants
        if _request_is_terminal(request, speak_id, is_internal_replay):
            return

        MEMORY.begin_processing(speak_id, request.get("emotion", ""))
        MEMORY.set_speak_status(speak_id, "WORKING")

        # Conditional check: evaluate domain preconditions and invariants
        if not is_internal_replay:
            _prepare_external_message_presentation(
                request,
                speak_id,
                signal_key,
                display_text,
            )

        session = _open_message_session(request, speak_id)

        # Conditional check: evaluate domain preconditions and invariants
        if session is None:
            return

        MEMORY.finish_thinking()

        # Conditional check: evaluate domain preconditions and invariants
        if request.get("manualSpeech"):
            MEMORY.show_manual_file(request)
            preserve_visual = True
            MEMORY.close_message_session(session, "DONE", preserve_visual=True)

            return

        # Conditional check: evaluate domain preconditions and invariants
        if session.muted:
            _complete_muted_message_session(session, request)

            return

        delegate_tts_for_session(session)

    # Failure recovery: handle execution or transport exception
    except Exception as exc:
        MEMORY.finish_thinking()

        replay_restored = MEMORY.restore_replay_record(request)

        # Conditional check: evaluate domain preconditions and invariants
        if not replay_restored:
            MEMORY.set_speak_status(speak_id, "ERROR", error=str(exc))

        # Conditional check: evaluate domain preconditions and invariants
        if session is not None:
            session.cancel()
            MEMORY.close_message_session(session, "ERROR")

    finally:
        # Conditional check: evaluate domain preconditions and invariants
        if session is not None and not preserve_visual:
            # Conditional check: evaluate domain preconditions and invariants
            if session.cancelled.is_set():
                status = "CANCELLED"

            else:
                status = "DONE"

            MEMORY.close_message_session(session, status)

        MEMORY.finish_processing(speak_id)


def delegate_tts_for_session(session: ActiveMessageSession) -> bool:
    """Validate the Qt lease at the exact TTS delegation boundary.

    Args:
        session: Active message session being delegated to TTS.

    Returns:
        bool: Whether TTS delegation was accepted by the current window lease.
    """

    # Conditional check: evaluate domain preconditions and invariants
    if not MEMORY.window_lease_is_current(session.window_lease):
        MEMORY.stop_active_speak()

        return False
    run_tts_batch_session(session)

    return True


def _publish_replay_tts_batch(
    session: ActiveMessageSession,
    replay_name: str,
    token: int,
    publisher: _TtsBatchPublisher,
) -> None:
    """Publish the retained message selected by a replay request.

    Args:
        session: Active session that owns the replay request.
        replay_name: Retained message identity selected for replay.
        token: Generation that owns the replay batch.
        publisher: Narrow batch-publishing capability of the TTS owner.

    Raises:
        LookupError: If the selected retained message is unavailable.

    Returns:
        None: The retained message is published to the TTS owner.
    """

    message = MEMORY.find_message(name=replay_name)

    # Conditional check: evaluate domain preconditions and invariants
    if message is None:
        raise LookupError(f"Replay message not found: {replay_name}")

    publisher.publish({"request": session.request, "message": message}, token)


def _chunk_request(
    request: _VoiceRequest,
    chunk: str,
    chunk_index: int,
    chunk_count: int,
) -> _VoiceRequest:
    """Copy a request and attach the current progressive chunk metadata.

    Args:
        request: Original canonical request for the session.
        chunk: Semantic speech text for this batch.
        chunk_index: Zero-based position of the chunk.
        chunk_count: Total semantic chunks selected for the request.

    Returns:
        _VoiceRequest: Independent request copy consumed by synthesis.
    """

    chunk_request = cast(_VoiceRequest, dict(request))
    chunk_metadata = {
        "text": chunk,
        "chunkIndex": chunk_index,
        "chunkCount": chunk_count,
    }
    chunk_request.update(chunk_metadata)

    return chunk_request


def _publish_synthesized_tts_batch(
    session: ActiveMessageSession,
    chunk_request: _VoiceRequest,
    chunk_index: int,
    synthesis: bytes | LocalPlayback,
    token: int,
    combined_audio: list[bytes],
    publisher: _TtsBatchPublisher,
) -> bool:
    """Publish one synthesized chunk and retain bytes for the combined cache.

    Args:
        session: Active session that owns the synthesized chunk.
        chunk_request: Copy of the request annotated with chunk metadata.
        chunk_index: Zero-based chunk position for progressive storage.
        synthesis: Produced audio bytes or a local playback handle.
        token: Generation that owns this batch.
        combined_audio: Byte chunks retained for the final combined store.
        publisher: Narrow batch-publishing capability of the TTS owner.

    Returns:
        bool: Whether the batch was accepted for playback.
    """

    # Type validation: verify parameter data type
    if isinstance(synthesis, bytes):
        combined_audio.append(synthesis)
        message = MEMORY.retain_progressive_audio(
            session.speak_id, chunk_index, synthesis
        )

        return publisher.publish(
            cast(_TtsBatch, {"request": chunk_request, "message": message}), token
        )

    return publisher.publish(
        cast(_TtsBatch, {"request": chunk_request, "localPlayback": synthesis}), token
    )


def _store_combined_audio_if_current(
    session: ActiveMessageSession,
    token: int,
    request: _VoiceRequest,
    combined_audio: list[bytes],
    publisher: _TtsBatchPublisher,
) -> None:
    """Store the byte cache only after the original acceptance checks pass.

    Args:
        session: Active session that owns the synthesized audio.
        token: Generation that must still own the session.
        request: Original request whose text labels the combined cache.
        combined_audio: Produced byte chunks accumulated in order.
        publisher: TTS owner used for the original acceptance check.

    Returns:
        None: The combined audio is stored only when the session is current.
    """

    # Conditional check: evaluate domain preconditions and invariants
    if not combined_audio:
        return

    # Conditional check: evaluate domain preconditions and invariants
    if not MEMORY.session_accepts(session, token) or not publisher.accepts(token):
        return

    combined_payload = b"".join(combined_audio)
    MEMORY.store(combined_payload, speak_id=session.speak_id, text=request["text"])


def _produce_tts_batches(session: ActiveMessageSession) -> None:
    """Synthesize bounded chunks into one session-private batch queue.

    Args:
        session: Audible session that exclusively owns the producer queue.

    Returns:
        None: Produced batches are published until synthesis or cancellation ends.
    """

    tts = session.tts

    # Conditional check: evaluate domain preconditions and invariants
    if tts is None:
        return

    token = session.generation
    request = session.request
    combined_audio: list[bytes] = []

    # Exception safety: execute operation within error boundary
    try:
        replay_name = str(request.get("replayName", ""))

        # Conditional check: evaluate domain preconditions and invariants
        if replay_name:
            _publish_replay_tts_batch(session, replay_name, token, tts)

            return

        chunk_limit = load_avatar_config().tts_chunks_size
        chunks = semantic_speech_chunks(request["text"], limit=chunk_limit)
        MEMORY.mark_progressive_speak(session.speak_id, len(chunks))

        # Iteration: loop over collection elements
        for chunk_index, chunk in enumerate(chunks):
            # Conditional check: evaluate domain preconditions and invariants
            if not MEMORY.session_accepts(session, token) or not tts.accepts(token):
                return

            chunk_request = _chunk_request(request, chunk, chunk_index, len(chunks))
            synthesis = synthesize_or_reuse(chunk_request)

            # Conditional check: evaluate domain preconditions and invariants
            if not MEMORY.session_accepts(session, token) or not tts.accepts(token):
                return

            # Conditional check: evaluate domain preconditions and invariants
            if not _publish_synthesized_tts_batch(
                session,
                chunk_request,
                chunk_index,
                synthesis,
                token,
                combined_audio,
                tts,
            ):
                return

        _store_combined_audio_if_current(session, token, request, combined_audio, tts)

    # Failure recovery: handle execution or transport exception
    except Exception as exc:
        tts.publish(cast(_TtsBatch, {"error": str(exc)}), token)

    finally:

        # Processing chrome represents synthesis work only. Once the producer
        # has rendered every available segment, playback may continue without
        # leaving the processing indicator active.
        MEMORY.finish_processing(session.speak_id)
        tts.producer_done.set()


def run_tts_batch_session(session: ActiveMessageSession) -> None:
    """Render and play the private batch queue for one audible message.

    Args:
        session: Audible message session owning the private TTS queue.

    Returns:
        None: Batches are played until production or cancellation completes.

    Raises:
        RuntimeError: If the session has no TTS batch owner.
    """

    tts = session.tts

    # Conditional check: evaluate domain preconditions and invariants
    if tts is None:
        raise RuntimeError("Audible message session has no TTS batch owner.")

    token = session.generation
    threading.Thread(
        target=_produce_tts_batches,
        args=(session,),
        daemon=True,
        name=f"voice-synthesis-{session.speak_id}",
    ).start()

    # Loop execution: process until boundary condition is satisfied
    while MEMORY.session_accepts(session, token) and tts.accepts(token):
        # Exception safety: execute operation within error boundary
        try:
            batch = tts.batches.get(timeout=0.025)

        # Failure recovery: handle execution or transport exception
        except queue.Empty:
            # Conditional check: evaluate domain preconditions and invariants
            if tts.producer_done.is_set():
                break

            continue

        # Exception safety: execute operation within error boundary
        try:
            # Conditional check: evaluate domain preconditions and invariants
            if "error" in batch:
                raise RuntimeError(str(batch["error"]))
            _play_tts_batch(session, batch, token)

        finally:
            tts.batches.task_done()

    tts.finished.set()


def _prepare_session_playback(session: ActiveMessageSession) -> None:
    """Prepare the visible playback state using the original session request.

    Args:
        session: Active session whose visible state will be prepared.

    Returns:
        None: Playback presentation state is prepared in runtime memory.
    """

    show_message = bool(session.request.get("showMessage", True))

    # Conditional check: evaluate domain preconditions and invariants
    if show_message:
        text = session.request["text"]
        emotion = session.request.get("emotion", "")
        display_text = session.request.get("displayText", "")

    else:
        text = ""
        emotion = ""
        display_text = ""

    MEMORY.prepare_playback(
        text,
        emotion,
        display_text,
        session.speak_id,
    )


def _playback_plan(
    session: ActiveMessageSession,
    batch: _TtsBatch,
    generation: int,
) -> _PlaybackPlan:
    """Select the original local or remote starter for one batch.

    Args:
        session: Active session that owns callback identity.
        batch: Synthesized batch selected by the playback consumer.
        generation: Generation passed unchanged to remote callbacks.

    Returns:
        _PlaybackPlan: Deferred starter and local-playback classification.
    """

    request = batch["request"]

    # Conditional check: evaluate domain preconditions and invariants
    if "localPlayback" in batch:
        MEMORY.begin_playback_prelude()

        return _PlaybackPlan(
            is_local_playback=True, starter=batch["localPlayback"].start
        )

    message = batch.get("message")
    prelude_seconds = bounded_prelude_seconds(request.get("preludeSeconds", 0))

    def starter() -> _PlaybackHandle:
        """Start remote playback using the batch's original callback data.

        Args:
            No arguments are accepted; the closure owns the playback metadata.

        Returns:
            _PlaybackHandle: Registered remote playback handle.
        """

        return play_audio_url(
            f"{VOICE_DAEMON_URL}/audio/name/{message['name']}",
            started_callback_url=f"{VOICE_DAEMON_URL}/playback-started",
            preparing_callback_url=f"{VOICE_DAEMON_URL}/playback-preparing",
            prelude_seconds=prelude_seconds,
            duration_callback_url=f"{VOICE_DAEMON_URL}/playback-duration",
            speak_id=session.speak_id,
            generation=generation,
        )

    return _PlaybackPlan(is_local_playback=False, starter=starter)


def _wait_for_tts_batch_playback(
    session: ActiveMessageSession,
    playback: _PlaybackHandle,
) -> None:
    """Wait for one playback handle and release it from the active session.

    Args:
        session: Active session that owns the playback handle.
        playback: Handle returned by the registered playback starter.

    Returns:
        None: Playback completion releases the handle from the active session.
    """

    # Exception safety: execute operation within error boundary
    try:
        playback.wait()

    finally:
        tts = session.tts

        # Conditional check: evaluate domain preconditions and invariants
        if tts is not None:
            tts.release_player(playback)

        # Concurrency control: acquire lock for thread-safe state mutation
        with MEMORY.lock:
            # Conditional check: evaluate domain preconditions and invariants
            if MEMORY.playback is playback:
                MEMORY.playback = None


def _play_tts_batch(
    session: ActiveMessageSession,
    batch: _TtsBatch,
    generation: int,
) -> None:
    """Play one batch while guarding the atomic STOP/start boundary.

    Args:
        session: Active session that owns the playback lifecycle.
        batch: Synthesized batch selected by the private TTS queue.
        generation: Generation that must still own the session.

    Returns:
        None: The batch is played when the session generation remains current.
    """

    # Conditional check: evaluate domain preconditions and invariants
    if not MEMORY.session_accepts(session, generation):
        return

    request = batch["request"]
    _prepare_session_playback(session)
    playback_plan = _playback_plan(session, batch, generation)
    playback = MEMORY.start_registered_playback(session.speak_id, playback_plan.starter)

    # Conditional check: evaluate domain preconditions and invariants
    if playback is None:
        return

    # Conditional check: evaluate domain preconditions and invariants
    if playback_plan.is_local_playback:
        MEMORY.set_playback_duration(
            round(estimated_speech_seconds(request["text"]) * 1000)
        )
        MEMORY.mark_playback_started()

    _wait_for_tts_batch_playback(session, playback)


def enqueue_message_persistence(request: dict[str, str]) -> None:
    """Queue eligible history through the composed runtime.

    Args:
        request: Voice request whose eligible history is queued.

    Returns:
        None: Persistence is delegated to the runtime-owned queue.
    """

    enqueue_persistence(MEMORY, request)


def consume_persistence_requests() -> None:
    """Consume persistence jobs through the composed runtime.

    Args:
        No arguments are accepted.

    Returns:
        None: Persistence jobs are consumed until process exit.
    """

    consume_persistence(MEMORY)


def replay_message(name: str | None = None, speak_id: str | None = None) -> bool:
    """Append replay of one retained identity to the logical message FIFO.

    Args:
        name: Optional retained audio name. The newest message is selected when omitted.
        speak_id: Optional identity associated with the replay request.

    Returns:
        bool: True when the replay request was accepted.
    """

    return MEMORY.enqueue_replay(name=name, speak_id=speak_id)


class VoiceDaemonHandler(http_api.VoiceHttpHandler):
    """Bind the generic HTTP adapter to this daemon composition root."""

    memory_provider = staticmethod(lambda: MEMORY)
    replay_callback = staticmethod(replay_message)
    core_runtime_id = CORE_RUNTIME_ID
    idle_ttl_seconds = IDLE_TTL_SECONDS


def supervise_avatar_window(supervisor: AvatarProcessSupervisor) -> int:
    """Supervise the avatar process using the composed runtime state.

    Args:
        supervisor: Avatar process supervisor being coordinated.

    Returns:
        int: Supervisor result code.
    """

    return supervise_window(MEMORY, supervisor)


def run_avatar_supervision(
    supervisor: AvatarProcessSupervisor,
    stop_event: threading.Event,
    poll_seconds: float = 0.05,
) -> None:
    """Run supervision using the composed runtime state.

    Args:
        supervisor: Avatar process supervisor being coordinated.
        stop_event: Event requesting supervision shutdown.
        poll_seconds: Delay between supervision checks.

    Returns:
        None: Supervision runs until the stop event is set.
    """

    supervise_loop(MEMORY, supervisor, stop_event, poll_seconds)


def main() -> int:
    """Run the daemon until idle shutdown or external stop is requested.

    Returns:
        int: Process exit status.

    Args:
        No arguments are accepted.
    """
    process_lease = ProcessLease(core_process_lease_name("voice-daemon"))

    # Conditional check: evaluate domain preconditions and invariants
    if not process_lease.acquire():
        return 0
    MEMORY.prepare_for_window_spawn()
    threading.Thread(
        target=consume_requests, daemon=True, name="voice-message-fifo"
    ).start()
    threading.Thread(
        target=consume_persistence_requests, daemon=True, name="message-persistence"
    ).start()
    server = ThreadingHTTPServer(
        (VOICE_DAEMON_HOST, VOICE_DAEMON_PORT), VoiceDaemonHandler
    )
    avatar_entrypoint = (
        SOURCE_ROOT / "brain" / "presentation" / "avatar" / "window" / "main.py"
    )
    avatar_supervisor = AvatarProcessSupervisor(avatar_entrypoint, DAEMON_INSTANCE_ID)
    MEMORY.bind_window_supervisor(avatar_supervisor)
    MEMORY.register_window_process(avatar_supervisor.ensure_running())
    supervisor_stop = threading.Event()
    supervisor_thread = threading.Thread(
        target=run_avatar_supervision,
        args=(avatar_supervisor, supervisor_stop),
        daemon=True,
        name="voice-window-supervisor",
    )
    supervisor_thread.start()
    server.timeout = 1.0

    # Exception safety: execute operation within error boundary
    try:
        # Loop execution: process until boundary condition is satisfied
        while not MEMORY.stop_requested and not MEMORY.idle_expired():
            server.handle_request()

    finally:
        MEMORY.cancel_all_instances()
        supervisor_stop.set()
        supervisor_thread.join(timeout=2)
        persistence_deadline = time.monotonic() + 5.0

        # Loop execution: process until boundary condition is satisfied
        while (
            MEMORY.persistence_requests.unfinished_tasks
            and time.monotonic() < persistence_deadline
        ):
            time.sleep(0.025)
        server.server_close()
        avatar_supervisor.close()
        MEMORY.window_pids = []
        process_lease.close()

    return 0


# Conditional check: evaluate domain preconditions and invariants
if __name__ == "__main__":
    raise SystemExit(main())
