"""Subquery planning helpers for deep global query mode."""

from __future__ import annotations

# Standard Libraries Imports
from datetime import datetime

# Application Modules Imports
from brain.application.querying.context import build_query_context
from brain.application.querying.dtos import QueryContextDTO, QuerySubqueryDTO
from brain.application.querying.language import normalize_query_text, query_segment_pattern, query_stop_words
from brain.application.querying.selectors import (
    MAX_DEEP_SUBQUERIES,
    QUOTED_QUERY_PATTERN,
    QUERY_TOKEN_PATTERN,
)


def plan_deep_subqueries(
    text: str,
    context: QueryContextDTO | None = None,
    as_of: datetime | None = None,
) -> list[QuerySubqueryDTO]:
    """
    Build focused retrieval subqueries from a broad user query.

    Args:
        text (str): Raw user query.
        context (QueryContextDTO | None): Existing query context.
        as_of (datetime | None): Optional deterministic clock value.

    Returns:
        list[QuerySubqueryDTO]: Planned subqueries with context metadata.
    """
    query_context: QueryContextDTO = context or build_query_context(text=text, as_of=as_of)
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    normalized_text: str = normalize_query_phrase(text=text)
    append_subquery(candidates=candidates, seen=seen, text=normalized_text, reason="original query")

    for match in QUOTED_QUERY_PATTERN.finditer(normalized_text):
        quoted_text: str = next((group for group in match.groups() if group), "")
        append_subquery(candidates=candidates, seen=seen, text=quoted_text, reason="quoted focus")

    for segment in query_segment_pattern().split(normalized_text):
        append_subquery(candidates=candidates, seen=seen, text=segment, reason="query segment")

    keywords: list[str] = query_context.keywords or significant_query_terms(text=normalized_text)
    for keyword_segment in keyword_segments(terms=keywords):
        append_subquery(
            candidates=candidates,
            seen=seen,
            text=keyword_segment,
            reason="keyword segment",
        )
    if len(keywords) >= 2:
        append_subquery(
            candidates=candidates,
            seen=seen,
            text=" ".join(keywords[:6]),
            reason="keyword focus",
        )
    for constraint in query_context.date_constraints:
        date_focus: str = " ".join([*keywords[:4], constraint.raw]).strip()
        append_subquery(
            candidates=candidates,
            seen=seen,
            text=date_focus,
            reason=f"date focus: {constraint.label}",
        )

    return [
        QuerySubqueryDTO(
            index=index,
            text=subquery_text,
            reason=reason,
            keywords=list(keywords),
            date_constraints=query_context.date_constraints,
        )
        for index, (subquery_text, reason) in enumerate(candidates[:MAX_DEEP_SUBQUERIES], 1)
    ]


def append_subquery(
    candidates: list[tuple[str, str]],
    seen: set[str],
    text: str,
    reason: str,
) -> None:
    """
    Add one normalized subquery when it is usable and unique.

    Args:
        candidates (list[tuple[str, str]]): Mutable candidate list.
        seen (set[str]): Casefolded text already added.
        text (str): Candidate subquery text.
        reason (str): Planning reason.
    """
    normalized_text: str = normalize_query_phrase(text=text)
    if len(normalized_text) < 2:
        return
    seen_key: str = normalized_text.casefold()
    if seen_key in seen:
        return
    seen.add(seen_key)
    candidates.append((normalized_text, reason))


def normalize_query_phrase(text: str) -> str:
    """
    Normalize one query phrase without losing source-like tokens.

    Args:
        text (str): Raw phrase.

    Returns:
        str: Compact phrase.
    """
    return " ".join(text.strip().split())


def significant_query_terms(text: str) -> list[str]:
    """
    Extract deterministic keyword focus terms from a query.

    Args:
        text (str): Query text.

    Returns:
        list[str]: Significant tokens in original order.
    """
    terms: list[str] = []
    seen: set[str] = set()
    for raw_token in QUERY_TOKEN_PATTERN.findall(text):
        token: str = raw_token.strip(".,:;!?()[]{}")
        normalized_token: str = normalize_query_text(value=token)
        if not token:
            continue
        if normalized_token in seen or normalized_token in query_stop_words():
            continue
        if len(normalized_token) <= 2 and not any(symbol in token for symbol in (".", "/", "_", "-", "@", "#")):
            continue
        seen.add(normalized_token)
        terms.append(token)
    return terms


def keyword_segments(terms: list[str]) -> list[str]:
    """
    Build short keyword windows for queries without explicit separators.

    Args:
        terms (list[str]): Significant query terms.

    Returns:
        list[str]: Short keyword segments.
    """
    if len(terms) < 3:
        return []
    if len(terms) == 3:
        return [
            " ".join(terms[:2]),
            " ".join(terms[1:]),
        ]
    leading_segment: str = " ".join(terms[:3])
    trailing_segment: str = " ".join(terms[-3:])
    if leading_segment == trailing_segment:
        return [leading_segment]
    return [leading_segment, trailing_segment]
