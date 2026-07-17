# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Unit tests for voice dispatch and asynchronous playback."""

import subprocess
from argparse import Namespace
from io import StringIO
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, call, patch

from brain.infrastructure.voice.daemon import IDLE_TTL_SECONDS, VoiceMemory
from brain.infrastructure.voice.daemon_client import (
    VOICE_DAEMON_STARTUP_TIMEOUT_SECONDS,
    VoiceDaemonClient,
    consumer_repository_path,
)
from brain.infrastructure.voice.config import load_voice_config, resolve_voice_daemon_endpoint
from brain.infrastructure.voice.catalog import VoiceCatalogService
from brain.infrastructure.voice.engines import (
    EdgeTtsEngine,
    ElevenLabsTtsEngine,
    LocalPlayback,
    OpenAiTtsEngine,
    play_audio_file,
    play_audio_url,
)
from brain.infrastructure.voice.service import VoiceService, clean_text_for_speech
from brain.infrastructure.voice.process_lease import core_process_lease_name, core_runtime_id


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
        with patch("brain.infrastructure.voice.config.get_avatar_config_path", return_value=config_path):
            config = load_voice_config()
    assert config["active_voice_engine"] == "edge"
    assert config["voice_engines"]["edge"]["voices"]["es"] == "voice"
    assert "active_engine" not in config
    assert "engines" not in config


