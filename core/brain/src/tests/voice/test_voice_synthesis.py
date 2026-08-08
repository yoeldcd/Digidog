# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

'Voice engine selection, synthesis, and audio-cache contracts.'

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch
from brain.infrastructure.voice.daemon.daemon import estimated_speech_seconds
from brain.infrastructure.avatar.configuration.avatar_config_dtos import AvatarConfigDTO
from brain.infrastructure.voice.catalog.voice_catalog import VoiceCatalogService
from brain.infrastructure.voice.audio.engines import EdgeTtsEngine, ElevenLabsTtsEngine, LocalPlayback, OpenAiTtsEngine, play_audio_file


def test_free_windows_engine_uses_speech_api_without_audio_file() -> None:
    """Prepare free-engine text without starting its blocking subprocess."""
    with (
        patch("brain.infrastructure.voice.audio.engines.sys.platform", "win32"),
        patch("brain.infrastructure.voice.audio.engines.subprocess.Popen") as popen,
    ):
        playback = EdgeTtsEngine({}).prepare("No SSD writes", "en")

    assert isinstance(playback, LocalPlayback)
    popen.assert_not_called()


def test_local_playback_starts_only_when_requested() -> None:
    """Keep local synthesis deferred until the sequential playback worker owns it."""
    playback = LocalPlayback(command=["voice"], popen_kwargs={"stdout": subprocess.DEVNULL})
    with patch("brain.infrastructure.voice.audio.engines.subprocess.Popen") as popen:
        playback.start()
    popen.assert_called_once_with(["voice"], stdout=subprocess.DEVNULL)


def test_openai_catalog_reports_configured_voice_and_model() -> None:
    """Expose deterministic configured catalogs when the provider has no list endpoint."""
    config = {
        "active_voice_engine": "openai",
        "voice_engines": {"openai": {"voice": "shimmer", "model": "tts-1", "voices": {"es": "shimmer"}}},
    }
    with patch("brain.infrastructure.voice.catalog.voice_catalog.load_avatar_config", return_value=AvatarConfigDTO.model_validate(config)):
        catalog = VoiceCatalogService().list_catalog(engine_name="openai")
    assert catalog["engine"] == "openai"
    assert catalog["active"] is True
    assert catalog["voices"][0]["id"] == "shimmer"
    assert catalog["voiceMap"] == {"es": "shimmer"}
    assert catalog["models"][0]["id"] == "tts-1"


def test_edge_neural_synthesis_returns_memory_audio_without_local_blocking() -> None:
    """Use the configured online Edge voice while keeping audio in daemon memory."""
    from brain.infrastructure.voice.daemon import daemon

    config = {"active_voice_engine": "edge", "voice_engines": {"edge": {"voices": {"es": "es-CO-Salome"}}}}
    with (
        patch.object(daemon, "load_avatar_config", return_value=AvatarConfigDTO.model_validate(config)),
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
    from brain.infrastructure.voice.daemon import daemon

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
        patch.object(daemon, "load_avatar_config", return_value=AvatarConfigDTO.model_validate(config)),
        patch.object(daemon, "_synthesize_edge_audio", new_callable=AsyncMock, return_value=b"audio") as synthesize,
    ):
        daemon.synthesize({"text": "brain_avatar__config.json", "lang": "es"})

    assert synthesize.call_args.kwargs["text"] == "brain avatar config.json"


def test_engine_boundary_strips_markdown_headers_and_tags_from_synthesis() -> None:
    """Sanitize direct daemon clients without altering their rich display text."""
    from brain.infrastructure.voice.daemon import daemon

    config = {
        "active_voice_engine": "edge",
        "voice_engines": {"edge": {"voices": {"es": "es-CO-Salome"}}},
    }
    request = {
        "text": "## Informe <strong>privado</strong>\n\nTexto con `código` y <em>énfasis</em>.",
        "displayText": "## Informe <strong>privado</strong>",
        "lang": "es",
    }
    with (
        patch.object(daemon, "load_avatar_config", return_value=AvatarConfigDTO.model_validate(config)),
        patch.object(daemon, "_synthesize_edge_audio", new_callable=AsyncMock, return_value=b"audio") as synthesize,
    ):
        daemon.synthesize(request)

    assert synthesize.call_args.kwargs["text"] == "Informe privado Texto con código y énfasis."
    assert request["displayText"] == "## Informe <strong>privado</strong>"


def test_invalid_engine_sanitization_regex_preserves_spoken_text() -> None:
    """A malformed optional pattern must not break avatar delivery."""
    from brain.infrastructure.voice.daemon.daemon import sanitize_engine_text

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
        patch("brain.infrastructure.voice.audio.engines.sys.platform", "win32"),
        patch("brain.infrastructure.voice.audio.engines.subprocess.Popen") as popen,
    ):
        play_audio_file(Path("voice.mp3"))

    command = popen.call_args.args[0]
    assert "-Sta" in command
    assert command[command.index("-WindowStyle") + 1] == "Hidden"
    assert popen.call_args.kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW


def test_speech_estimate_ignores_markdown_table_content() -> None:
    """Visual rows never extend a muted message's narrable lifetime."""
    spoken = "Tengo dos resultados."
    display = spoken + "\n\n| estado | contenido |\n| --- | --- |\n| Γ£à | una fila muy extensa que no se narra |"

    assert estimated_speech_seconds(display) == estimated_speech_seconds(spoken)


def test_paid_synthesis_hash_reuses_audio_without_second_provider_call() -> None:
    from brain.infrastructure.voice.daemon import daemon

    request = {"text": "Mensaje estable", "lang": "es"}
    config = {
        "active_voice_engine": "openai",
        "voice_engines": {"openai": {"api_key": "secret", "model": "tts-1", "voices": {"es": "shimmer"}}},
    }
    daemon.MEMORY.audio_by_hash.clear()
    with (
        patch.object(daemon, "load_avatar_config", return_value=AvatarConfigDTO.model_validate(config)),
        patch.object(daemon, "synthesize", return_value=b"audio") as synthesize,
    ):
        assert daemon.synthesize_or_reuse(request) == b"audio"
        assert daemon.synthesize_or_reuse(request) == b"audio"
    synthesize.assert_called_once_with(request)


def test_paid_synthesis_hash_changes_with_voice_or_text() -> None:
    from brain.infrastructure.voice.daemon import daemon

    first_config = {"active_voice_engine": "openai", "voice_engines": {"openai": {"voices": {"es": "shimmer"}}}}
    second_config = {"active_voice_engine": "openai", "voice_engines": {"openai": {"voices": {"es": "nova"}}}}
    with patch.object(daemon, "load_avatar_config", return_value=AvatarConfigDTO.model_validate(first_config)):
        first = daemon.paid_synthesis_cache_key({"text": "Hola", "lang": "es"})
        different_text = daemon.paid_synthesis_cache_key({"text": "Adiós", "lang": "es"})
    with patch.object(daemon, "load_avatar_config", return_value=AvatarConfigDTO.model_validate(second_config)):
        different_voice = daemon.paid_synthesis_cache_key({"text": "Hola", "lang": "es"})
    assert len({first, different_text, different_voice}) == 3
