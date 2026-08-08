# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

'Voice avatar text normalization and processing-status contracts.'

from brain.infrastructure.voice.daemon.daemon import VoiceMemory
from brain.infrastructure.voice.narration.markdown_narration import normalize_avatar_message_text
from brain.infrastructure.voice.service.voice_service import clean_text_for_speech


def test_avatar_text_restores_escaped_word_prefix_controls() -> None:
    """Control sequences embedded before words recover their missing prefix."""
    source = "t541: \thinking; \application; \build; \verify; \format"

    normalized = normalize_avatar_message_text(source)

    assert normalized == "t541: thinking; application; build; verify; format"
    assert clean_text_for_speech(source) == normalized


def test_avatar_text_preserves_lines_and_removes_other_c0_controls() -> None:
    """Line structure remains stable while unsafe controls become whitespace."""
    source = "first\nsecond\x00third\r\nfourth"


    assert normalize_avatar_message_text(source) == "first\nsecond third\r\nfourth"


def test_voice_memory_exposes_independent_processing_activity() -> None:
    """Synthesis activity remains visible without replacing playback state."""
    memory = VoiceMemory()
    memory.set_state("speaking", "Mensaje activo", "happy")

    memory.begin_processing("speak-next", "focused")

    assert memory.status()["state"] == "speaking"
    assert memory.status()["processing"] is True
    assert memory.status()["processingEmotion"] == "focused"
    memory.finish_processing("speak-next")
    assert memory.status()["processing"] is False
    assert memory.status()["processingEmotion"] == ""
