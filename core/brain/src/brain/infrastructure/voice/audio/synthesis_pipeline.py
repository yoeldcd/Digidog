"""Synthesize speech, sanitize provider text, and cache paid audio in memory.

File: core/brain/src/brain/infrastructure/voice/audio/synthesis_pipeline.py

Author: Yoel David <yoeldcd@gmail.com>
X: https://x.com/SAY6267
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Callable, Protocol

from brain.infrastructure.avatar.configuration.avatar_config import load_avatar_config
from brain.infrastructure.voice.audio.engines import LocalPlayback, get_engine
from brain.infrastructure.voice.narration.markdown_narration import markdown_text_for_speech


class AudioCache(Protocol):
    """Define the retained paid-audio operations required by synthesis.

    Implementations retain bytes only for the active daemon lifetime.
    """

    def cached_audio(self, cache_key: str) -> bytes | None:
        """Return cached audio for a stable request hash.

        Args:
            cache_key: Stable paid-synthesis request hash.

        Returns:
            bytes | None: Retained audio, or ``None`` when absent.
        """

    def retain_cached_audio(self, cache_key: str, audio: bytes) -> None:
        """Retain provider audio for a stable request hash.

        Args:
            cache_key: Stable paid-synthesis request hash.
            audio: In-memory audio returned by a paid provider.
        """


def semantic_speech_chunks(text: str, limit: int = 2000) -> list[str]:
    """Split narration into ordered bounded chunks, preferring semantic boundaries.

    Args:
        text: Narration text to partition.
        limit: Maximum character count for each retained chunk. Defaults to 2000.

    Returns:
        list[str]: Ordered, trimmed narration chunks.
    """

    remaining = text.strip()
    chunks: list[str] = []

    if limit <= 0:
        limit = 2000

    while remaining:

        if len(remaining) <= limit:
            chunks.append(remaining)

            break

        window = remaining[:limit]
        cut = -1

        # 1. Paragraph boundary: double newline (\n\n)
        para_end = window.rfind("\n\n")

        if para_end >= 0:
            cut = para_end + 2

        if cut < 0:
            # 2. Single newline boundary (\n)
            newline_end = window.rfind("\n")

            if newline_end >= 0:
                cut = newline_end + 1

        if cut < 0:
            # 3. Sentence boundary: (. ! ? followed by optional quote/paren then space or end)
            sentence_matches = list(re.finditer(r'[.!?]["\'»\)]?(?:\s+|\Z)', window))

            if sentence_matches:
                cut = sentence_matches[-1].end()

        if cut < 0 or cut > limit:
            # 4. Clause / punctuation boundary (;, :, ,, - followed by space or end)
            clause_matches = list(re.finditer(r'[;,:-](?:\s+|\Z)', window))

            if clause_matches:
                cut = clause_matches[-1].end()

        if cut < 0 or cut > limit:
            # 5. Space boundary (word boundary)
            space_pos = window.rfind(" ")

            if space_pos > 0:
                cut = space_pos + 1

        if cut <= 0 or cut > limit:
            # 6. Hard cut fallback if an unbroken token exceeds limit
            cut = limit

        chunk = remaining[:cut].strip()

        if chunk:
            chunks.append(chunk)

        remaining = remaining[cut:].strip()

    return chunks


def paid_synthesis_cache_key(
    request: dict[str, str],
    *,
    config_loader: Callable = load_avatar_config,
) -> str:
    """Build a stable cache key for paid synthesis inputs.

    Args:
        request: Canonical voice request.
        config_loader: Configuration loader supplying active engine options.

    Returns:
        str: Stable request hash, or an empty string for local engines.
    """

    config = config_loader()
    engine_name = config.active_voice_engine

    if engine_name not in {"openai", "elevenlabs"}:
        return ""

    engine_config = getattr(config.voice_engines, engine_name).model_dump()
    engine_config.pop("api_key", None)

    identity = {
        "engine": engine_name,
        "engineConfig": engine_config,
        "lang": request.get("lang", "es"),
        "text": markdown_text_for_speech(request.get("text", "")),
    }

    serialized = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def synthesize(
    request: dict[str, str],
    *,
    config_loader: Callable = load_avatar_config,
    edge_synthesizer: Callable | None = None,
) -> bytes | LocalPlayback:
    """Prepare a paid audio payload or deferred local playback request.

    Args:
        request: Canonical voice request.
        config_loader: Configuration loader that supplies the active engine.
        edge_synthesizer: Awaitable Edge synthesis callable, when overridden.

    Returns:
        bytes | LocalPlayback: In-memory provider audio or local playback spec.

    Raises:
        RuntimeError: If Edge voice is unconfigured or synthesis fails.
        Exception: If the configured remote provider rejects synthesis.
    """

    import requests

    edge_synthesizer = edge_synthesizer or _synthesize_edge_audio
    config = config_loader()
    engine_name = config.active_voice_engine
    engine_config = getattr(config.voice_engines, engine_name).model_dump()

    text = sanitize_engine_text(markdown_text_for_speech(request["text"]), engine_config)
    requested_language = str(request.get("lang", "es")).strip().casefold()
    lang = requested_language.split("-", 1)[0] or "es"

    if engine_name == "edge":
        configured_voice = str(engine_config.get("voices", {}).get(lang, "")).strip()

        if not configured_voice:
            raise RuntimeError(f"No Edge voice is configured for language `{lang}`.")

        voice = configured_voice

        if not configured_voice.endswith("Neural"):
            voice = f"{configured_voice}Neural"

        try:
            return asyncio.run(
                edge_synthesizer(
                    text=text,
                    voice=voice,
                    rate=str(engine_config.get("rate", "+0%")),
                    volume=str(engine_config.get("volume", "+0%")),
                    pitch=str(engine_config.get("pitch", "+0Hz")),
                )
            )
        except Exception as exc:
            raise RuntimeError(
                f"Edge synthesis failed for configured voice `{voice}` and language `{lang}`."
            ) from exc

    if engine_name == "elevenlabs":
        voice = engine_config.get("voices", {}).get(lang, engine_config.get("voice_id"))

        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            headers={
                "xi-api-key": engine_config.get("api_key", ""),
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": engine_config.get("model_id", "eleven_multilingual_v2"),
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=60,
        )

        response.raise_for_status()

        return response.content

    if engine_name == "openai":
        voice = engine_config.get("voices", {}).get(lang, engine_config.get("voice", "shimmer"))

        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {engine_config.get('api_key', '')}",
                "Content-Type": "application/json",
            },
            json={
                "model": engine_config.get("model", "tts-1"),
                "input": text,
                "voice": voice,
            },
            timeout=60,
        )

        response.raise_for_status()

        return response.content

    return get_engine(engine_name, engine_config).prepare(text=text, lang=lang)


def sanitize_engine_text(text: str, engine_config: dict[str, object]) -> str:
    """Apply an engine-owned regex to a spoken text projection.

    Args:
        text: Plain narration text.
        engine_config: Engine configuration with optional sanitization regex.

    Returns:
        str: Sanitized text, or the original text for invalid regexes.
    """

    pattern = str(engine_config.get("sanitization_regex", "")).strip()

    if not pattern:
        return text

    try:
        sanitized = re.sub(pattern, " ", text)
    except re.error:
        return text

    return re.sub(r"\s+", " ", sanitized).strip()


async def _synthesize_edge_audio(
    text: str,
    voice: str,
    rate: str = "+0%",
    volume: str = "+0%",
    pitch: str = "+0Hz",
) -> bytes:
    """Collect one Microsoft Edge Neural stream entirely in memory.

    Args:
        text: Sanitized narration text.
        voice: Fully qualified Edge Neural voice name.
        rate: Provider speech-rate adjustment.
        volume: Provider volume adjustment.
        pitch: Provider pitch adjustment.

    Returns:
        bytes: Complete in-memory provider audio stream.

    Raises:
        RuntimeError: If the provider emits no audio chunks.
    """

    import edge_tts

    chunks: list[bytes] = []
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
    )

    async for chunk in communicate.stream():

        if chunk.get("type") == "audio":
            chunks.append(chunk["data"])

    audio = b"".join(chunks)

    if not audio:
        raise RuntimeError(f"Edge returned no audio for voice `{voice}`.")

    return audio


def synthesize_or_reuse(
    memory: AudioCache,
    request: dict[str, str],
    *,
    synthesize_fn: Callable = synthesize,
    config_loader: Callable = load_avatar_config,
) -> bytes | LocalPlayback:
    """Reuse paid audio by hash before requesting provider synthesis.

    Args:
        memory: Audio cache owned by the voice daemon.
        request: Canonical voice request.
        synthesize_fn: Provider-synthesis callable used after a cache miss.
        config_loader: Configuration loader used to derive a paid-audio key.

    Returns:
        bytes | LocalPlayback: Cached or newly synthesized audio representation.
    """

    cache_key = paid_synthesis_cache_key(request, config_loader=config_loader)
    cached = memory.cached_audio(cache_key) if cache_key else None

    if cached is not None:
        return cached

    result = synthesize_fn(request)

    if isinstance(result, bytes) and cache_key:
        memory.retain_cached_audio(cache_key, result)

    return result
