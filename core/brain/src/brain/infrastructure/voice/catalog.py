"""Voice and model catalog adapters for configured avatar speech engines."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from typing import Any

import requests

from brain.infrastructure.voice.config import load_voice_config


SUPPORTED_ENGINES = ("edge", "pyttsx3", "openai", "elevenlabs")
ENGINE_MODES = {"edge": "hybrid", "pyttsx3": "offline", "openai": "online", "elevenlabs": "online"}


class VoiceCatalogService:
    """Resolve the voices and models exposed by one speech engine."""

    def list_catalog(self, engine_name: str = "") -> dict[str, Any]:
        """Return a normalized catalog for one requested engine."""
        config = load_voice_config()
        resolved_engine = (engine_name or str(config.get("active_voice_engine", "edge"))).strip().casefold()
        if resolved_engine not in SUPPORTED_ENGINES:
            supported = ", ".join(SUPPORTED_ENGINES)
            raise ValueError(f"Unknown avatar voice engine `{resolved_engine}`. Supported engines: {supported}.")
        engine_config = dict(config.get("voice_engines", {}).get(resolved_engine, {}))
        resolver = getattr(self, f"_list_{resolved_engine}")
        catalog = resolver(engine_config)
        return {
            "engine": resolved_engine,
            "mode": ENGINE_MODES[resolved_engine],
            "active": resolved_engine == str(config.get("active_voice_engine", "edge")).casefold(),
            "voices": catalog.get("voices", []),
            "voiceMap": catalog.get("voiceMap", {}),
            "models": catalog.get("models", []),
            "source": catalog.get("source", "engine"),
            "warnings": catalog.get("warnings", []),
            "settings": catalog.get("settings", {}),
        }

    @staticmethod
    def _list_edge(config: dict[str, Any]) -> dict[str, Any]:
        """Read online Neural and offline SAPI voices exposed by Edge on Windows."""
        if sys.platform != "win32":
            raise RuntimeError("The Edge avatar engine voice catalog currently requires Windows.")
        selected = {str(value) for value in dict(config.get("voices", {})).values()}
        selected.update(f"{value}Neural" for value in tuple(selected) if value and not value.endswith("Neural"))
        warnings: list[str] = []
        online_voices: list[dict[str, Any]] = []
        try:
            import edge_tts

            online_voices = [
                {
                    "id": str(row.get("ShortName", "")),
                    "name": str(row.get("FriendlyName") or row.get("ShortName", "")),
                    "language": str(row.get("Locale", "")),
                    "gender": str(row.get("Gender", "")),
                    "availability": "online",
                    "selected": str(row.get("ShortName", "")) in selected,
                }
                for row in asyncio.run(edge_tts.list_voices())
            ]
        except Exception as exc:
            warnings.append(f"Online Edge voice discovery failed: {exc}")
        command = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.GetInstalledVoices() | ForEach-Object { "
            "$i = $_.VoiceInfo; [pscustomobject]@{ id=$i.Name; name=$i.Name; "
            "language=$i.Culture.Name; gender=$i.Gender.ToString(); age=$i.Age.ToString() } "
            "} | ConvertTo-Json -Compress; $s.Dispose()"
        )
        result = subprocess.run(
            ["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        offline_voices = _normalize_json_rows(result.stdout)
        for voice in offline_voices:
            voice["availability"] = "offline"
            voice["selected"] = str(voice.get("id", "")) in selected
        voices = [*online_voices, *offline_voices]
        return {
            "voices": voices,
            "voiceMap": _build_voice_map(voices, language_field="language"),
            "models": [],
            "source": "engine",
            "warnings": warnings,
            "settings": {
                "rate": str(config.get("rate", "+0%")),
                "volume": str(config.get("volume", "+0%")),
                "pitch": str(config.get("pitch", "+0Hz")),
            },
        }

    @staticmethod
    def _list_pyttsx3(config: dict[str, Any]) -> dict[str, Any]:
        """Read voices exposed by the local `pyttsx3` driver."""
        try:
            import pyttsx3
        except ImportError as exc:
            raise RuntimeError("The `pyttsx3` package is not installed.") from exc
        engine = pyttsx3.init()
        try:
            selected = {str(value) for value in dict(config.get("voices", {})).values()}
            voices = [
                {
                    "id": str(voice.id),
                    "name": str(getattr(voice, "name", voice.id)),
                    "languages": [_decode_language(value) for value in getattr(voice, "languages", [])],
                    "gender": str(getattr(voice, "gender", "") or ""),
                    "age": getattr(voice, "age", None),
                    "selected": str(voice.id) in selected,
                }
                for voice in engine.getProperty("voices")
            ]
        finally:
            engine.stop()
        return {
            "voices": voices,
            "voiceMap": _build_voice_map(voices, language_field="languages"),
            "models": [],
            "source": "engine",
        }

    @staticmethod
    def _list_openai(config: dict[str, Any]) -> dict[str, Any]:
        """Return the voices and model explicitly exposed by OpenAI configuration."""
        voices = sorted({str(value) for value in dict(config.get("voices", {})).values() if value})
        default_voice = str(config.get("voice", "")).strip()
        if default_voice:
            voices = sorted({*voices, default_voice})
        model = str(config.get("model", "")).strip()
        return {
            "voices": [{"id": voice, "name": voice, "selected": voice == default_voice} for voice in voices],
            "voiceMap": dict(config.get("voices", {})) or ({"default": default_voice} if default_voice else {}),
            "models": ([{"id": model, "name": model, "selected": True}] if model else []),
            "source": "configuration",
        }

    @staticmethod
    def _list_elevenlabs(config: dict[str, Any]) -> dict[str, Any]:
        """Read the live ElevenLabs voice and TTS model catalogs."""
        api_key = str(config.get("api_key", "")).strip()
        if not api_key or api_key.startswith("$"):
            raise RuntimeError("ElevenLabs voice discovery requires a resolved API key.")
        headers = {"xi-api-key": api_key}
        voices_response = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers, timeout=20)
        voices_response.raise_for_status()
        models_response = requests.get("https://api.elevenlabs.io/v1/models", headers=headers, timeout=20)
        models_response.raise_for_status()
        selected_voice = str(config.get("voice_id", ""))
        selected_model = str(config.get("model_id", ""))
        voices = [
            {
                "id": str(row.get("voice_id", "")),
                "name": str(row.get("name", "")),
                "category": str(row.get("category", "")),
                "language": str(dict(row.get("labels", {})).get("language", "")),
                "selected": str(row.get("voice_id", "")) == selected_voice,
            }
            for row in voices_response.json().get("voices", [])
        ]
        models = [
            {
                "id": str(row.get("model_id", "")),
                "name": str(row.get("name", "")),
                "selected": str(row.get("model_id", "")) == selected_model,
            }
            for row in models_response.json()
            if row.get("can_do_text_to_speech", True)
        ]
        configured_map = dict(config.get("voices", {}))
        return {
            "voices": voices,
            "voiceMap": configured_map or _build_voice_map(voices, language_field="language"),
            "models": models,
            "source": "engine",
        }


def _normalize_json_rows(value: str) -> list[dict[str, Any]]:
    """Normalize PowerShell JSON output that may contain zero, one, or many rows."""
    if not value.strip():
        return []
    parsed = json.loads(value)
    rows = parsed if isinstance(parsed, list) else [parsed]
    return [dict(row) for row in rows]


def _decode_language(value: object) -> str:
    """Convert a `pyttsx3` language token to readable text."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").lstrip("\x05")
    return str(value)


def _build_voice_map(rows: list[dict[str, Any]], language_field: str) -> dict[str, str]:
    """Build a copy-ready JSON voice map with stable duplicate suffixes."""
    voice_map: dict[str, str] = {}
    key_counts: dict[str, int] = {}
    for row in rows:
        raw_language = row.get(language_field, "")
        if isinstance(raw_language, list):
            raw_language = raw_language[0] if raw_language else ""
        base_key = str(raw_language or row.get("name") or "voice").split("-", 1)[0].casefold()
        base_key = "".join(character for character in base_key if character.isalnum() or character == "_") or "voice"
        key_counts[base_key] = key_counts.get(base_key, 0) + 1
        suffix = "" if key_counts[base_key] == 1 else f"_{key_counts[base_key]}"
        voice_map[f"{base_key}{suffix}"] = str(row.get("id", ""))
    return voice_map
