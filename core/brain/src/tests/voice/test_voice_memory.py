# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

'Voice in-memory lifecycle, status, mute, and replay contracts.'

import threading
import time
from unittest.mock import Mock, patch
from brain.infrastructure.voice.daemon.daemon import IDLE_TTL_SECONDS, VoiceMemory
from brain.infrastructure.avatar.configuration.avatar_config_dtos import AvatarConfigDTO


def test_reaction_clear_queue_before_leaves_only_reaction_pending() -> None:
    """Idle double-click semantics atomically replace all prior pending messages."""
    memory = VoiceMemory()
    prior_ids = [memory.enqueue(f"Previo {index}", "es") for index in range(3)]

    reaction_id = memory.enqueue("Reacción", "es", clear_queue_before=True)

    assert reaction_id is not None
    assert memory.requests.qsize() == 1
    queued = memory.requests.get_nowait()
    memory.requests.task_done()
    assert queued["id"] == reaction_id
    assert all(
        next(item for item in memory.speaks if item["id"] == prior_id)["status"] == "CANCELLED"
        for prior_id in prior_ids
    )


def test_atomic_stop_start_terminates_player_and_releases_next_session() -> None:
    """A player created at the STOP boundary cannot survive its generation."""
    memory = VoiceMemory()
    first_id = memory.enqueue("Primero", "es")
    first_request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(first_id or "", "WORKING")
    session = memory.begin_message_session(first_request)
    assert session is not None and session.tts is not None
    starter_entered = threading.Event()
    release_starter = threading.Event()
    player = Mock()

    def starter() -> Mock:
        starter_entered.set()
        release_starter.wait(timeout=1)
        return player

    result: list[object | None] = []
    starter_thread = threading.Thread(
        target=lambda: result.append(memory.start_registered_playback(first_id or "", starter)),
    )
    starter_thread.start()
    assert starter_entered.wait(timeout=1)
    stop_thread = threading.Thread(target=memory.stop_active_speak)
    stop_thread.start()
    release_starter.set()
    starter_thread.join(timeout=1)
    stop_thread.join(timeout=1)

    assert starter_thread.is_alive() is False and stop_thread.is_alive() is False
    player.terminate.assert_called_once_with()
    assert memory.active_session is None
    assert memory.active_speak_id == ""


def test_reaction_cleans_command_outputs_but_preserves_direct_speaks() -> None:
    """A reaction leaves living direct speech queued and deprecates command narration."""
    memory = VoiceMemory()
    direct_id = memory.enqueue("Habla directa", "es")
    command_id = memory.enqueue("Salida de comando", "es", source_command="show-backlog", source_phase="output")

    memory.enqueue("Reacci├│n", "es", keep_speaks_only=True)

    direct = next(item for item in memory.speaks if item["id"] == direct_id)
    command = next(item for item in memory.speaks if item["id"] == command_id)
    assert direct["status"] == "QUEUED"
    assert command["status"] == "DEPRECATED"
    assert command["deprecated"] == "true"


def test_cancel_processing_marks_active_job_for_discard() -> None:
    """Cancelling hides processing immediately and invalidates its eventual result."""
    memory = VoiceMemory()
    speak_id = memory.enqueue("Trabajo activo", "es")
    memory.begin_processing(speak_id or "", "focused")

    assert memory.cancel_processing() == 1
    speak = next(item for item in memory.speaks if item["id"] == speak_id)
    assert speak["status"] == "CANCELLED"
    assert speak["deprecated"] == "true"
    assert memory.status()["processing"] is False


def test_voice_memory_retains_speak_and_audio_without_disk() -> None:
    """Retain queue records and synthesized bytes in process memory."""
    memory = VoiceMemory()
    speak_id = memory.enqueue("Memory only", "es")
    assert speak_id is not None
    message = memory.store(b"mp3-bytes", speak_id=speak_id, text="Memory only")

    snapshot = memory.snapshot()
    assert snapshot["speaks"][0]["id"] == speak_id
    assert snapshot["messages"][0]["id"] == message["id"]
    assert memory.find_audio(message["name"]) == b"mp3-bytes"
    assert IDLE_TTL_SECONDS == 3600


def test_voice_memory_finds_named_message_for_direct_replay() -> None:
    memory = VoiceMemory()
    speak_id = memory.enqueue("Mensaje retenido", "es")
    message = memory.store(b"mp3-bytes", speak_id=speak_id, text="Mensaje retenido")

    assert memory.find_message(name=message["name"])["audio"] == b"mp3-bytes"
    assert memory.find_message(name="missing.mp3") is None


