# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

'Voice window readiness and active-session lease contracts.'

import json
import threading
from io import BytesIO
import time
from unittest.mock import Mock, patch
from brain.infrastructure.voice.daemon.daemon import VoiceDaemonHandler, VoiceMemory


def test_daemon_supervisor_and_status_share_one_instance_identity() -> None:
    """The Qt child lease and daemon status must identify the same lifetime."""
    from brain.infrastructure.voice.daemon import daemon

    assert daemon.DAEMON_INSTANCE_ID == daemon.MEMORY.status()["instanceId"]


def test_window_readiness_defaults_open_and_main_owns_supervisor_thread() -> None:
    """Unit memories stay fast while real main gates and joins supervision."""
    import inspect
    from brain.infrastructure.voice.daemon import daemon

    assert VoiceMemory().window_ready.is_set()
    source = inspect.getsource(daemon.main)
    assert source.index("MEMORY.prepare_for_window_spawn()") < source.index("AvatarProcessSupervisor(")
    assert "target=run_avatar_supervision" in source
    assert "supervisor_stop.set()" in source
    assert "supervisor_thread.join" in source


def test_window_ready_endpoint_rejects_stale_pid_and_accepts_live_pid_idempotently() -> None:
    from brain.infrastructure.voice.daemon import daemon

    memory = VoiceMemory()
    memory.prepare_for_window_spawn()
    supervisor = Mock()
    supervisor.pid = 222
    memory.bind_window_supervisor(supervisor)
    memory.register_window_process(222)
    handler = object.__new__(VoiceDaemonHandler)
    handler.path = "/window-ready"
    handler._send_json = Mock()

    stale_body = json.dumps({"pid": 111}).encode("utf-8")
    handler.headers = {"Content-Length": str(len(stale_body))}
    handler.rfile = BytesIO(stale_body)
    with patch.object(daemon, "MEMORY", memory):
        handler.do_POST()
    assert handler._send_json.call_args.kwargs["status"].value == 409
    assert memory.window_ready.is_set() is False

    live_body = json.dumps({"pid": 222}).encode("utf-8")
    handler.headers = {"Content-Length": str(len(live_body))}
    handler.rfile = BytesIO(live_body)
    with patch.object(daemon, "MEMORY", memory):
        handler.do_POST()
        handler.rfile = BytesIO(live_body)
        handler.do_POST()
    assert handler._send_json.call_args.kwargs["status"].value == 200
    assert memory.ready_window_pid == 222
    assert memory.window_ready.is_set()


def test_death_between_ready_wait_and_activation_retries_same_id_on_new_lease() -> None:
    """One invocation retains its FIFO identity across a stale claim lease."""
    from brain.infrastructure.voice.daemon import daemon

    memory = VoiceMemory()
    memory.prepare_for_window_spawn()
    supervisor = Mock()
    supervisor.pid = 501
    memory.bind_window_supervisor(supervisor)
    memory.register_window_process(501)
    assert memory.mark_window_ready(501)
    speak_id = memory.enqueue("Mismo mensaje", "es")
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    first_claim_entered = threading.Event()
    release_stale_claim = threading.Event()
    original_begin_session = memory.begin_message_session
    claim_count = 0

    def begin_session_after_controlled_race(
        candidate: dict[str, object],
        lease: object,
    ) -> object:
        nonlocal claim_count
        claim_count += 1
        if claim_count == 1:
            first_claim_entered.set()
            assert release_stale_claim.wait(timeout=1)
        return original_begin_session(candidate, lease)  # type: ignore[arg-type]

    player = Mock()
    player.wait.return_value = 0
    with (
        patch.object(daemon, "MEMORY", memory),
        patch.object(memory, "begin_message_session", side_effect=begin_session_after_controlled_race),
        patch.object(daemon, "synthesize_or_reuse", return_value=b"audio") as synthesize,
        patch.object(daemon, "play_audio_url", return_value=player),
    ):
        worker = threading.Thread(target=daemon.process_message_request, args=(request,))
        worker.start()
        assert first_claim_entered.wait(timeout=1)
        assert speak_id in memory.processing_speak_ids
        assert memory.awaiting_window_speak_id == speak_id

        supervisor.pid = None
        supervisor.ensure_running.side_effect = lambda: setattr(supervisor, "pid", 502) or 502
        assert daemon.supervise_avatar_window(supervisor) == 502
        release_stale_claim.set()

        deadline = time.monotonic() + 1
        while claim_count < 1 or memory.current_window_pid != 502:
            assert time.monotonic() < deadline
            time.sleep(0.001)
        synthesize.assert_not_called()
        retained = next(item for item in memory.speaks if item["id"] == speak_id)
        assert retained["status"] != "CANCELLED"
        assert memory.awaiting_window_speak_id == speak_id

        assert memory.mark_window_ready(502)
        worker.join(timeout=1)

    assert worker.is_alive() is False
    synthesize.assert_called_once()
    assert claim_count == 2
    assert memory.messages[0]["speakId"] == speak_id


