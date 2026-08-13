# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Voice client, configuration, and service adapter contracts.

Tests synchronous and asynchronous speak dispatch, input validation, repeat-last
dialogue operations, and voice catalog inspection routing.
"""

from argparse import Namespace
from io import StringIO
import tempfile
from pathlib import Path
from unittest.mock import Mock, call, patch
from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.daemon.daemon import VoiceMemory, semantic_speech_chunks
from brain.infrastructure.voice.daemon.daemon_client import VOICE_DAEMON_STARTUP_TIMEOUT_SECONDS, VoiceDaemonClient, consumer_repository_path
from brain.infrastructure.avatar.configuration.avatar_config import load_avatar_config, resolve_voice_daemon_endpoint
from brain.infrastructure.avatar.configuration.avatar_config_dtos import AvatarConfigDTO
from brain.infrastructure.voice.service.voice_service import VoiceService
from brain.infrastructure.voice.daemon.process_lease import core_process_lease_name, core_runtime_id


def test_daemon_cold_start_allows_slow_windows_process_initialization() -> None:
    """Keep polling readiness beyond the former three-second false timeout."""
    assert VOICE_DAEMON_STARTUP_TIMEOUT_SECONDS >= 10.0


def test_avatar_config_uses_renamed_storage_and_schema() -> None:
    """Load only the core-owned avatar config and voice-engine keys."""
    with tempfile.TemporaryDirectory() as directory:
        config_path = Path(directory) / "core" / "configs" / "brain_avatar_config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            '{"active_voice_engine":"edge","voice_engines":{"edge":{"voices":{"es":"voice"}}}}',
            encoding="utf-8",
        )
        with patch("brain.infrastructure.avatar.configuration.avatar_config.get_avatar_config_path", return_value=config_path):
            config = load_avatar_config()
    assert config.active_voice_engine == "edge"
    assert config.voice_engines.edge.voices["es"] == "voice"
    assert not hasattr(config, "active_engine")
    assert not hasattr(config, "engines")


def test_avatar_service_endpoint_is_read_from_core_config() -> None:
    """Allow separate cores to bind independent loopback daemon ports."""
    config = AvatarConfigDTO.model_validate({"service": {"host": "127.0.0.1", "port": 19133}})

    assert resolve_voice_daemon_endpoint(config) == (
        "127.0.0.1",
        19133,
    )


def test_voice_process_identity_is_scoped_to_physical_core() -> None:
    """Two cores must not share daemon or avatar-window singleton leases."""
    first = Path("D:/agents/@First/core")
    second = Path("D:/agents/@Second/core")
    assert core_runtime_id(first) != core_runtime_id(second)
    assert core_process_lease_name("voice-daemon", first) != core_process_lease_name("voice-daemon", second)
    assert core_process_lease_name("voice-daemon", first) != core_process_lease_name("voice-avatar-window", first)


def test_windows_daemon_cold_start_uses_detached_standard_user_process() -> None:
    """Windows lazy startup must detach without requesting administrator rights."""
    import inspect
    from brain.infrastructure.voice.daemon.daemon_client import VoiceDaemonClient

    source = inspect.getsource(VoiceDaemonClient._ensure_daemon)
    assert "DETACHED_PROCESS" in source
    assert "CREATE_NEW_PROCESS_GROUP" in source
    assert '"runas"' not in source
    assert "ShellExecuteW" not in source


def test_codex_sandbox_refuses_to_spawn_an_invisible_avatar() -> None:
    """Require the interactive user to own GUI startup instead of a sandbox desktop."""
    client = VoiceDaemonClient()
    with (
        patch.object(client, "_is_healthy", return_value=False),
        patch("brain.infrastructure.voice.daemon.daemon_client.sys.platform", "win32"),
        patch.dict("os.environ", {"USERNAME": "CodexSandboxOnline"}, clear=False),
        patch("brain.infrastructure.voice.daemon.daemon_client.subprocess.Popen") as popen,
    ):
        try:
            client._ensure_daemon()
        except RuntimeError as exc:
            assert "invisible GUI" in str(exc)
        else:
            raise AssertionError("Codex sandbox startup must be rejected")

    popen.assert_not_called()


def test_explicit_daemon_start_is_idempotent_and_returns_status() -> None:
    """The explicit command must reuse the lazy lifecycle contract."""
    client = VoiceDaemonClient()
    with (
        patch.object(client, "_ensure_daemon") as ensure,
        patch.object(client, "_request_json", return_value={"ok": True, "daemonPid": 42}) as request,
    ):
        snapshot = client.start()

    ensure.assert_called_once_with()
    assert request.call_args_list == [
        call(path="/theme", method="POST", payload={"mode": "light"}),
        call(path="/status"),
    ]
    assert snapshot["daemonPid"] == 42


def test_explicit_daemon_start_propagates_dark_theme() -> None:
    client = VoiceDaemonClient()
    with (
        patch.object(client, "_ensure_daemon"),
        patch.object(client, "_request_json", return_value={"ok": True}) as request,
    ):
        client.start(mode="dark")
    assert request.call_args_list[0] == call(path="/theme", method="POST", payload={"mode": "dark"})


def test_avatar_service_defaults_to_dark_and_preserves_explicit_light(monkeypatch) -> None:
    """Keep the CLI default and runtime default aligned on dark theme.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate omitted and explicit theme behavior.
    """

    monkeypatch.setenv("WORKSPACE_ROOT", str(Path.cwd()))

    from brain.presentation.commands.registry import COMMAND_MODULES
    from brain.presentation.parser.services.argument_parser_service import build_argument_parser

    parser = build_argument_parser(COMMAND_MODULES)
    assert parser.parse_args(["start-avatar-service"]).mode == "dark"
    assert parser.parse_args(["start-avatar-service", "--mode", "light"]).mode == "light"

    memory = VoiceMemory()
    assert memory.status()["themeMode"] == "dark"
    assert memory.set_theme_mode("light") == "light"
    assert memory.status()["themeMode"] == "light"

    try:
        VoiceDaemonClient().start(mode="sepia")
    except ValueError:
        pass
    else:
        raise AssertionError("Unsupported themes must be rejected before startup.")


def test_voice_memory_exposes_validated_theme_in_status() -> None:
    memory = VoiceMemory()
    assert memory.set_theme_mode("dark") == "dark"
    assert memory.status()["themeMode"] == "dark"
    try:
        memory.set_theme_mode("sepia")
    except ValueError:
        pass
    else:
        raise AssertionError("Unsupported themes must be rejected")


def test_avatar_message_accepts_one_stdin_json_envelope() -> None:
    """Keep the executable command constant while message data travels over stdin."""
    from brain.presentation.actions.general.command_speak import handle

    args = Namespace(
        text=None,
        body=None,
        lang="es",
        emotion="",
        codex_thread_id="",
        stdin_json=True,
        color=False,
        json=False,
        no_speak=False,
    )
    envelope = '{"text":"Hola desde stdin","lang":"es","emotion":"happy","codex_thread_id":"thread-1"}\n'
    with (
        patch("sys.stdin", StringIO(envelope)),
        patch("brain.presentation.actions.general.command_speak.VoiceService.speak") as speak,
    ):
        assert handle(args) == 0

    speak.assert_called_once_with(
        text="Hola desde stdin",
        lang="es",
        emotion="happy",
        codex_thread_id="thread-1",
    )
    assert args.json_payload == {
        "ok": True,
        "command": "speak",
        "state": "SPEAKED",
        "instruction": "continue",
    }


def test_daemon_client_attaches_nearest_consumer_repository() -> None:
    with tempfile.TemporaryDirectory() as directory:
        repository = Path(directory) / "consumer"
        nested = repository / "src" / "feature"
        nested.mkdir(parents=True)
        (repository / ".git").mkdir()
        assert consumer_repository_path(nested) == str(repository.resolve())

        client = VoiceDaemonClient()
        with (
            patch.object(client, "_ensure_daemon"),
            patch.object(client, "_request_json", return_value={"ok": True}) as request,
        ):
            client.speak(AvatarSpeakRequest(text="Mensaje", consumer_path=str(repository)))
        payload = request.call_args.kwargs["payload"]
        assert payload["consumerPath"] == str(repository)


def test_voice_processes_acquire_kernel_singleton_leases_before_ui_or_server() -> None:
    """Daemon and avatar entrypoints must reject concurrent duplicate processes."""
    import inspect
    from brain.infrastructure.voice.daemon import daemon
    from brain.presentation.avatar.window import main as avatar_main

    daemon_source = inspect.getsource(daemon.main)
    avatar_source = inspect.getsource(avatar_main)
    assert 'ProcessLease(core_process_lease_name("voice-daemon"))' in daemon_source
    assert daemon_source.index("process_lease.acquire()") < daemon_source.index("ThreadingHTTPServer")
    assert 'ProcessLease(core_process_lease_name("voice-avatar-window"))' in avatar_source
    assert "BRAIN_VOICE_DAEMON_INSTANCE_ID" in avatar_source


def test_avatar_supervisor_binds_child_to_its_daemon_instance() -> None:
    """A replacement window must reject status from every other daemon lifetime."""
    from brain.infrastructure.avatar.process.avatar_process import AvatarProcessSupervisor

    entrypoint = Path("avatar-main.py")
    supervisor = AvatarProcessSupervisor(entrypoint, "daemon-instance-one")
    process = Mock(pid=321)
    process.poll.return_value = None
    with patch("brain.infrastructure.avatar.process.avatar_process.subprocess.Popen", return_value=process) as popen:
        assert supervisor.ensure_running() == 321

    environment = popen.call_args.kwargs["env"]
    assert environment["BRAIN_VOICE_DAEMON_INSTANCE_ID"] == "daemon-instance-one"


def test_avatar_supervisor_replaces_an_exited_window_once() -> None:
    """The healthy voice daemon relaunches an exited avatar without duplicates."""
    from brain.infrastructure.avatar.process.avatar_process import AvatarProcessSupervisor

    first = Mock(pid=111)
    first.poll.return_value = 1
    second = Mock(pid=222)
    second.poll.return_value = None
    supervisor = AvatarProcessSupervisor(Path("avatar-main.py"), "daemon-one")
    supervisor._process = first
    with patch("brain.infrastructure.avatar.process.avatar_process.subprocess.Popen", return_value=second) as popen:
        assert supervisor.ensure_running() == 222
        assert supervisor.ensure_running() == 222
    popen.assert_called_once()


def test_speak_delegates_to_worker_without_synthesizing() -> None:
    """Delegate immediately to the warm daemon client."""
    service = VoiceService()

    with patch("brain.infrastructure.voice.service.voice_service.VoiceDaemonClient.speak") as speak:
        service.speak("Audible request")

    speak.assert_called_once_with(AvatarSpeakRequest(text="Audible request", display_text="Audible request"))


def test_speak_forwards_generic_emotion() -> None:
    service = VoiceService()
    with patch("brain.infrastructure.voice.service.voice_service.VoiceDaemonClient.speak") as speak:
        service.speak("Happy request", emotion="happy")
    speak.assert_called_once_with(AvatarSpeakRequest(text="Happy request", display_text="Happy request", emotion="happy"))


def test_voice_preserves_original_markdown_for_visual_presentation() -> None:
    service = VoiceService()
    original = "[Render status.] **Status ready**, operator."
    with patch("brain.infrastructure.voice.service.voice_service.VoiceDaemonClient.speak") as speak:
        service.speak(original, emotion="happy")
    speak.assert_called_once_with(
        AvatarSpeakRequest(text="Render status. Status ready, operator.", display_text=original, emotion="happy")
    )


def test_enqueue_message_persistence_skips_embedded_file_requests() -> None:
    """Do not enqueue asset presentation requests with embedded files into database persistence."""
    from unittest.mock import MagicMock
    from brain.infrastructure.voice.audio.voice_persistence import enqueue_message_persistence

    mock_memory = MagicMock()
    embedded_request = {
        "id": "speak-123",
        "createdAt": "2026-08-05T14:00:00Z",
        "text": "Header content",
        "displayText": "<!-- avatar-file:start -->...",
        "hasEmbeddedFile": True,
        "consumerPath": "d:/agents/@Example",
    }

    enqueue_message_persistence(mock_memory, embedded_request)
    mock_memory.persistence_requests.put.assert_not_called()



def test_semantic_speech_chunks_are_ordered_and_bounded() -> None:
    text = ("Primera oración con contexto. " * 150) + ("segmentosinpausas" * 100)
    chunks = semantic_speech_chunks(text, limit=2000)
    assert chunks
    assert all(0 < len(chunk) <= 2000 for chunk in chunks)
    assert "".join(chunks).replace(" ", "").replace("\n", "") == text.strip().replace(" ", "").replace("\n", "")


def test_semantic_speech_chunks_preserve_sentence_and_paragraph_boundaries() -> None:
    sentence1 = "Esta es la primera oración completa de prueba."
    sentence2 = "Esta es la segunda oración con bastante contexto descriptivo."
    paragraph = f"{sentence1} {sentence2}\n\n"
    long_text = paragraph * 30

    chunks = semantic_speech_chunks(long_text, limit=300)
    assert chunks
    for chunk in chunks:
        assert len(chunk) <= 300
        # Ensure chunk ends at sentence or paragraph boundary (period, exclamation, question mark, or newline)
        assert chunk[-1] in {".", "!", "?", "\n"}


def test_avatar_config_loads_tts_chunks_size_with_fallback() -> None:
    config = load_avatar_config()
    assert hasattr(config, "tts_chunks_size")
    assert config.tts_chunks_size >= 1000
