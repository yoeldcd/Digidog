# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Search scoring helpers for knowledge graph read models."""

from __future__ import annotations

# Standard Libraries Imports
import difflib
from typing import Any

# Application Modules Imports
from brain.application.knowledge.models.ontology_keys import normalize_label


def build_fts_query(text: str) -> str:
    """
    Build a safe FTS5 query from user text.

    Args:
        text (str): Raw search text.

    Returns:
        str: Tokenized FTS5 query.
    """
    tokens: list[str] = [
        token.replace('"', "")
        for token in normalize_label(text).split()
        if token.replace("_", "").replace("-", "").isalnum()
    ]
    if not tokens:
        return '""'
    quoted_tokens: list[str] = [f'"{token}"' for token in tokens[:8]]
    return " OR ".join(quoted_tokens)


def _query_tokens(text: str) -> list[str]:
    """
    Return normalized query tokens.

    Args:
        text: Raw query text.

    Returns:
        list[str]: Search tokens.
    """
    return [
        token
        for token in normalize_label(text).split()
        if len(token) > 1
    ]


def _score_values(tokens: list[str], values: list[Any]) -> float:
    """
    Score query tokens against arbitrary graph text values.

    Args:
        tokens: Normalized query tokens.
        values: Candidate values.

    Returns:
        float: Score in the 0..1 range.
    """
    haystack: str = normalize_label(" ".join(str(value or "") for value in values))
    if not tokens or not haystack:
        return 0.0
    token_hits: int = sum(1 for token in tokens if token in haystack)
    minimum_hits: int = 2 if len(tokens) >= 4 else 1
    overlap_score: float = token_hits / len(tokens)
    fuzzy_score: float = difflib.SequenceMatcher(None, " ".join(tokens), haystack[:240]).ratio()
    if token_hits < minimum_hits and fuzzy_score < 0.36:
        return 0.0
    return min(1.0, max(overlap_score, fuzzy_score))


def _assertion_search_text(assertions: list[dict[str, Any]]) -> str:
    """
    Build searchable text from entity type assertions.

    Args:
        assertions (list[dict[str, Any]]): Type assertion payloads.

    Returns:
        str: Compact search text.
    """
    return " ".join(
        " ".join(
            (
                str(assertion.get("entity_class") or ""),
                str(assertion.get("description") or ""),
                str(assertion.get("source_path") or ""),
            ),
        )
        for assertion in assertions
    )
