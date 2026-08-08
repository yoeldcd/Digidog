"""Avatar configuration and window-process infrastructure."""

from brain.infrastructure.avatar.configuration import (
    AvatarConfigDTO,
    AvatarConfigModel,
    AvatarReactionConfigDTO,
    EdgeVoiceConfigDTO,
    ElevenLabsVoiceConfigDTO,
    OpenAiVoiceConfigDTO,
    Pyttsx3VoiceConfigDTO,
    VoiceEnginesConfigDTO,
    VoiceServiceConfigDTO,
    load_avatar_config,
    resolve_voice_daemon_endpoint,
)
from brain.infrastructure.avatar.process import (
    AvatarProcessSupervisor,
    SupervisedVoiceRuntime,
    run_avatar_supervision,
    supervise_avatar_window,
)

__all__ = [
    "AvatarConfigDTO",
    "AvatarConfigModel",
    "AvatarReactionConfigDTO",
    "AvatarProcessSupervisor",
    "EdgeVoiceConfigDTO",
    "ElevenLabsVoiceConfigDTO",
    "OpenAiVoiceConfigDTO",
    "Pyttsx3VoiceConfigDTO",
    "SupervisedVoiceRuntime",
    "VoiceEnginesConfigDTO",
    "VoiceServiceConfigDTO",
    "load_avatar_config",
    "resolve_voice_daemon_endpoint",
    "run_avatar_supervision",
    "supervise_avatar_window",
]