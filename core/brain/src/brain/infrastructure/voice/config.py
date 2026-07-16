# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Voice configuration parsing and environment variable expansion service."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from brain.infrastructure.runtime.paths import get_avatar_config_path


DEFAULT_VOICE_DAEMON_HOST = "127.0.0.1"
DEFAULT_VOICE_DAEMON_PORT = 8133


def load_voice_config() -> dict[str, Any]:
    """
    Load the voice configuration JSON, resolving environment variable placeholders.

    Returns:
        dict[str, Any]: Expanded configuration dictionary.
    """
    config_path = get_avatar_config_path()
    if not config_path.is_file():
        return _default_config()

    try:
        content = config_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception:
        return _default_config()

    return _expand_env_vars(data)


def _expand_env_vars(val: Any) -> Any:
    """Recursively expand environment variable placeholders starting with $ or $Env:."""
    if isinstance(val, dict):
        return {k: _expand_env_vars(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_expand_env_vars(v) for v in val]
    if isinstance(val, str):
        if val.startswith("$"):
            # Strip $ or $Env: prefixes
            var_name = val
            if var_name.startswith("$Env:"):
                var_name = var_name[5:]
            elif var_name.startswith("$"):
                var_name = var_name[1:]
            return os.environ.get(var_name, val)
    return val


def _default_config() -> dict[str, Any]:
    """Fallback default configuration if the file is missing or corrupted."""
    return {
        "service": {
            "host": DEFAULT_VOICE_DAEMON_HOST,
            "port": DEFAULT_VOICE_DAEMON_PORT,
        },
        "active_voice_engine": "edge",
        "voice_engines": {
            "edge": {
                "rate": "+0%",
                "volume": "+0%",
                "pitch": "+0Hz",
                "sanitization_regex": r"_+",
                "voices": {
                    "es": "es-ES-ElviraNeural",
                    "en": "en-US-AriaNeural"
                }
            },
            "pyttsx3": {
                "rate": 150,
                "volume": 1.0,
                "voices": {
                    "es": "spanish",
                    "en": "english"
                }
            }
        }
    }


def resolve_voice_daemon_endpoint(config: dict[str, Any] | None = None) -> tuple[str, int]:
    """Resolve the per-core daemon endpoint from avatar configuration."""
    resolved_config = config or load_voice_config()
    service = resolved_config.get("service", {})
    if not isinstance(service, dict):
        service = {}
    host = str(service.get("host", DEFAULT_VOICE_DAEMON_HOST)).strip() or DEFAULT_VOICE_DAEMON_HOST
    try:
        port = int(service.get("port", DEFAULT_VOICE_DAEMON_PORT))
    except (TypeError, ValueError):
        port = DEFAULT_VOICE_DAEMON_PORT
    if port < 1 or port > 65535:
        port = DEFAULT_VOICE_DAEMON_PORT
    return host, port