def test_replay_uses_logical_fifo_and_preserves_identity_without_history_duplication() -> None:
    """Replay remains a message turn while reusing speakId and retained audio."""
    memory = VoiceMemory()
    retained_speak_id = memory.enqueue("Mensaje retenido", "es")
    original_request = memory.requests.get_nowait()
    memory.requests.task_done()
    retained = memory.store(b"mp3-bytes", speak_id=retained_speak_id or "", text="Mensaje retenido")
    history_count = len(memory.speaks)

    assert memory.enqueue_replay(name=retained["name"]) is True
    replay_request = memory.requests.get_nowait()
    memory.requests.task_done()

    assert replay_request["id"] == retained_speak_id == original_request["id"]
    assert replay_request["replayName"] == retained["name"]
    assert replay_request["internalReplay"] is True
    assert len(memory.speaks) == history_count


def test_default_replay_prefers_newest_cancelled_identity_over_older_done() -> None:
    memory = VoiceMemory()
    older_id = memory.enqueue("Anterior concluido", "es")
    newest_id = memory.enqueue("Último detenido", "es")
    while memory.requests.qsize():
        memory.requests.get_nowait()
        memory.requests.task_done()
    memory.set_speak_status(older_id or "", "DONE")
    newest = next(item for item in memory.speaks if item["id"] == newest_id)
    newest.update({"status": "CANCELLED", "error": "stopped", "deprecated": "true"})

    assert memory.enqueue_replay() is True
    replay = memory.requests.get_nowait()
    memory.requests.task_done()

    assert replay["id"] == newest_id
    assert replay["status"] == "QUEUED"
    assert replay["error"] == ""
    assert replay["deprecated"] == "false"


def test_explicit_cancelled_replay_reuses_identity_without_history_duplication() -> None:
    memory = VoiceMemory()
    speak_id = memory.enqueue("Mensaje detenido", "es")
    memory.requests.get_nowait()
    memory.requests.task_done()
    selected = next(item for item in memory.speaks if item["id"] == speak_id)
    selected.update({"status": "CANCELLED", "error": "stopped", "deprecated": "true"})
    history_count = len(memory.speaks)

    assert memory.enqueue_replay(speak_id=speak_id) is True
    replay = memory.requests.get_nowait()
    memory.requests.task_done()

    assert replay["id"] == speak_id
    assert len(memory.speaks) == history_count
    assert selected["status"] == "QUEUED"
    assert selected["error"] == ""
    assert selected["deprecated"] == "false"


def test_replay_rejects_error_and_deprecated_identities() -> None:
    memory = VoiceMemory()
    error_id = memory.enqueue("Fallido", "es")
    deprecated_id = memory.enqueue("Obsoleto", "es")
    while memory.requests.qsize():
        memory.requests.get_nowait()
        memory.requests.task_done()
    memory.set_speak_status(error_id or "", "ERROR", "provider")
    memory.set_speak_status(deprecated_id or "", "DEPRECATED")

    assert memory.enqueue_replay(speak_id=error_id) is False
    assert memory.enqueue_replay(speak_id=deprecated_id) is False
    assert memory.requests.qsize() == 0


def test_replay_does_not_stack_while_another_replay_waits() -> None:
    memory = VoiceMemory()
    speak_id = memory.enqueue("Mensaje retenido", "es")
    memory.requests.get_nowait()
    memory.requests.task_done()
    retained = memory.store(b"mp3-bytes", speak_id=speak_id or "", text="Mensaje retenido")

    assert memory.enqueue_replay(name=retained["name"]) is True
    assert memory.enqueue_replay(name=retained["name"]) is False
    assert memory.requests.qsize() == 1


def test_voice_status_counts_only_messages_waiting_behind_active() -> None:
    """Private batches never contribute to the public logical queue meter."""
    memory = VoiceMemory()
    first_id = memory.enqueue("Primero", "es")
    second_id = memory.enqueue("Segundo", "es")
    first_request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(first_id or "", "WORKING")
    session = memory.begin_message_session(first_request)
    assert session is not None and session.tts is not None and second_id

    assert memory.status()["queueDepth"] == 1
    assert session.tts.publish({"internal": 1}, session.generation) is True
    assert session.tts.publish({"internal": 2}, session.generation) is True
    assert memory.status()["queueDepth"] == 1