def test_death_after_session_before_tts_cancels_generation_without_audio() -> None:
    from brain.infrastructure.voice.daemon import daemon

    memory = VoiceMemory()
    memory.prepare_for_window_spawn()
    supervisor = Mock()
    supervisor.pid = 601
    memory.bind_window_supervisor(supervisor)
    memory.register_window_process(601)
    assert memory.mark_window_ready(601)
    speak_id = memory.enqueue("No debe sonar", "es")
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    memory.set_speak_status(speak_id or "", "WORKING")
    lease = memory.wait_for_window(request)
    session = memory.begin_message_session(request, lease)
    assert session is not None
    supervisor.pid = None
    supervisor.ensure_running.side_effect = lambda: setattr(supervisor, "pid", 602) or 602
    with (
        patch.object(daemon, "MEMORY", memory),
        patch.object(daemon, "synthesize_or_reuse") as synthesize,
    ):
        daemon.supervise_avatar_window(supervisor)
        assert daemon.delegate_tts_for_session(session) is False

    synthesize.assert_not_called()
    assert session.cancelled.is_set()
    assert memory.messages == []
    assert memory.active_speak_id == ""


def test_concurrent_stale_handler_interleaving_cannot_restore_dead_pid_lease() -> None:
    """Handler validation observes death even when it began before respawn."""
    from brain.infrastructure.voice.daemon import daemon

    class InterleavingSupervisor:
        def __init__(self) -> None:
            self.current: int | None = 701
            self.block = True
            self.pid_read = threading.Event()
            self.release = threading.Event()

        @property
        def pid(self) -> int | None:
            if self.block:
                self.pid_read.set()
                self.release.wait(timeout=1)
            return self.current

        def ensure_running(self) -> int:
            self.current = 702
            return 702

    supervisor = InterleavingSupervisor()
    memory = VoiceMemory()
    memory.prepare_for_window_spawn()
    memory.bind_window_supervisor(supervisor)
    memory.register_window_process(701)
    body = json.dumps({"pid": 701}).encode("utf-8")
    handler = object.__new__(VoiceDaemonHandler)
    handler.path = "/window-ready"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler._send_json = Mock()
    with patch.object(daemon, "MEMORY", memory):
        worker = threading.Thread(target=handler.do_POST)
        worker.start()
        assert supervisor.pid_read.wait(timeout=1)
        supervisor.current = None
        supervisor.block = False
        supervisor.release.set()
        worker.join(timeout=1)
        assert handler._send_json.call_args.kwargs["status"].value == 409
        assert daemon.supervise_avatar_window(supervisor) == 702

    assert memory.window_ready.is_set() is False
    assert memory.current_window_pid == 702


def test_stop_and_daemon_stop_release_window_wait_without_tts() -> None:
    from brain.infrastructure.voice.daemon import daemon

    for daemon_stop in (False, True):
        memory = VoiceMemory()
        memory.prepare_for_window_spawn()
        speak_id = memory.enqueue("Esperando ventana", "es")
        request = memory.requests.get_nowait()
        memory.requests.task_done()
        with patch.object(daemon, "MEMORY", memory), patch.object(daemon, "synthesize_or_reuse") as synthesize:
            worker = threading.Thread(target=daemon.process_message_request, args=(request,))
            worker.start()
            deadline = time.monotonic() + 1
            while memory.awaiting_window_speak_id != speak_id and time.monotonic() < deadline:
                time.sleep(0.001)
            stopped_id = memory.request_daemon_stop() if daemon_stop else memory.stop_active_speak()
            worker.join(timeout=1)
        assert stopped_id is None if daemon_stop else stopped_id == speak_id
        assert worker.is_alive() is False
        synthesize.assert_not_called()


def test_hidden_muted_request_releases_fifo_without_visual_wait() -> None:
    """A hidden muted request completes immediately instead of reserving the FIFO."""
    from brain.infrastructure.voice.daemon import daemon
    memory = VoiceMemory()
    memory.mute_mode = "total"
    memory.muted = True
    speak_id = memory.enqueue("No mostrar", "es", hide_when_muted=True)
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    with patch.object(daemon, "MEMORY", memory):
        daemon.process_message_request(request)
    assert memory.active_session is None
    assert memory.active_speak_id == ""
    assert memory.muted_visual_deadline == 0.0
    assert next(item for item in memory.speaks if item["id"] == speak_id)["status"] == "DONE"