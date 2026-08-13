"""Immutable contracts crossing the voice daemon boundary."""

from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.contracts.instance_results import (
    InstanceEnqueueResult,
    InstanceTerminalResult,
    InstanceTerminalState,
    VoiceEnqueueResult,
    VoiceTerminalResult,
    VoiceTerminalState,
    instance_id_from_payload,
    terminal_result_from_payload,
)

__all__ = [
    "AvatarSpeakRequest",
    "InstanceEnqueueResult",
    "InstanceTerminalResult",
    "InstanceTerminalState",
    "VoiceEnqueueResult",
    "VoiceTerminalResult",
    "VoiceTerminalState",
    "instance_id_from_payload",
    "terminal_result_from_payload",
]
