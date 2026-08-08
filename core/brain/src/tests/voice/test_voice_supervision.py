# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

'Voice avatar-process supervision contracts.'

import threading
import time
from unittest.mock import Mock, patch
from brain.infrastructure.voice.daemon.daemon import VoiceMemory


def test_supervision_live_child_preserves_pid_lease_and_active_session() -> None:
    from brain.infrastructure.voice.daemon import daemon

    memory = VoiceMemory()
    memory.prepare_for_window_spawn()
    supervisor = Mock()
    supervisor.pid = 321
    memory.bind_window_supervisor(supervisor)
    memory.register_window_process(321)
    assert memory.mark_window_ready(321) is True
    speak_id = memory.enqueue("Activo", "es")
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(speak_id or "", "WORKING")
    lease = memory.wait_for_window(request)
    session = memory.begin_message_session(request, lease)

    with patch.object(daemon, "MEMORY", memory):
        assert daemon.supervise_avatar_window(supervisor) == 321

    assert memory.window_lease_is_current(lease)
    assert memory.active_session is session
    assert memory.window_pids == [321]
    supervisor.ensure_running.assert_not_called()


def test_supervisor_respawn_cancels_active_then_gates_next_until_new_pid_ready() -> None:
    """A replacement process cannot inherit the dead controller's lease."""
    from brain.infrastructure.voice.daemon import daemon

    memory = VoiceMemory()
    memory.prepare_for_window_spawn()
    supervisor = Mock()
    supervisor.pid = 410
    memory.bind_window_supervisor(supervisor)
    memory.register_window_process(410)
    assert memory.mark_window_ready(410)
    active_id = memory.enqueue("Controlador antiguo", "es")
    next_id = memory.enqueue("Controlador nuevo", "es")
    active_request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(active_id or "", "WORKING")
    old_lease = memory.wait_for_window(active_request)
    active_session = memory.begin_message_session(active_request, old_lease)
    assert active_session is not None and active_session.tts is not None
    old_player = Mock()
    active_session.tts.player = old_player
    memory.playback = old_player
    supervisor.pid = None

    def ensure_replacement() -> int:
        assert memory.window_ready.is_set() is False
        assert memory.active_session is None
        assert memory.active_display_text == ""
        old_player.terminate.assert_called_once_with()
        supervisor.pid = 654
        return 654

    supervisor.ensure_running.side_effect = ensure_replacement
    with patch.object(daemon, "MEMORY", memory):
        assert daemon.supervise_avatar_window(supervisor) == 654

    assert memory.window_lease_is_current(old_lease) is False
    assert memory.window_ready.is_set() is False
    next_request = memory.requests.get_nowait()
    memory.requests.task_done()
    new_player = Mock()
    new_player.wait.return_value = 0
    with (
        patch.object(daemon, "MEMORY", memory),
        patch.object(daemon, "synthesize_or_reuse", return_value=b"new-audio") as synthesize,
        patch.object(daemon, "play_audio_url", return_value=new_player),
    ):
        worker = threading.Thread(target=daemon.process_message_request, args=(next_request,))
        worker.start()
        deadline = time.monotonic() + 1
        while memory.awaiting_window_speak_id != next_id and time.monotonic() < deadline:
            time.sleep(0.001)
        assert memory.awaiting_window_speak_id == next_id
        synthesize.assert_not_called()
        assert memory.mark_window_ready(654)
        worker.join(timeout=1)

    assert worker.is_alive() is False
    synthesize.assert_called_once()
    assert memory.messages[0]["speakId"] == next_id


def test_supervision_thread_detects_death_without_http_request_progress() -> None:
    from brain.infrastructure.voice.daemon import daemon

    memory = VoiceMemory()
    memory.prepare_for_window_spawn()
    supervisor = Mock()
    supervisor.pid = 801
    memory.bind_window_supervisor(supervisor)
    memory.register_window_process(801)
    assert memory.mark_window_ready(801)
    supervisor.pid = None
    supervisor.ensure_running.side_effect = lambda: setattr(supervisor, "pid", 802) or 802
    stop_event = threading.Event()
    with patch.object(daemon, "MEMORY", memory):
        worker = threading.Thread(
            target=daemon.run_avatar_supervision,
            args=(supervisor, stop_event, 0.01),
        )
        worker.start()
        deadline = time.monotonic() + 1
        while memory.current_window_pid != 802 and time.monotonic() < deadline:
            time.sleep(0.001)
        stop_event.set()
        worker.join(timeout=1)

    assert worker.is_alive() is False
    assert memory.current_window_pid == 802
    assert memory.window_ready.is_set() is False


def test_supervision_thread_recovers_after_one_spawn_failure() -> None:
    """A transient ensure failure invalidates leases but cannot kill polling."""
    from brain.infrastructure.voice.daemon import daemon

    class RecoveringSupervisor:
        def __init__(self) -> None:
            self.current_pid: int | None = None
            self.ensure_calls = 0

        @property
        def pid(self) -> int | None:
            return self.current_pid

        def ensure_running(self) -> int:
            self.ensure_calls += 1
            if self.ensure_calls == 1:
                raise RuntimeError("spawn failed once")
            self.current_pid = 902
            return self.current_pid

    memory = VoiceMemory()
    memory.prepare_for_window_spawn()
    supervisor = RecoveringSupervisor()
    memory.bind_window_supervisor(supervisor)  # type: ignore[arg-type]
    stop_event = threading.Event()
    with patch.object(daemon, "MEMORY", memory):
        worker = threading.Thread(
            target=daemon.run_avatar_supervision,
            args=(supervisor, stop_event, 0.01),  # type: ignore[arg-type]
        )
        worker.start()
        deadline = time.monotonic() + 1
        while memory.current_window_pid != 902 and time.monotonic() < deadline:
            time.sleep(0.001)
        assert worker.is_alive()
        stop_event.set()
        worker.join(timeout=1)

    assert worker.is_alive() is False
    assert supervisor.ensure_calls == 2
    assert memory.current_window_pid == 902
    assert memory.window_ready.is_set() is False
    assert memory.supervision_errors == ["spawn failed once"]
