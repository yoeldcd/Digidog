# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

'Voice replay, cancellation, and manual narration contracts.'

import json
import threading
from io import BytesIO
from unittest.mock import Mock, patch
from brain.infrastructure.voice.daemon.daemon import VoiceDaemonHandler, VoiceMemory


def test_projected_text_replay_synthesizes_same_identity_without_history_or_persistence() -> None:
    """Replay without retained audio is internal TTS, not a new logical record."""
    from brain.infrastructure.voice.daemon import daemon

    memory = VoiceMemory()
    speak_id = memory.enqueue(
        "Texto proyectado",
        "es",
        display_text="## Archivo proyectado",
        has_embedded_file=True,
        manual_speech=True,
    )
    original = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(speak_id or "", "DONE")
    memory.active_speak_id = speak_id or ""
    before_history = memory.status()["historyCount"]
    before_speaks = [item["id"] for item in memory.speaks]

    body = json.dumps({"speakId": speak_id}).encode("utf-8")
    handler = object.__new__(VoiceDaemonHandler)
    handler.path = "/replay"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler._send_json = Mock()
    with patch.object(daemon, "MEMORY", memory):
        handler.do_POST()
    assert handler._send_json.call_args.kwargs["status"].value == 202
    replay = memory.requests.get_nowait()
    memory.requests.task_done()
    player = Mock()
    player.wait.return_value = 0
    with (
        patch.object(daemon, "MEMORY", memory),
        patch.object(daemon, "synthesize_or_reuse", return_value=b"replayed-audio") as synthesize,
        patch.object(daemon, "play_audio_url", return_value=player),
    ):
        daemon.process_message_request(replay)

    assert replay["internalReplay"] is True
    assert replay["id"] == original["id"] == speak_id
    synthesize.assert_called_once()
    assert memory.messages[0]["speakId"] == speak_id
    assert [item["id"] for item in memory.speaks] == before_speaks
    assert memory.status()["historyCount"] == before_history
    assert memory.persistence_requests.qsize() == 0


def test_late_generation_is_discarded_without_touching_next_message() -> None:
    """STOP invalidates synthesis and a late provider result cannot cross sessions."""
    from brain.infrastructure.voice.daemon import daemon

    memory = VoiceMemory()
    first_id = memory.enqueue("Primero", "es")
    second_id = memory.enqueue("Segundo", "es")
    assert first_id and second_id
    first_request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(first_id, "WORKING")
    first_session = memory.begin_message_session(first_request)
    assert first_session is not None and first_session.tts is not None
    synthesis_started = threading.Event()
    release_synthesis = threading.Event()

    def late_synthesis(_request: dict[str, str]) -> bytes:
        synthesis_started.set()
        release_synthesis.wait(timeout=1)
        return b"late-first-audio"

    with (
        patch.object(daemon, "MEMORY", memory),
        patch.object(daemon, "synthesize_or_reuse", side_effect=late_synthesis),
    ):
        producer = threading.Thread(target=daemon._produce_tts_batches, args=(first_session,))
        producer.start()
        assert synthesis_started.wait(timeout=1)
        assert memory.stop_active_speak() == first_id
        second_request = memory.requests.get_nowait()
        memory.requests.task_done()
        memory.set_speak_status(second_id, "WORKING")
        second_session = memory.begin_message_session(second_request)
        assert second_session is not None
        release_synthesis.set()
        producer.join(timeout=1)

    assert producer.is_alive() is False
    assert memory.active_session is second_session
    assert memory.messages == []
    assert memory.progressive_audio == {}
    assert first_session.tts.batches.empty()
    assert next(item for item in memory.speaks if item["id"] == first_id)["status"] == "CANCELLED"


def test_progressive_producer_clears_processing_before_audio_playback_finishes() -> None:
    """Rendered segments stop processing chrome while their queued audio remains playable."""
    from brain.infrastructure.voice.daemon import daemon

    memory = VoiceMemory()
    speak_id = memory.enqueue("Segmento audible", "es")
    assert speak_id is not None
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    session = memory.begin_message_session(request)
    assert session is not None and session.tts is not None
    memory.begin_processing(speak_id, "focused")

    with (
        patch.object(daemon, "MEMORY", memory),
        patch.object(daemon, "synthesize_or_reuse", return_value=b"audio-rendered"),
    ):
        daemon._produce_tts_batches(session)

    assert memory.status()["processing"] is False
    assert session.tts.producer_done.is_set()
    assert session.tts.batches.qsize() == 1


def test_cancel_processing_clears_progressive_audio_after_first_chunk() -> None:
    memory = VoiceMemory()
    speak_id = memory.enqueue("x" * 2200, "es")
    assert speak_id is not None
    memory.begin_processing(speak_id)
    memory.retain_progressive_audio(speak_id, 0, b"partial")
    assert memory.cancel_processing() == 1
    assert memory.progressive_audio == {}
    speak = next(item for item in memory.speaks if item["id"] == speak_id)
    assert speak["status"] == "CANCELLED"


def test_manual_file_narration_reuses_existing_logical_identity() -> None:
    memory = VoiceMemory()
    file_id = memory.enqueue(
        "Plan narrable",
        "es",
        display_text="## Plan",
        has_embedded_file=True,
        manual_speech=True,
    )
    assert file_id is not None
    original_request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(file_id, "DONE")
    memory.active_speak_id = file_id
    before_ids = [item["id"] for item in memory.speaks]

    narration_id = memory.enqueue_active_file_narration()

    assert narration_id == file_id
    assert [item["id"] for item in memory.speaks] == before_ids
    assert len(memory.speaks) == 1
    narration_request = memory.requests.get_nowait()
    assert narration_request["id"] == file_id
    assert narration_request["text"] == original_request["text"]
    assert narration_request["hasEmbeddedFile"] is True
    assert narration_request["manualSpeech"] is False
    assert memory.speaks[0]["manualSpeech"] is True
    assert memory.speaks[0]["status"] == "QUEUED"