def test_voice_memory_exposes_thinking_without_interrupting_playback_contract() -> None:
    memory = VoiceMemory()
    memory.begin_thinking()
    assert memory.status()["state"] == "thinking"
    assert memory.status()["text"] == "Pensando…"
    memory.prepare_playback("Narración lista", "happy")
    assert memory.status()["state"] == "thinking"
    assert memory.status()["text"] == "Pensando…"
    memory.mark_playback_started()
    assert memory.status()["state"] == "speaking"
    assert memory.status()["text"] == "Narración lista"
    assert memory.status()["activeSpeakId"] == ""
    memory.set_state("thinking", "Pensando…", "thinking")
    memory.finish_thinking()
    assert memory.status()["state"] == "awaiting"


def test_voice_memory_exposes_active_speak_identity() -> None:
    memory = VoiceMemory()
    memory.prepare_playback("Mensaje", "happy", "**Mensaje**", "speak-123")
    memory.mark_playback_started()
    assert memory.status()["activeSpeakId"] == "speak-123"
    memory.set_state("awaiting")
    assert memory.status()["activeSpeakId"] == ""


def test_voice_memory_preserves_active_consumer_provenance() -> None:
    memory = VoiceMemory()
    speak_id = memory.enqueue("Mensaje", "es", consumer_path=r"D:\repo-consumer")
    memory.prepare_playback("Mensaje", "happy", speak_id=speak_id or "")
    memory.mark_playback_started()
    snapshot = memory.status()
    assert snapshot["activeConsumerPath"] == r"D:\repo-consumer"
    assert snapshot["historyCount"] == 1


def test_voice_memory_preserves_codex_thread_metadata() -> None:
    memory = VoiceMemory()
    thread_id = "019f5dad-af67-7533-b394-8fb55258adb2"
    speak_id = memory.enqueue("Mensaje", "es", codex_thread_id=thread_id)
    memory.prepare_playback("Mensaje", "happy", speak_id=speak_id or "")
    memory.mark_playback_started()
    assert memory.status()["activeCodexThreadId"] == thread_id
    message = memory.store(b"mp3", speak_id=speak_id or "", text="Mensaje")
    assert message["codexThreadId"] == thread_id


def test_paid_synthesis_hash_ignores_codex_thread_metadata() -> None:
    from brain.infrastructure.voice.daemon import daemon

    config = {"active_voice_engine": "openai", "voice_engines": {"openai": {"voices": {"es": "shimmer"}}}}
    request = {"text": "Hola", "lang": "es"}
    targeted_request = {**request, "codexThreadId": "019f5dad-af67-7533-b394-8fb55258adb2"}
    with patch.object(daemon, "load_avatar_config", return_value=AvatarConfigDTO.model_validate(config)):
        assert daemon.paid_synthesis_cache_key(request) == daemon.paid_synthesis_cache_key(targeted_request)


def test_idle_expiry_waits_for_pending_or_active_playback() -> None:
    memory = VoiceMemory()
    memory.last_activity = 10
    memory.prepare_playback("Último mensaje", "happy", speak_id="speak-final")
    expired_at = memory.last_activity + IDLE_TTL_SECONDS + 1
    assert memory.idle_expired(expired_at) is False
    memory.pending_playback = None
    memory.set_state("awaiting")
    assert memory.idle_expired(expired_at) is True


def test_partial_and_total_mute_classify_direct_and_narrated_requests() -> None:
    """Partial mute keeps direct speech audible while total mute suppresses all."""
    memory = VoiceMemory()
    direct_request = {"sourceCommand": ""}
    narrated_request = {"sourceCommand": "show-backlog", "sourcePhase": "output"}

    assert memory.toggle_muted() == "partial"
    assert memory.is_muted(request=direct_request) is False
    assert memory.is_muted(request=narrated_request) is True
    assert memory.toggle_muted() == "total"
    assert memory.is_muted(request=direct_request) is True
    assert memory.is_muted(request=narrated_request) is True
    assert memory.toggle_muted() == "off"
    assert memory.is_muted(request=direct_request) is False


