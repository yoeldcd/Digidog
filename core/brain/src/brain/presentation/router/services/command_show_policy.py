"""Resolve immutable per-command avatar presentation policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from brain.infrastructure.avatar.configuration.avatar_config_dtos import AvatarConfigDTO


@dataclass(frozen=True, slots=True)
class CommandShowPolicy:
    """Describe immutable avatar presentation settings for one command.

    Attributes:
        show_message: Whether the avatar should render the command result.
        speak_message: Whether the avatar should narrate the command result.
        hiden_on_muted: Whether muted messages stay visually hidden.
        level: Presentation importance exposed to the avatar client.
        pre_processor: Text preprocessing policy identifier.
        animation: Avatar animation policy identifier.
    """

    show_message: bool = True
    speak_message: bool = True
    hiden_on_muted: bool = False
    level: Literal["important", "informative"] = "informative"
    pre_processor: str = "<default>"
    animation: str = "<default>"


def command_show_policy(command: str, config: AvatarConfigDTO) -> CommandShowPolicy | None:
    """Resolve one command's effective avatar presentation policy.

    Configured silence takes precedence over every customization and returns
    ``None``. Commands without a customization receive immutable defaults.

    Args:
        command: Canonical CLI command name, optionally hyphenated.
        config: Validated avatar configuration that owns policy precedence.

    Returns:
        CommandShowPolicy | None: Configured or default presentation policy, or
            ``None`` for an authoritatively silent command.
    """
    if command in config.silent_commands:
        return None

    customization_key = command.replace("-", "_")
    customization = config.commands_show_customization.get(customization_key)

    if customization is None:
        return CommandShowPolicy()

    return CommandShowPolicy(
        show_message=customization.show_message,
        speak_message=customization.speak_message,
        hiden_on_muted=customization.hiden_on_muted,
        level=customization.level,
        pre_processor=customization.pre_processor,
        animation=customization.animation,
    )
