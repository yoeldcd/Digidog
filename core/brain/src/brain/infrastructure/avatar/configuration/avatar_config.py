"""Load and validate the semantic avatar configuration."""

from __future__ import annotations

import json
import os
from typing import TypeAlias

from pydantic import ValidationError

from brain.infrastructure.runtime.paths import get_avatar_config_path
from brain.infrastructure.avatar.configuration.avatar_config_dtos import AvatarConfigDTO


JsonConfigurationValue: TypeAlias = (
    str | int | float | bool | None | list["JsonConfigurationValue"] | dict[str, "JsonConfigurationValue"]
)
"""JSON-compatible configuration value that may contain environment placeholders."""


def load_avatar_config() -> AvatarConfigDTO:
    """Load validated avatar settings or a safe fallback.

    Returns:
        AvatarConfigDTO: Frozen validated avatar settings.
    """

    config_path = get_avatar_config_path()
    if not config_path.is_file():
        return AvatarConfigDTO()

    try:
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
        return AvatarConfigDTO.model_validate(_expand_environment_values(parsed))
    except (OSError, json.JSONDecodeError, TypeError, ValidationError):
        return AvatarConfigDTO()


def _expand_environment_values(value: JsonConfigurationValue) -> JsonConfigurationValue:
    """Expand supported environment placeholders recursively.

    Args:
        value: JSON-compatible configuration value.

    Returns:
        Equivalent value with environment placeholders resolved.
    """

    if isinstance(value, dict):
        return {key: _expand_environment_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment_values(item) for item in value]
    if isinstance(value, str) and value.startswith("$"):
        variable_name = value.removeprefix("$Env:").removeprefix("$")
        return os.environ.get(variable_name, value)
    return value


def resolve_voice_daemon_endpoint(config: AvatarConfigDTO | None = None) -> tuple[str, int]:
    """Return the validated daemon endpoint.

    Args:
        config: Optional typed configuration override.

    Returns:
        tuple[str, int]: Host and port for the local voice daemon.
    """

    resolved = config or load_avatar_config()
    return resolved.service.host, resolved.service.port