# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Vectorstore configuration loading."""

from __future__ import annotations

# Standard Libraries Imports
import json

# Application Modules Imports
from brain.application.knowledge.runtime.config_store import resolve_secret
from brain.infrastructure.runtime.paths import get_brain_configs_path


def load_config() -> dict:
    """
    Load unified brain memory config and resolve environment references.

    Returns:
        dict: Memory/vectorstore configuration payload.
    """
    config_path = get_brain_configs_path()
    if not config_path.exists():
        return {}
    try:
        content = config_path.read_text(encoding="utf-8")
        data = json.loads(content)
        if "memory" in data and isinstance(data["memory"], dict):
            data = data["memory"]

        for section in ("embedding_model", "text_model"):
            if section in data:
                for key, value in data[section].items():
                    data[section][key] = _resolve_config_value(value=value)
        return data
    except Exception:
        return {}


def _resolve_config_value(value: object) -> object:
    """
    Resolve environment-variable references in vectorstore config values.

    Args:
        value: Raw config value.

    Returns:
        object: Resolved value or original value.
    """
    if isinstance(value, str) and value.startswith("$"):
        return resolve_secret(value)
    return value
