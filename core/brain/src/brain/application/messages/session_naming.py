"""Intent-oriented naming for persisted message sessions."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from brain.application.querying.llm import request_query_json
from brain.infrastructure.messages.models import MessageRecordDTO


SESSION_NAME_SYSTEM_PROMPT = """You name work and conversation sessions from their transcript.
Return JSON only: {"name": "..."}.
The name must summarize the session's dominant intention, decision, or achieved outcome—not quote its opening words.
Use the transcript's language, concrete nouns, and an action or purpose when useful.
Avoid greetings, filler, speaker labels, dates, generic phrases such as 'conversation about', and unsupported claims.
Write between 3 and 10 words."""


def propose_session_name(
    records: list[MessageRecordDTO],
    requester: Callable[[str, str, int], dict[str, Any]] = request_query_json,
) -> str:
    """
    Generate one bounded session title from the session's dominant intention.

    Args:
        records: Chronological or reverse-chronological session transcript records.
        requester: JSON completion boundary used to generate the semantic title.

    Returns:
        A reviewable title containing at most ten words.

    Raises:
        ValueError: If the session has no records.
    """
    if not records:
        raise ValueError("Message session not found.")
    chronological: list[MessageRecordDTO] = sorted(records, key=lambda record: record.created_at)
    transcript: list[dict[str, str]] = [
        {"timestamp": record.created_at, "text": _plain_text(record.text)}
        for record in chronological
        if _plain_text(record.text)
    ]
    user_prompt: str = json.dumps(
        {
            "task": "Infer the dominant intention, decision, or outcome and name this session.",
            "transcript": transcript[-40:],
        },
        ensure_ascii=False,
    )
    try:
        payload: dict[str, Any] = requester(SESSION_NAME_SYSTEM_PROMPT, user_prompt, 80)
        candidate: str = _bounded_name(str(payload.get("name") or ""))
        if candidate:
            return candidate
    except (KeyError, RuntimeError, TypeError, ValueError):
        pass
    return _fallback_name(transcript=transcript)


def _plain_text(markdown: str) -> str:
    """Collapse Markdown decorations and whitespace for model context."""
    return " ".join(re.sub(r"[`*_#\[\]()>]", " ", markdown).split())


def _bounded_name(value: str) -> str:
    """Normalize a model candidate to the public ten-word title contract."""
    words: list[str] = re.findall(r"[\wÀ-ÿ'-]+", value, flags=re.UNICODE)
    return " ".join(words[:10]).strip()


def _fallback_name(transcript: list[dict[str, str]]) -> str:
    """Build a deterministic intent-shaped fallback when the text model is unavailable."""
    text: str = " ".join(item["text"] for item in transcript[-8:])
    clauses: list[str] = [part.strip() for part in re.split(r"[.!?;:\n]+", text) if part.strip()]
    intent_pattern = re.compile(
        r"\b(?:quiero|queremos|necesito|necesitamos|vamos a|hay que|debo|debemos|implement|correg|mejor|diseñ|cre|revis|audit)",
        re.IGNORECASE,
    )
    selected: str = next((clause for clause in reversed(clauses) if intent_pattern.search(clause)), clauses[-1] if clauses else "")
    bounded: str = _bounded_name(selected)
    return bounded or "Resumen de la sesión"
