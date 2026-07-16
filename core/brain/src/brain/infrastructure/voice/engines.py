# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Speech synthesis engine implementations for Edge-TTS, PyTTSx3, OpenAI, and ElevenLabs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


PLAYBACK_TAIL_OFFSET_MILLISECONDS = 2_000


@dataclass(frozen=True, slots=True)
class LocalPlayback:
    """Deferred local speech process that starts only in the playback worker."""

    command: list[str]
    popen_kwargs: dict[str, Any]

    def start(self) -> subprocess.Popen[bytes]:
        """Start local speech without blocking the caller."""
        return subprocess.Popen(self.command, **self.popen_kwargs)


def play_audio_file(filepath: Path) -> None:
    """Start audible playback in a non-blocking STA PowerShell process."""
    abs_path = filepath.resolve().as_posix()
    # PresentationCore assembly provides System.Windows.Media.MediaPlayer.
    # Metadata loading is bounded, while valid media plays through its natural
    # duration instead of being truncated by a fixed wall-clock limit.
    ps_cmd = (
        "[void][System.Reflection.Assembly]::LoadWithPartialName('PresentationCore'); "
        "$m = New-Object System.Windows.Media.MediaPlayer; "
        f"$m.Open('{abs_path}'); "
        "$m.Play(); "
        "$loadDeadline = [DateTime]::UtcNow.AddSeconds(30); "
        "while (-not $m.NaturalDuration.HasTimeSpan -and [DateTime]::UtcNow -lt $loadDeadline) { "
        "    Start-Sleep -Milliseconds 100 "
        "}; "
        "if ($m.NaturalDuration.HasTimeSpan) { "
        "    $duration = $m.NaturalDuration.TimeSpan; "
        "    $playbackDeadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(30, $duration.TotalSeconds + 30)); "
        "    while ($m.Position + [TimeSpan]::FromMilliseconds(150) -lt $duration "
        "           -and [DateTime]::UtcNow -lt $playbackDeadline) { Start-Sleep -Milliseconds 100 } "
        "}; "
        f"Start-Sleep -Milliseconds {PLAYBACK_TAIL_OFFSET_MILLISECONDS}; "
        "$m.Close()"
    )

    if sys.platform == "win32":
        # MediaPlayer needs an STA apartment. CREATE_NO_WINDOW preserves the
        # interactive audio session while keeping playback invisible and asynchronous.
        subprocess.Popen(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Sta",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps_cmd,
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            ["powershell", "-Command", ps_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


def play_audio_url(
    url: str,
    started_callback_url: str = "",
    preparing_callback_url: str = "",
    prelude_seconds: float = 0,
    duration_callback_url: str = "",
) -> subprocess.Popen[bytes]:
    """Play an HTTP resource and optionally signal a timed visual prelude."""
    if sys.platform != "win32":
        raise RuntimeError("Memory-backed URL playback currently requires Windows.")
    escaped_url = url.replace("'", "''")
    escaped_callback = started_callback_url.replace("'", "''")
    escaped_preparing_callback = preparing_callback_url.replace("'", "''")
    escaped_duration_callback = duration_callback_url.replace("'", "''")
    callback_command = (
        f"try {{ Invoke-WebRequest -UseBasicParsing -Method Post -ContentType 'application/json' -Body '{{}}' -Uri '{escaped_callback}' | Out-Null }} catch {{ }}; "
        if escaped_callback else ""
    )
    preparing_command = (
        f"try {{ Invoke-WebRequest -UseBasicParsing -Method Post -ContentType 'application/json' -Body '{{}}' -Uri '{escaped_preparing_callback}' | Out-Null }} catch {{ }}; "
        if escaped_preparing_callback else ""
    )
    duration_command = (
        "$durationBody = '{\"milliseconds\":' + "
        f"[Math]::Ceiling($duration.TotalMilliseconds + {PLAYBACK_TAIL_OFFSET_MILLISECONDS}) + '}}'; "
        f"try {{ Invoke-WebRequest -UseBasicParsing -Method Post -ContentType 'application/json' -Body $durationBody -Uri '{escaped_duration_callback}' | Out-Null }} catch {{ }}; "
        if escaped_duration_callback else ""
    )
    prelude_command = f"Start-Sleep -Milliseconds {round(max(0, min(3, prelude_seconds)) * 1000)}; " if prelude_seconds else ""
    command = (
        "[void][System.Reflection.Assembly]::LoadWithPartialName('PresentationCore'); "
        "$m = New-Object System.Windows.Media.MediaPlayer; "
        f"$m.Open([Uri]'{escaped_url}'); {preparing_command}{prelude_command}$m.Play(); {callback_command}"
        "$loadDeadline = [DateTime]::UtcNow.AddSeconds(30); "
        "while (-not $m.NaturalDuration.HasTimeSpan -and [DateTime]::UtcNow -lt $loadDeadline) { "
        "Start-Sleep -Milliseconds 100 }; "
        "if ($m.NaturalDuration.HasTimeSpan) { "
        "$duration = $m.NaturalDuration.TimeSpan; "
        f"{duration_command}"
        "}; "
        "if ($m.NaturalDuration.HasTimeSpan) { "
        "$playbackDeadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(30, $duration.TotalSeconds + 30)); "
        "while ($m.Position + [TimeSpan]::FromMilliseconds(150) -lt $duration "
        "-and [DateTime]::UtcNow -lt $playbackDeadline) { Start-Sleep -Milliseconds 100 } }; "
        f"Start-Sleep -Milliseconds {PLAYBACK_TAIL_OFFSET_MILLISECONDS}; "
        "$m.Close()"
    )
    return subprocess.Popen(
        ["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-Sta", "-WindowStyle", "Hidden", "-Command", command],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
class BaseTtsEngine:
    """Base interface for Text-to-Speech engines."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def prepare(self, text: str, lang: str) -> LocalPlayback:
        """Create a deferred local playback request."""
        raise NotImplementedError

    def speak(self, text: str, lang: str) -> subprocess.Popen[bytes]:
        """Start local playback asynchronously and return its process."""
        return self.prepare(text=text, lang=lang).start()


class EdgeTtsEngine(BaseTtsEngine):
    """Free Windows speech engine that avoids persistent or transient audio files."""

    def prepare(self, text: str, lang: str) -> LocalPlayback:
        """Build deferred Windows speech without blocking synthesis or UI threads."""
        if sys.platform != "win32":
            raise RuntimeError("File-free speech for the free engine currently requires Windows.")

        escaped_text = text.replace("'", "''")
        culture = "es-ES" if lang == "es" else "en-US"
        rate_percent = _percentage_value(self.config.get("rate", "+0%"))
        volume_percent = _percentage_value(self.config.get("volume", "+0%"))
        pitch = _pitch_value(self.config.get("pitch", "+0Hz"))
        sapi_rate = max(-10, min(10, round(rate_percent / 10)))
        sapi_volume = max(0, min(100, 100 + volume_percent))
        command = (
            "Add-Type -AssemblyName System.Speech; "
            "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"try {{ $voice.SelectVoiceByHints('Female', 'Adult', 0, '{culture}') }} catch {{ }}; "
            f"$voice.Rate = {sapi_rate}; $voice.Volume = {sapi_volume}; "
            f"$escaped = [Security.SecurityElement]::Escape('{escaped_text}'); "
            f"$ssml = \"<speak version='1.0' xml:lang='{culture}'><prosody pitch='{pitch}'>\" + "
            "$escaped + '</prosody></speak>'; $voice.SpeakSsml($ssml); "
            "$voice.Dispose()"
        )
        return LocalPlayback(
            command=["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            popen_kwargs={
                "creationflags": subprocess.CREATE_NO_WINDOW,
                "close_fds": True,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            },
        )


class Pyttsx3Engine(BaseTtsEngine):
    """PyTTSx3 Engine for 100% offline, local system speech synthesis."""

    def prepare(self, text: str, lang: str) -> LocalPlayback:
        """Build a deferred `pyttsx3` subprocess request."""
        try:
            import pyttsx3
        except ImportError:
            raise RuntimeError(
                "The 'pyttsx3' package is not installed. "
                "Please run: pip install pyttsx3"
            )

        # We wrap pyttsx3 speech in an independent background process call since
        # pyttsx3 is strictly synchronous and ties itself to the calling thread/process.
        # To do this safely and asynchronously without blocking the CLI runner exit,
        # we can execute a simple detached python subprocess script.
        # This keeps the main CLI thread responsive and exits immediately.
        py_cmd = (
            f"import pyttsx3; "
            f"engine = pyttsx3.init(); "
            f"engine.setProperty('rate', {self.config.get('rate', 150)}); "
            f"engine.setProperty('volume', {self.config.get('volume', 1.0)}); "
            f"voices = engine.getProperty('voices'); "
            f"target_lang = 'spa' if '{lang}' == 'es' else 'eng'; "
            f"selected_voice = None; "
            f"for v in voices: "
            f"    if target_lang in getattr(v, 'languages', []) or target_lang in getattr(v, 'name', '').lower(): "
            f"        selected_voice = v.id; "
            f"        break; "
            f"if selected_voice: "
            f"    engine.setProperty('voice', selected_voice); "
            f"engine.say('''{text}'''); "
            f"engine.runAndWait()"
        )

        kwargs: dict[str, Any] = {
            "close_fds": True,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs["start_new_session"] = True
        return LocalPlayback(command=[sys.executable, "-c", py_cmd], popen_kwargs=kwargs)


class OpenAiTtsEngine(BaseTtsEngine):
    """OpenAI TTS API Engine using text-to-speech endpoints."""

    def prepare(self, text: str, lang: str) -> LocalPlayback:
        raise RuntimeError("OpenAI TTS must run through the memory-only voice daemon.")


class ElevenLabsTtsEngine(BaseTtsEngine):
    """ElevenLabs TTS API Engine for highly expressive voice synthesis."""

    def prepare(self, text: str, lang: str) -> LocalPlayback:
        raise RuntimeError("ElevenLabs TTS must run through the memory-only voice daemon.")


def get_engine(engine_name: str, config: dict[str, Any]) -> BaseTtsEngine:
    """Factory to retrieve a configured speech engine."""
    engines = {
        "edge": EdgeTtsEngine,
        "pyttsx3": Pyttsx3Engine,
        "openai": OpenAiTtsEngine,
        "elevenlabs": ElevenLabsTtsEngine,
    }
    engine_class = engines.get(engine_name.lower())
    if not engine_class:
        raise ValueError(f"Unknown voice engine: {engine_name}")
    return engine_class(config)


def _percentage_value(value: object) -> int:
    """Parse a signed Edge percentage for the bounded SAPI fallback."""
    match = re.fullmatch(r"([+-]?\d+)%", str(value).strip())
    return int(match.group(1)) if match else 0


def _pitch_value(value: object) -> str:
    """Return a safe Edge pitch token for SAPI SSML."""
    normalized = str(value).strip()
    return normalized if re.fullmatch(r"[+-]?\d+(?:Hz|%)", normalized, re.IGNORECASE) else "+0Hz"
