"""Voice synthesis, playback, and audio persistence infrastructure."""

from brain.infrastructure.voice.audio.audio_store import AudioStoreMixin
from brain.infrastructure.voice.audio.engines import (
    BaseTtsEngine,
    EdgeTtsEngine,
    ElevenLabsTtsEngine,
    LocalPlayback,
    OpenAiTtsEngine,
    PlaybackProcess,
    Pyttsx3Engine,
    get_engine,
    play_audio_file,
    play_audio_url,
)
from brain.infrastructure.voice.audio.synthesis_pipeline import (
    paid_synthesis_cache_key,
    sanitize_engine_text,
    semantic_speech_chunks,
    synthesize,
    synthesize_or_reuse,
)
from brain.infrastructure.voice.audio.voice_persistence import (
    PersistenceRuntime,
    consume_persistence_requests,
    enqueue_message_persistence,
)

__all__ = [
    "AudioStoreMixin",
    "BaseTtsEngine",
    "EdgeTtsEngine",
    "ElevenLabsTtsEngine",
    "LocalPlayback",
    "OpenAiTtsEngine",
    "PersistenceRuntime",
    "PlaybackProcess",
    "Pyttsx3Engine",
    "consume_persistence_requests",
    "enqueue_message_persistence",
    "get_engine",
    "paid_synthesis_cache_key",
    "play_audio_file",
    "play_audio_url",
    "sanitize_engine_text",
    "semantic_speech_chunks",
    "synthesize",
    "synthesize_or_reuse",
]