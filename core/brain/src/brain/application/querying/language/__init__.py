# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Language-specific query matching definitions."""

from __future__ import annotations

# Standard Libraries Imports
import difflib
import re
from types import ModuleType
import unicodedata

# Application Modules Imports
from brain.application.querying.language import en, es


LANGUAGE_MATCHERS = (en, es)
"""Language modules used by deterministic deep-query parsing."""


def normalize_query_text(value: str) -> str:
    """
    Normalize multilingual query text for deterministic comparisons.

    Args:
        value (str): Raw text value.

    Returns:
        str: Casefolded, accent-folded, whitespace-normalized text.
    """
    decomposed: str = unicodedata.normalize("NFKD", value.casefold())
    ascii_text: str = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(ascii_text.split())


def query_stop_words() -> set[str]:
    """
    Return normalized stopwords from every supported language module.

    Returns:
        set[str]: Stopwords used for deterministic query keyword extraction.
    """
    return {
        normalize_query_text(value=word)
        for matcher in LANGUAGE_MATCHERS
        for word in matcher.STOP_WORDS
    }


def temporal_words() -> set[str]:
    """
    Return normalized temporal words from every supported language module.

    Returns:
        set[str]: Temporal tokens excluded from retrieval keywords.
    """
    return {
        normalize_query_text(value=word)
        for matcher in LANGUAGE_MATCHERS
        for word in matcher.DATE_WORDS
    }


def query_segment_pattern() -> re.Pattern[str]:
    """
    Build the multilingual broad-query segmentation pattern.

    Returns:
        re.Pattern[str]: Regex matching language connectors and neutral punctuation.
    """
    connector_words: list[str] = sorted(
        {
            word
            for matcher in LANGUAGE_MATCHERS
            for word in matcher.QUERY_SEGMENT_WORDS
        },
        key=len,
        reverse=True,
    )
    connector_pattern: str = "|".join(re.escape(word) for word in connector_words)
    return re.compile(rf"\s+(?:{connector_pattern})\s+|[,;?]+", re.IGNORECASE)


def find_language_text_matches(line: str, query: str, threshold: float = 0.75) -> list[tuple[str, int, int]]:
    """
    Find language-aware fuzzy token or phrase matches in one text line.

    Args:
        line (str): Candidate content line.
        query (str): User query text.
        threshold (float): Minimum fuzzy ratio required for one match.

    Returns:
        list[tuple[str, int, int]]: Matched text spans as `(text, start, end)`.
    """
    matches: list[tuple[str, int, int]] = []
    seen: set[tuple[int, int, str]] = set()
    for matcher in LANGUAGE_MATCHERS:
        for match_text, start_index, end_index in find_text_matches_for_language(
            matcher=matcher,
            line=line,
            query=query,
            threshold=threshold,
        ):
            key: tuple[int, int, str] = (start_index, end_index, match_text)
            if key in seen:
                continue
            seen.add(key)
            matches.append((match_text, start_index, end_index))
    return matches


def find_text_matches_for_language(
    matcher: ModuleType,
    line: str,
    query: str,
    threshold: float,
) -> list[tuple[str, int, int]]:
    """
    Find text matches with the token pattern declared by one language module.

    Args:
        matcher (ModuleType): Language module with a `TEXT_TOKEN_PATTERN`.
        line (str): Candidate content line.
        query (str): User query text.
        threshold (float): Minimum fuzzy ratio required for one match.

    Returns:
        list[tuple[str, int, int]]: Matched text spans.
    """
    query_words: list[str] = normalize_query_text(value=query).split()
    if not query_words:
        return []

    matches: list[tuple[str, int, int]] = []
    tokens: list[re.Match[str]] = list(matcher.TEXT_TOKEN_PATTERN.finditer(line))
    if len(query_words) == 1:
        return find_single_word_matches(tokens=tokens, query_word=query_words[0], threshold=threshold)

    query_text: str = " ".join(query_words)
    phrase_size: int = len(query_words)
    for index in range(len(tokens) - phrase_size + 1):
        window_tokens: list[re.Match[str]] = tokens[index:index + phrase_size]
        window_text: str = line[window_tokens[0].start():window_tokens[-1].end()]
        ratio: float = difflib.SequenceMatcher(
            None,
            query_text,
            normalize_query_text(value=window_text),
        ).ratio()
        if ratio >= threshold:
            matches.append((window_text, window_tokens[0].start(), window_tokens[-1].end()))
    return matches


def find_single_word_matches(
    tokens: list[re.Match[str]],
    query_word: str,
    threshold: float,
) -> list[tuple[str, int, int]]:
    """
    Find one-token fuzzy matches from language-specific token spans.

    Args:
        tokens (list[re.Match[str]]): Candidate token spans.
        query_word (str): Normalized query word.
        threshold (float): Minimum fuzzy ratio required for one match.

    Returns:
        list[tuple[str, int, int]]: Matched text spans.
    """
    matches: list[tuple[str, int, int]] = []
    for token in tokens:
        word: str = token.group(0)
        ratio: float = difflib.SequenceMatcher(
            None,
            query_word,
            normalize_query_text(value=word),
        ).ratio()
        if ratio >= threshold:
            matches.append((word, token.start(), token.end()))
    return matches


def language_match_ratio(match_text: str, query: str) -> float:
    """
    Return fuzzy similarity for a language-normalized text match.

    Args:
        match_text (str): Matched text span.
        query (str): User query text.

    Returns:
        float: Similarity ratio from 0.0 to 1.0.
    """
    return difflib.SequenceMatcher(
        None,
        normalize_query_text(value=query),
        normalize_query_text(value=match_text),
    ).ratio()
