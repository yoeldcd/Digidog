# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

'Voice logical queue and progressive-audio contracts.'

from brain.infrastructure.voice.daemon.daemon import VoiceMemory


def test_manual_file_display_is_stable_and_does_not_enter_playback_state() -> None:
    memory = VoiceMemory()
    request = {
        "id": "speak-file",
        "text": "Plan narrable",
        "displayText": "## Plan",
        "emotion": "focused",
    }
    memory.show_manual_file(request)
    assert memory.state == memory.ambient_state
    assert memory.active_speak_id == "speak-file"
    assert memory.pending_playback is None
    assert memory.playback is None
    next_id = memory.enqueue("Mensaje siguiente", "es")
    assert next_id is not None
    assert memory.requests.qsize() == 1


def test_progressive_audio_chunks_keep_one_logical_message() -> None:
    memory = VoiceMemory()
    speak_id = memory.enqueue("x" * 2200, "es")
    assert speak_id is not None
    first = memory.retain_progressive_audio(speak_id, 0, b"a")
    second = memory.retain_progressive_audio(speak_id, 1, b"b")
    assert len(memory.messages) == 0
    assert memory.find_audio(first["name"]) == b"a"
    assert memory.find_audio(second["name"]) == b"b"
    memory.store(b"ab", speak_id=speak_id, text="x" * 2200)
    assert len(memory.speaks) == 1
    assert len(memory.messages) == 1
    assert memory.messages[0]["speakId"] == speak_id
    memory.store(b"replacement", speak_id=speak_id, text="x" * 2200)
    assert len(memory.messages) == 1
    assert memory.messages[0]["audio"] == b"replacement"


def test_internal_progressive_artifacts_do_not_change_public_counts() -> None:
    memory = VoiceMemory()
    speak_id = memory.enqueue("Texto progresivo " * 200, "es")
    assert speak_id is not None
    before = memory.snapshot()
    before_status = memory.status()
    memory.mark_progressive_speak(speak_id, 3)
    memory.retain_progressive_audio(speak_id, 0, b"one")
    memory.retain_progressive_audio(speak_id, 1, b"two")
    after = memory.snapshot()
    after_status = memory.status()
    assert [item["id"] for item in after["speaks"]] == [item["id"] for item in before["speaks"]]
    assert after["messages"] == before["messages"] == []
    assert after_status["historyCount"] == before_status["historyCount"] == 1
    assert after_status["queueDepth"] == before_status["queueDepth"] == 1


def test_stop_current_message_closes_active_then_releases_next_fifo_message() -> None:
    """The next logical session starts only after active ownership is released."""
    memory = VoiceMemory()
    active_id = memory.enqueue("Activo", "es")
    next_id = memory.enqueue("Siguiente", "es")
    assert active_id and next_id
    active_request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(active_id, "WORKING")
    active_session = memory.begin_message_session(active_request)
    assert active_session is not None and active_session.tts is not None
    memory.mark_progressive_speak(active_id, 2)
    memory.retain_progressive_audio(active_id, 1, b"prepared")
    assert memory.status()["queueDepth"] == 1

    stopped_id = memory.stop_active_speak()
    next_request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(next_id, "WORKING")
    next_session = memory.begin_message_session(next_request)

    assert stopped_id == active_id
    assert active_session.cancelled.is_set()
    assert next_session is not None and memory.active_session is next_session
    assert memory.active_speak_id == next_id
    assert memory.progressive_audio == {}
    assert next(item for item in memory.speaks if item["id"] == active_id)["status"] == "CANCELLED"


def test_stop_muted_message_unblocks_presentation_and_rejects_late_chunks() -> None:
    memory = VoiceMemory()
    speak_id = memory.enqueue("Activo silenciado", "es")
    assert speak_id is not None
    memory.active_speak_id = speak_id
    memory.state = "speaking"
    memory.mute_mode = "total"
    memory.muted = True
    memory.mark_progressive_speak(speak_id, 2)
    memory.retain_progressive_audio(speak_id, 1, b"late")

    assert memory.stop_active_speak() == speak_id

    assert memory.presentation_cancel_event.is_set()
    assert memory.is_speak_terminal(speak_id)
    assert memory.progressive_audio == {}
    assert memory.active_speak_id == ""
    assert memory.state == memory.ambient_state
