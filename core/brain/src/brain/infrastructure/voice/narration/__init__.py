"""Speech narration normalization and prompt infrastructure."""

from brain.infrastructure.voice.narration.markdown_narration import (
    markdown_text_for_speech,
    normalize_avatar_message_text,
)
from brain.infrastructure.voice.narration.narration_prompts import SPANISH_NARRATION_SYSTEM_PROMPT

__all__ = [
    "SPANISH_NARRATION_SYSTEM_PROMPT",
    "markdown_text_for_speech",
    "normalize_avatar_message_text",
]