def test_muted_active_message_expires_at_natural_playback_deadline() -> None:
    memory = VoiceMemory()
    memory.set_state("speaking", "Mensaje largo", "happy", "**Mensaje largo**")
    memory.set_playback_duration(90_000)
    assert memory.toggle_muted() == "partial"
    assert memory.toggle_muted() == "total"
    snapshot = memory.status()
    assert snapshot["state"] == "muted"
    assert snapshot["visualRemainingSeconds"] > 80
    memory.muted_visual_deadline = time.monotonic() - 1
    snapshot = memory.status()
    assert snapshot["state"] == "awaiting"
    assert snapshot["displayText"] == ""


def test_message_received_while_muted_gets_bounded_visual_lifetime() -> None:
    memory = VoiceMemory()
    memory.toggle_muted()
    memory.show_muted_message("Mensaje visual con varias palabras", "focused", speak_id="muted-one")
    snapshot = memory.status()
    assert snapshot["state"] == "muted_replay"
    assert 2 <= snapshot["visualRemainingSeconds"] <= 180


def test_muted_presentation_wait_is_released_by_pause() -> None:
    """Pausing a muted turn releases the playback worker before its deadline."""
    memory = VoiceMemory()
    memory.toggle_muted()
    memory.show_muted_message("Mensaje visual largo", "focused", speak_id="muted-one")

    memory.stop_playback()

    assert memory.wait_for_muted_presentation(60) is True
    assert memory.status()["state"] == "awaiting"


def test_muted_presentation_wait_expires_naturally_without_cancellation() -> None:
    """A short visual turn completes normally when no control cancels it."""
    memory = VoiceMemory()
    memory.toggle_muted()
    memory.show_muted_message("Breve", "focused", speak_id="muted-one")

    assert memory.wait_for_muted_presentation(0.001) is False


def test_stop_releases_active_muted_session_and_closes_bubble() -> None:
    """Muted ownership is cancellable without ever creating a TTS session."""
    memory = VoiceMemory()
    memory.toggle_muted()
    memory.toggle_muted()
    speak_id = memory.enqueue("Mensaje visual largo", "es")
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(speak_id or "", "WORKING")
    session = memory.begin_message_session(request)
    assert session is not None and session.tts is None
    waiter = threading.Thread(target=session.presentation_done.wait, args=(60,))
    waiter.start()

    assert memory.stop_active_speak() == speak_id
    waiter.join(timeout=1)

    assert waiter.is_alive() is False
    assert session.cancelled.is_set()
    assert memory.status()["state"] == memory.ambient_state
    assert memory.status()["displayText"] == ""


def test_voice_memory_mute_preserves_visual_message_and_status() -> None:
    memory = VoiceMemory()
    memory.set_state("speaking", "Mensaje visible", "happy")

    assert memory.toggle_muted() == "partial"
    assert memory.toggle_muted() == "total"
    assert memory.status()["muted"] is True
    assert memory.status()["muteMode"] == "total"
    assert memory.status()["state"] == "muted"
    assert memory.status()["text"] == "Mensaje visible"

    memory.show_muted_message("Siguiente mensaje", "focused")
    assert memory.status()["text"] == "Siguiente mensaje"
    assert memory.status()["state"] == "muted_replay"
    assert memory.toggle_muted() == "off"
    assert memory.status()["state"] == "awaiting"


def test_muted_replay_restores_latest_request_as_visual_dialogue() -> None:
    memory = VoiceMemory()
    memory.enqueue("Mensaje retenido", "es", emotion="reacting")
    memory.toggle_muted()
    memory.set_state("awaiting")

    assert memory.has_replayable_content() is True
    assert memory.reveal_latest_request() is True
    assert memory.status()["state"] == "muted_replay"
    assert memory.status()["text"] == "Mensaje retenido"
    assert memory.status()["emotion"] == "reacting"


def test_mute_policy_respects_message_level_and_speech_disablement() -> None:
    """Mute modes keep important signals audible and always suppress disabled speech."""
    memory = VoiceMemory()
    cases = (("partial", {"sourceCommand": "query", "messageLevel": "important"}, False), ("partial", {"sourceCommand": "query", "messageLevel": "informative"}, True), ("total", {"sourceCommand": "query", "messageLevel": "important"}, True), ("total", {"sourceCommand": "query", "messageLevel": "informative"}, True), ("off", {"sourceCommand": "query", "speakMessage": False}, True))
    for mute_mode, request, expected_muted in cases:
        memory.mute_mode = mute_mode
        assert memory.is_muted(request=request) is expected_muted