# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

'Voice playback process, timing, callback, and session contracts.'

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch
from brain.infrastructure.voice.daemon.daemon import VoiceMemory
from brain.infrastructure.voice.audio.engines import play_audio_file, play_audio_url


def test_playback_prelude_exposes_animation_without_claiming_audio_started() -> None:
    memory = VoiceMemory()
    memory.prepare_playback("Reacción", "reacting")

    assert memory.begin_playback_prelude() is True
    assert memory.status()["state"] == "preparing"
    assert memory.status()["emotion"] == "reacting"
    assert memory.has_pending_playback() is True
    memory.mark_playback_started()
    assert memory.status()["state"] == "speaking"


def test_active_playback_exposes_remaining_visual_duration() -> None:
    """The status countdown follows the active audio duration for the Qt footer."""
    memory = VoiceMemory()
    memory.prepare_playback("Mensaje", "happy", speak_id="speak-one")
    memory.set_playback_duration(65_000)
    memory.mark_playback_started()

    snapshot = memory.status()

    assert snapshot["state"] == "speaking"
    assert 64 <= snapshot["visualRemainingSeconds"] <= 65


def test_playback_process_supports_terminal_cancellation_only() -> None:
    from brain.infrastructure.voice.audio.engines import PlaybackProcess

    process = Mock()
    process.poll.return_value = None
    playback = PlaybackProcess(process)

    playback.terminate()

    process.terminate.assert_called_once()
    assert playback.process is process


def test_completed_playback_process_termination_is_idempotent() -> None:
    from brain.infrastructure.voice.audio.engines import PlaybackProcess

    process = Mock()
    process.poll.return_value = 0
    playback = PlaybackProcess(process)

    playback.terminate()

    process.terminate.assert_not_called()


def test_url_player_signals_prelude_then_waits_before_audio() -> None:
    with patch("brain.infrastructure.voice.audio.engines.subprocess.Popen") as popen:
        play_audio_url(
            "http://127.0.0.1/audio",
            "http://127.0.0.1/playback-started",
            "http://127.0.0.1/playback-preparing",
            1,
        )

    command = popen.call_args.args[0][-1]
    preparing_index = command.index("playback-preparing")
    prelude_index = command.index("$preludeTicks = 0")
    started_index = command.index("playback-started")
    play_index = command.index("$m.Play()")
    load_index = command.index("$loadTicks = 0")
    assert preparing_index < prelude_index < play_index < started_index < load_index
    assert "ReadLineAsync" not in command
    assert popen.call_args.kwargs["stdin"] == subprocess.DEVNULL
    assert "$i -ge 600" not in command
    assert "$duration.TotalSeconds + 30" in command
    assert "Start-Sleep -Milliseconds 2000; $m.Close()" in command


def test_file_player_has_no_fixed_sixty_second_cutoff() -> None:
    with (
        patch("brain.infrastructure.voice.audio.engines.sys.platform", "win32"),
        patch("brain.infrastructure.voice.audio.engines.subprocess.Popen") as popen,
    ):
        play_audio_file(Path("long-voice.mp3"))

    command = popen.call_args.args[0][-1]
    assert "$i -ge 600" not in command
    assert "$duration.TotalSeconds + 30" in command
    assert "Start-Sleep -Milliseconds 2000; $m.Close()" in command
    assert "$m.Close()" in command


def test_url_player_reports_natural_duration_after_media_starts() -> None:
    with patch("brain.infrastructure.voice.audio.engines.subprocess.Popen") as popen:
        play_audio_url(
            "http://127.0.0.1/audio",
            "http://127.0.0.1/playback-started",
            duration_callback_url="http://127.0.0.1/playback-duration",
        )

    command = popen.call_args.args[0][-1]
    assert "NaturalDuration.TimeSpan" in command
    assert "playback-duration" in command
    assert "$duration.TotalMilliseconds + 2000" in command
    play_index = command.index("$m.Play()")
    assert play_index < command.index("playback-started")
    assert play_index < command.index("$loadTicks = 0") < command.index("playback-duration")


