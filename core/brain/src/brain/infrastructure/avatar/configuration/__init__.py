"""Typed Avatar configuration infrastructure."""

from brain.infrastructure.avatar.configuration.avatar_config import (
    load_avatar_config,
    resolve_voice_daemon_endpoint,
)
from brain.infrastructure.avatar.configuration.avatar_config_dtos import (
    AvatarConfigDTO,
    AvatarConfigModel,
    AvatarReactionConfigDTO,
    EdgeVoiceConfigDTO,
    ElevenLabsVoiceConfigDTO,
    OpenAiVoiceConfigDTO,
    Pyttsx3VoiceConfigDTO,
    VoiceEnginesConfigDTO,
    VoiceServiceConfigDTO,
)

__all__ = [
    "AvatarConfigDTO",
    "AvatarConfigModel",
    "AvatarReactionConfigDTO",
    "EdgeVoiceConfigDTO",
    "ElevenLabsVoiceConfigDTO",
    "OpenAiVoiceConfigDTO",
    "Pyttsx3VoiceConfigDTO",
    "VoiceEnginesConfigDTO",
    "VoiceServiceConfigDTO",
    "load_avatar_config",
    "resolve_voice_daemon_endpoint",
]