def test_avatar_service_endpoint_is_read_from_core_config() -> None:
    """Allow separate cores to bind independent loopback daemon ports."""
    assert resolve_voice_daemon_endpoint({"service": {"host": "127.0.0.1", "port": 19133}}) == (
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
    from brain.infrastructure.voice.daemon_client import VoiceDaemonClient

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
        patch("brain.infrastructure.voice.daemon_client.sys.platform", "win32"),
        patch.dict("os.environ", {"USERNAME": "CodexSandboxOnline"}, clear=False),
        patch("brain.infrastructure.voice.daemon_client.subprocess.Popen") as popen,
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
    assert args.json_payload["characters"] == len("Hola desde stdin")

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
            client.speak("Mensaje", consumer_path=str(repository))
        payload = request.call_args.kwargs["payload"]
        assert payload["consumerPath"] == str(repository)


def test_voice_processes_acquire_kernel_singleton_leases_before_ui_or_server() -> None:
    """Daemon and avatar entrypoints must reject concurrent duplicate processes."""
    import inspect
    from brain.infrastructure.voice import daemon
    from brain.presentation.avatar.window import main as avatar_main

    daemon_source = inspect.getsource(daemon.main)
    avatar_source = inspect.getsource(avatar_main)
    assert 'ProcessLease(core_process_lease_name("voice-daemon"))' in daemon_source
    assert daemon_source.index("process_lease.acquire()") < daemon_source.index("ThreadingHTTPServer")
    assert 'ProcessLease(core_process_lease_name("voice-avatar-window"))' in avatar_source
    assert "BRAIN_VOICE_DAEMON_INSTANCE_ID" in avatar_source


def test_speak_delegates_to_worker_without_synthesizing() -> None:
    """Delegate immediately to the warm daemon client."""
    service = VoiceService()

    with patch("brain.infrastructure.voice.service.VoiceDaemonClient.speak") as speak:
        service.speak("Audible request")

    speak.assert_called_once_with(
        text="Audible request",
        display_text="Audible request",
        lang="es",
        emotion="",
        signal_key="",
        codex_thread_id="",
    )


def test_speak_forwards_generic_emotion() -> None:
    service = VoiceService()
    with patch("brain.infrastructure.voice.service.VoiceDaemonClient.speak") as speak:
        service.speak("Happy request", emotion="happy")
    speak.assert_called_once_with(
        text="Happy request",
        display_text="Happy request",
        lang="es",
        emotion="happy",
        signal_key="",
        codex_thread_id="",
    )


def test_voice_preserves_original_markdown_for_visual_presentation() -> None:
    service = VoiceService()
    original = "[Meneo la colita.] **Hola**, papi."
    with patch("brain.infrastructure.voice.service.VoiceDaemonClient.speak") as speak:
        service.speak(original, emotion="happy")
    speak.assert_called_once_with(
        text="Meneo la colita. Hola, papi.",
        display_text=original,
        lang="es",
        emotion="happy",
        signal_key="",
        codex_thread_id="",
    )


def test_speak_propagates_codex_reply_target_as_metadata() -> None:
    service = VoiceService()
    thread_id = "019f5dad-af67-7533-b394-8fb55258adb2"
    with patch("brain.infrastructure.voice.service.VoiceDaemonClient.speak") as speak:
        service.speak("Mensaje dirigido", codex_thread_id=thread_id)
    assert speak.call_args.kwargs["codex_thread_id"] == thread_id


def test_speech_cleanup_extracts_angi_dialogue_body_before_stripping_roleplay() -> None:
    dialogue = (
        "@Angi🩷.**friend** (✨) [Qué bien, Yoi. Eso refuerza bastante la hipótesis de que "
        "Lenovo Vantage estaba reteniendo el registro del usuario durante la transición de sesión.]"
    )

    cleaned = clean_text_for_speech(dialogue)

    assert cleaned.startswith("Qué bien, Yoi.")
    assert "Lenovo Vantage" in cleaned
    assert "@Angi" not in cleaned
    assert "friend" not in cleaned


def test_speech_cleanup_preserves_a_fully_bracketed_dialogue() -> None:
    dialogue = (
        "[Levanto despacito una de mis orejitas largas al escuchar tu voz. "
        "Sí, papi, tengo un poquito de sueñito.]"
    )

    assert clean_text_for_speech(dialogue) == dialogue[1:-1]


def test_speech_cleanup_narrates_inline_bracketed_narrative() -> None:
    assert clean_text_for_speech("Hola, papi. [Meneo la colita.] Estoy aquí.") == (
        "Hola, papi. Meneo la colita. Estoy aquí."
    )


def test_speech_cleanup_narrates_emphasis_instead_of_treating_it_as_an_action() -> None:
    assert clean_text_for_speech("Una **frase importante** *y expresiva*") == "Una frase importante y expresiva"


def test_speech_cleanup_narrates_inline_code_without_backticks() -> None:
    """Inline code is semantic prose even though its delimiters are visual-only."""
    assert clean_text_for_speech("Versioné `brain_avatar_config.json` sin alterar la vista.") == (
        "Versioné brain_avatar_config.json sin alterar la vista."
    )


def test_speech_cleanup_projects_semantic_markdown_and_omits_visual_only_blocks() -> None:
    message = """# Informe narrable

[Levanto una orejita.]

- Primer elemento.
- [x] Segundo elemento con [documentación](https://example.com/docs).

| Estado | Valor |
|---|---:|
| Voz | Omitir esta fila |

```python
print("No narrar")
```

![Diagrama secreto](https://example.com/image.png)

Texto con `código inline narrable` y **énfasis narrable**.
"""

    assert clean_text_for_speech(message) == (
        "Informe narrable Levanto una orejita. Primer elemento. "
        "Segundo elemento con documentación. Texto con código inline narrable y énfasis narrable."
    )


def test_voice_keeps_visual_only_markdown_in_display_text() -> None:
    service = VoiceService()
    original = "Texto narrable.\n\n| A | B |\n|---|---|\n| secreto | visual |\n\n```py\npass\n```"
    with patch("brain.infrastructure.voice.service.VoiceDaemonClient.speak") as speak:
        service.speak(original)
    speak.assert_called_once_with(
        text="Texto narrable.",
        display_text=original,
        lang="es",
        emotion="",
        signal_key="",
        codex_thread_id="",
    )


def test_free_windows_engine_uses_speech_api_without_audio_file() -> None:
    """Prepare free-engine text without starting its blocking subprocess."""
    with (
        patch("brain.infrastructure.voice.engines.sys.platform", "win32"),
        patch("brain.infrastructure.voice.engines.subprocess.Popen") as popen,
    ):
        playback = EdgeTtsEngine({}).prepare("No SSD writes", "en")

    assert isinstance(playback, LocalPlayback)
    popen.assert_not_called()


def test_local_playback_starts_only_when_requested() -> None:
    """Keep local synthesis deferred until the sequential playback worker owns it."""
    playback = LocalPlayback(command=["voice"], popen_kwargs={"stdout": subprocess.DEVNULL})
    with patch("brain.infrastructure.voice.engines.subprocess.Popen") as popen:
        playback.start()
    popen.assert_called_once_with(["voice"], stdout=subprocess.DEVNULL)


def test_openai_catalog_reports_configured_voice_and_model() -> None:
    """Expose deterministic configured catalogs when the provider has no list endpoint."""
    config = {
        "active_voice_engine": "openai",
        "voice_engines": {"openai": {"voice": "shimmer", "model": "tts-1", "voices": {"es": "shimmer"}}},
    }
    with patch("brain.infrastructure.voice.catalog.load_voice_config", return_value=config):
        catalog = VoiceCatalogService().list_catalog(engine_name="openai")
    assert catalog["engine"] == "openai"
    assert catalog["active"] is True
    assert catalog["voices"][0]["id"] == "shimmer"
    assert catalog["voiceMap"] == {"es": "shimmer"}
    assert catalog["models"][0]["id"] == "tts-1"


def test_edge_neural_synthesis_returns_memory_audio_without_local_blocking() -> None:
    """Use the configured online Edge voice while keeping audio in daemon memory."""
    from brain.infrastructure.voice import daemon

    config = {"active_voice_engine": "edge", "voice_engines": {"edge": {"voices": {"es": "es-CO-Salome"}}}}
    with (
        patch.object(daemon, "load_voice_config", return_value=config),
        patch.object(
            daemon,
            "_synthesize_edge_audio",
            new_callable=AsyncMock,
            return_value=b"edge-audio",
        ) as synthesize,
    ):
        result = daemon.synthesize({"text": "Hola", "lang": "es"})
    assert result == b"edge-audio"
    assert synthesize.call_args.kwargs["voice"] == "es-CO-SalomeNeural"
    assert synthesize.call_args.kwargs["rate"] == "+0%"
    assert synthesize.call_args.kwargs["volume"] == "+0%"
    assert synthesize.call_args.kwargs["pitch"] == "+0Hz"


def test_edge_synthesis_applies_configured_regex_only_to_spoken_text() -> None:
    """Engine sanitization removes noisy symbols before provider synthesis."""
    from brain.infrastructure.voice import daemon

    config = {
        "active_voice_engine": "edge",
        "voice_engines": {
            "edge": {
                "sanitization_regex": "_+",
                "voices": {"es": "es-CO-Salome"},
            }
        },
    }
    with (
        patch.object(daemon, "load_voice_config", return_value=config),
        patch.object(daemon, "_synthesize_edge_audio", new_callable=AsyncMock, return_value=b"audio") as synthesize,
    ):
        daemon.synthesize({"text": "brain_avatar__config.json", "lang": "es"})

    assert synthesize.call_args.kwargs["text"] == "brain avatar config.json"


def test_invalid_engine_sanitization_regex_preserves_spoken_text() -> None:
    """A malformed optional pattern must not break avatar delivery."""
    from brain.infrastructure.voice.daemon import sanitize_engine_text

    assert sanitize_engine_text("brain_config", {"sanitization_regex": "["}) == "brain_config"


def test_paid_engines_reject_direct_disk_backed_synthesis() -> None:
    """Force all paid synthesis through the RAM-only daemon boundary."""
    for engine in (OpenAiTtsEngine({}), ElevenLabsTtsEngine({})):
        try:
            engine.speak("Protected SSD", "es")
        except RuntimeError as exc:
            assert "memory-only voice daemon" in str(exc)
        else:
            raise AssertionError("Direct paid synthesis unexpectedly succeeded.")


def test_windows_playback_uses_hidden_sta_process() -> None:
    """Launch MediaPlayer asynchronously without detaching it from the audio session."""
    with (
        patch("brain.infrastructure.voice.engines.sys.platform", "win32"),
        patch("brain.infrastructure.voice.engines.subprocess.Popen") as popen,
    ):
        play_audio_file(Path("voice.mp3"))

    command = popen.call_args.args[0]
    assert "-Sta" in command
    assert command[command.index("-WindowStyle") + 1] == "Hidden"
    assert popen.call_args.kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW


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


def test_incoming_message_interrupts_historical_replay() -> None:
    """Live speech must own the audio channel instead of overlapping replay."""
    playback = Mock()
    playback.poll.return_value = None
    memory = VoiceMemory()
    memory.playback = playback
    memory.replay_active = True
    memory.enqueue("Mensaje entrante", "es")
    playback.terminate.assert_called_once_with()
    assert memory.replay_active is False
    assert memory.playback is None


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
    from brain.infrastructure.voice import daemon

    config = {"active_voice_engine": "openai", "voice_engines": {"openai": {"voices": {"es": "shimmer"}}}}
    request = {"text": "Hola", "lang": "es"}
    targeted_request = {**request, "codexThreadId": "019f5dad-af67-7533-b394-8fb55258adb2"}
    with patch.object(daemon, "load_voice_config", return_value=config):
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


def test_muted_active_message_expires_at_natural_playback_deadline() -> None:
    memory = VoiceMemory()
    memory.set_state("speaking", "Mensaje largo", "happy", "**Mensaje largo**")
    memory.set_playback_duration(90_000)
    assert memory.toggle_muted() is True
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


def test_paid_synthesis_hash_reuses_audio_without_second_provider_call() -> None:
    from brain.infrastructure.voice import daemon

    request = {"text": "Mensaje estable", "lang": "es"}
    config = {
        "active_voice_engine": "openai",
        "voice_engines": {"openai": {"api_key": "secret", "model": "tts-1", "voices": {"es": "shimmer"}}},
    }
    daemon.MEMORY.audio_by_hash.clear()
    with (
        patch.object(daemon, "load_voice_config", return_value=config),
        patch.object(daemon, "synthesize", return_value=b"audio") as synthesize,
    ):
        assert daemon.synthesize_or_reuse(request) == b"audio"
        assert daemon.synthesize_or_reuse(request) == b"audio"
    synthesize.assert_called_once_with(request)


def test_paid_synthesis_hash_changes_with_voice_or_text() -> None:
    from brain.infrastructure.voice import daemon

    first_config = {"active_voice_engine": "openai", "voice_engines": {"openai": {"voices": {"es": "shimmer"}}}}
    second_config = {"active_voice_engine": "openai", "voice_engines": {"openai": {"voices": {"es": "nova"}}}}
    with patch.object(daemon, "load_voice_config", return_value=first_config):
        first = daemon.paid_synthesis_cache_key({"text": "Hola", "lang": "es"})
        different_text = daemon.paid_synthesis_cache_key({"text": "Adiós", "lang": "es"})
    with patch.object(daemon, "load_voice_config", return_value=second_config):
        different_voice = daemon.paid_synthesis_cache_key({"text": "Hola", "lang": "es"})
    assert len({first, different_text, different_voice}) == 3


def test_voice_memory_mute_preserves_visual_message_and_status() -> None:
    memory = VoiceMemory()
    memory.set_state("speaking", "Mensaje visible", "happy")

    assert memory.toggle_muted() is True
    assert memory.status()["muted"] is True
    assert memory.status()["state"] == "muted"
    assert memory.status()["text"] == "Mensaje visible"

    memory.show_muted_message("Siguiente mensaje", "focused")
    assert memory.status()["text"] == "Siguiente mensaje"
    assert memory.status()["state"] == "muted_replay"
    assert memory.toggle_muted() is False
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


def test_playback_prelude_exposes_animation_without_claiming_audio_started() -> None:
    memory = VoiceMemory()
    memory.prepare_playback("ReacciÃ³n", "reacting")

    assert memory.begin_playback_prelude() is True
    assert memory.status()["state"] == "preparing"
    assert memory.status()["emotion"] == "reacting"
    assert memory.has_pending_playback() is True
    memory.mark_playback_started()
    assert memory.status()["state"] == "speaking"


def test_url_player_signals_prelude_then_waits_before_audio() -> None:
    with patch("brain.infrastructure.voice.engines.subprocess.Popen") as popen:
        play_audio_url(
            "http://127.0.0.1/audio",
            "http://127.0.0.1/playback-started",
            "http://127.0.0.1/playback-preparing",
            1,
        )

    command = popen.call_args.args[0][-1]
    assert command.index("playback-preparing") < command.index("Start-Sleep -Milliseconds 1000")
    assert command.index("Start-Sleep -Milliseconds 1000") < command.index("$m.Play()")
    assert command.index("$m.Play()") < command.index("playback-started")
    assert "$i -ge 600" not in command
    assert "$duration.TotalSeconds + 30" in command
    assert "Start-Sleep -Milliseconds 2000; $m.Close()" in command


def test_file_player_has_no_fixed_sixty_second_cutoff() -> None:
    with (
        patch("brain.infrastructure.voice.engines.sys.platform", "win32"),
        patch("brain.infrastructure.voice.engines.subprocess.Popen") as popen,
    ):
        play_audio_file(Path("long-voice.mp3"))

    command = popen.call_args.args[0][-1]
    assert "$i -ge 600" not in command
    assert "$duration.TotalSeconds + 30" in command
    assert "Start-Sleep -Milliseconds 2000; $m.Close()" in command
    assert "$m.Close()" in command


def test_url_player_reports_natural_duration_after_media_starts() -> None:
    with patch("brain.infrastructure.voice.engines.subprocess.Popen") as popen:
        play_audio_url(
            "http://127.0.0.1/audio",
            "http://127.0.0.1/playback-started",
            duration_callback_url="http://127.0.0.1/playback-duration",
        )

    command = popen.call_args.args[0][-1]
    assert "NaturalDuration.TimeSpan" in command
    assert "playback-duration" in command
    assert "$duration.TotalMilliseconds + 2000" in command
    assert command.index("$m.Play()") < command.index("playback-duration")


def test_muted_requests_skip_synthesis_but_keep_refined_text() -> None:
    import inspect

    request_source = inspect.getsource(__import__("brain.infrastructure.voice.daemon", fromlist=["consume_requests"]).consume_requests)
    assert request_source.index("cohere_signal_presentation") < request_source.index("MEMORY.is_muted()")
    assert request_source.index("MEMORY.is_muted()") < request_source.index("synthesis = synthesize_or_reuse(request)")
    assert "MEMORY.show_muted_message" in request_source
