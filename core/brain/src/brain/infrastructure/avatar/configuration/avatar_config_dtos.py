"""Immutable typed schema for the avatar configuration document."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AvatarConfigModel(BaseModel):
    """Provide immutable strict validation for avatar configuration values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class VoiceServiceConfigDTO(AvatarConfigModel):
    """Represent the avatar voice service endpoint."""

    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8133, ge=1, le=65535)


class EdgeVoiceConfigDTO(AvatarConfigModel):
    """Represent the Edge synthesis configuration."""

    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"
    sanitization_regex: str = ""
    voices: dict[str, str] = Field(
        default_factory=lambda: {
            "es": "es-ES-ElviraNeural",
            "en": "en-US-AriaNeural",
        }
    )


class Pyttsx3VoiceConfigDTO(AvatarConfigModel):
    """Represent the local pyttsx3 synthesis configuration."""

    rate: int = Field(default=150, ge=1)
    volume: float = Field(default=1.0, ge=0.0, le=1.0)
    voices: dict[str, str] = Field(
        default_factory=lambda: {
            "es": "spanish",
            "en": "english",
        }
    )


class OpenAiVoiceConfigDTO(AvatarConfigModel):
    """Represent the OpenAI synthesis configuration."""

    api_key: str = ""
    model: str = "tts-1"
    voice: str = "shimmer"
    voices: dict[str, str] = Field(
        default_factory=lambda: {
            "es": "shimmer",
            "en": "shimmer",
        }
    )


class ElevenLabsVoiceConfigDTO(AvatarConfigModel):
    """Represent the ElevenLabs synthesis configuration, including both model keys."""

    api_key: str = ""
    model_id_: str = "eleven_multilingual_v2"
    model_id: str = "eleven_flash_v2_5"
    voice_id: str = ""
    voices: dict[str, str] = Field(default_factory=dict)


class VoiceEnginesConfigDTO(AvatarConfigModel):
    """Group every supported speech engine configuration."""

    edge: EdgeVoiceConfigDTO = Field(default_factory=EdgeVoiceConfigDTO)
    pyttsx3: Pyttsx3VoiceConfigDTO = Field(default_factory=Pyttsx3VoiceConfigDTO)
    openai: OpenAiVoiceConfigDTO = Field(default_factory=OpenAiVoiceConfigDTO)
    elevenlabs: ElevenLabsVoiceConfigDTO = Field(default_factory=ElevenLabsVoiceConfigDTO)


class AvatarReactionConfigDTO(AvatarConfigModel):
    """Represent one configured avatar interaction reaction."""

    message: str = Field(min_length=1)
    animation: str = Field(default="reacting", min_length=1)


class CommandShowCustomizationDTO(AvatarConfigModel):
    """Control the visual and spoken projection of one CLI command."""

    show_message: bool = True
    speak_message: bool = True
    hiden_on_muted: bool = False
    level: Literal["important", "informative"] = "informative"
    pre_processor: str = "<default>"
    animation: str = "<default>"

    @field_validator("pre_processor")
    @classmethod
    def validate_pre_processor(cls, value: str) -> str:
        """Require custom instructions to expose the command output placeholder."""
        if value not in {"<none>", "<default>"} and "{OUTPUT}" not in value:
            raise ValueError("Custom pre_processor instructions must contain {OUTPUT}.")
        return value


class AvatarConfigDTO(AvatarConfigModel):
    """Represent the complete persisted avatar configuration document."""

    service: VoiceServiceConfigDTO = Field(default_factory=VoiceServiceConfigDTO)
    active_voice_engine: Literal["edge", "pyttsx3", "openai", "elevenlabs"] = "edge"
    voice_engines: VoiceEnginesConfigDTO = Field(default_factory=VoiceEnginesConfigDTO)
    ignore_quota_state: bool = False
    tts_chunks_size: int = Field(default=2000, ge=1)
    reactions: tuple[AvatarReactionConfigDTO, ...] = ()
    silent_commands: tuple[str, ...] = ()
    commands_show_customization: dict[str, CommandShowCustomizationDTO] = Field(default_factory=dict)