def test_url_playback_callbacks_carry_session_identity_and_follow_media_start() -> None:
    with patch("brain.infrastructure.voice.audio.engines.subprocess.Popen") as popen:
        play_audio_url(
            "http://127.0.0.1/audio",
            "http://127.0.0.1/playback-started",
            "http://127.0.0.1/playback-preparing",
            1,
            "http://127.0.0.1/playback-duration",
            speak_id="speak-owned",
            generation=7,
        )

    command = popen.call_args.args[0][-1]
    assert command.count('"speakId":"speak-owned"') == 3
    assert command.count('"generation":7') == 3
    assert command.index("$m.Play()") < command.index("playback-started")
    assert '"milliseconds":' in command


def test_stale_playback_callbacks_cannot_mutate_replacement_session() -> None:
    memory = VoiceMemory()
    first_id = memory.enqueue("Primero", "es")
    first_request = memory.requests.get_nowait()
    memory.requests.task_done()
    first = memory.begin_message_session(first_request)
    assert first is not None and first_id
    memory.prepare_playback("Primero", "happy", speak_id=first_id)
    first_generation = first.generation
    memory.close_message_session(first, "DONE")

    second_id = memory.enqueue("Segundo", "es")
    second_request = memory.requests.get_nowait()
    memory.requests.task_done()
    second = memory.begin_message_session(second_request)
    assert second is not None and second_id
    memory.prepare_playback("Segundo", "focused", speak_id=second_id)

    assert memory.mark_playback_started_for(first_id, first_generation) is False
    assert memory.set_playback_duration_for(first_id, first_generation, 90_000) is False
    snapshot = memory.status()
    assert snapshot["state"] == "preparing"
    assert snapshot["activeSpeakId"] == second_id
    assert snapshot["visualRemainingSeconds"] == 0


def test_url_natural_callbacks_drive_timing_and_process_completion_closes_session() -> None:
    from brain.infrastructure.voice.daemon import daemon

    memory = VoiceMemory()
    speak_id = memory.enqueue("Mensaje cuya estimación no manda", "es", emotion="happy")
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    player = Mock()
    player.wait.return_value = 0
    observed: dict[str, object] = {}

    def start_url(_url: str, **kwargs: object) -> Mock:
        observed.update(kwargs)
        assert memory.status()["state"] == "preparing"
        assert memory.status()["visualRemainingSeconds"] == 0
        assert memory.begin_playback_prelude_for(
            str(kwargs["speak_id"]), int(kwargs["generation"])
        ) is True
        assert memory.mark_playback_started_for(
            str(kwargs["speak_id"]), int(kwargs["generation"])
        ) is True
        assert memory.set_playback_duration_for(
            str(kwargs["speak_id"]), int(kwargs["generation"]), 42_000
        ) is True
        active = memory.status()
        assert active["state"] == "speaking"
        assert 41 <= active["visualRemainingSeconds"] <= 42
        return player

    with (
        patch.object(daemon, "MEMORY", memory),
        patch.object(daemon, "synthesize_or_reuse", return_value=b"audio"),
        patch.object(daemon, "play_audio_url", side_effect=start_url),
    ):
        daemon.process_message_request(request)

    assert observed["started_callback_url"] == f"{daemon.VOICE_DAEMON_URL}/playback-started"
    assert observed["preparing_callback_url"] == f"{daemon.VOICE_DAEMON_URL}/playback-preparing"
    assert observed["duration_callback_url"] == f"{daemon.VOICE_DAEMON_URL}/playback-duration"
    assert observed["speak_id"] == speak_id
    snapshot = memory.status()
    assert snapshot["state"] == "awaiting"
    assert snapshot["text"] == ""
    assert snapshot["displayText"] == ""
    assert snapshot["activeSpeakId"] == ""
    assert snapshot["visualRemainingSeconds"] == 0


def test_muted_active_session_owns_bubble_without_creating_tts_batches() -> None:
    """Mute is decided once by the message session and suppresses TTS ownership."""
    memory = VoiceMemory()
    memory.toggle_muted()
    memory.toggle_muted()
    speak_id = memory.enqueue("Mensaje silenciado", "es")
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(speak_id or "", "WORKING")

    session = memory.begin_message_session(request)

    assert session is not None
    assert session.muted is True
    assert session.tts is None
    assert memory.status()["activeSpeakId"] == speak_id
    assert memory.status()["state"] == "muted_replay"
    assert memory.status()["queueDepth"] == 0
