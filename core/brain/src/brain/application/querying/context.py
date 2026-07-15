"""Deep query context extraction, keyword selection, and date parsing."""

from __future__ import annotations

# Standard Libraries Imports
from datetime import datetime, time, timedelta
import re

# Application Modules Imports
from brain.application.querying.dtos import QueryContextDTO, QueryDateConstraintDTO
from brain.application.querying.language import LANGUAGE_MATCHERS, normalize_query_text, query_stop_words, temporal_words
from brain.application.querying.selectors import QUERY_TOKEN_PATTERN


ISO_DATE_PATTERN = re.compile(r"\b(?P<year>20\d{2})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")
DMY_DATE_PATTERN = re.compile(r"\b(?P<day>\d{1,2})[-/](?P<month>\d{1,2})[-/](?P<year>20\d{2})\b")


def build_query_context(text: str, as_of: datetime | None = None) -> QueryContextDTO:
    """
    Build structured retrieval context for one deep query.

    Args:
        text (str): Raw user query.
        as_of (datetime | None): Optional deterministic clock value.

    Returns:
        QueryContextDTO: Normalized context with keywords and dates.
    """
    resolved_as_of: datetime = as_of or datetime.now().astimezone()
    date_constraints: list[QueryDateConstraintDTO] = parse_query_dates(text=text, as_of=resolved_as_of)
    return QueryContextDTO(
        query=text,
        as_of=resolved_as_of.isoformat(),
        timezone=str(resolved_as_of.tzinfo or ""),
        keywords=extract_query_keywords(text=text),
        date_constraints=date_constraints,
    )


def extract_query_keywords(text: str) -> list[str]:
    """
    Extract deterministic, non-temporal keywords from a query.

    Args:
        text (str): Raw user query.

    Returns:
        list[str]: Significant keywords in first-seen order.
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
        if normalized_token in temporal_words():
            continue
        if len(normalized_token) <= 2 and not any(symbol in token for symbol in (".", "/", "_", "-", "@", "#")):
            continue
        seen.add(normalized_token)
        terms.append(token)
    return terms


def parse_query_dates(text: str, as_of: datetime) -> list[QueryDateConstraintDTO]:
    """
    Parse supported absolute and relative dates from a query.

    Args:
        text (str): Raw user query.
        as_of (datetime): Clock used for relative phrases.

    Returns:
        list[QueryDateConstraintDTO]: Date constraints in query order.
    """
    constraints: list[QueryDateConstraintDTO] = []
    seen: set[tuple[str, str, str]] = set()
    append_time_bucket_constraints(text=text, as_of=as_of, constraints=constraints, seen=seen)
    append_absolute_date_constraints(text=text, constraints=constraints, seen=seen)
    append_relative_day_constraints(text=text, as_of=as_of, constraints=constraints, seen=seen)
    append_weekday_constraints(text=text, as_of=as_of, constraints=constraints, seen=seen)
    return constraints


def append_time_bucket_constraints(
    text: str,
    as_of: datetime,
    constraints: list[QueryDateConstraintDTO],
    seen: set[tuple[str, str, str]],
) -> None:
    """Append supported time-bucket constraints."""
    normalized_text: str = normalize_query_text(value=text)
    for matcher in LANGUAGE_MATCHERS:
        for phrase, (start_time, end_time, label) in matcher.TIME_BUCKETS.items():
            normalized_phrase: str = normalize_query_text(value=phrase)
            if normalized_phrase not in normalized_text:
                continue
            start_dt: datetime = datetime.combine(as_of.date(), start_time, tzinfo=as_of.tzinfo)
            end_dt: datetime = datetime.combine(as_of.date(), end_time, tzinfo=as_of.tzinfo)
            append_constraint(
                constraints=constraints,
                seen=seen,
                raw=phrase,
                label=f"{as_of.date().isoformat()} {label}",
                start=start_dt,
                end=end_dt,
                granularity="time_bucket",
            )


def append_absolute_date_constraints(
    text: str,
    constraints: list[QueryDateConstraintDTO],
    seen: set[tuple[str, str, str]],
) -> None:
    """Append ISO and day-month-year date constraints."""
    for match in ISO_DATE_PATTERN.finditer(text):
        append_date_match(match=match, constraints=constraints, seen=seen)
    for match in DMY_DATE_PATTERN.finditer(text):
        append_date_match(match=match, constraints=constraints, seen=seen)


def append_date_match(
    match: re.Match[str],
    constraints: list[QueryDateConstraintDTO],
    seen: set[tuple[str, str, str]],
) -> None:
    """Append one regex date match when it is valid."""
    try:
        date_dt = datetime(
            year=int(match.group("year")),
            month=int(match.group("month")),
            day=int(match.group("day")),
        )
    except ValueError:
        return
    append_day_constraint(
        constraints=constraints,
        seen=seen,
        raw=match.group(0),
        label=date_dt.date().isoformat(),
        date_dt=date_dt,
        granularity="date",
    )


def append_relative_day_constraints(
    text: str,
    as_of: datetime,
    constraints: list[QueryDateConstraintDTO],
    seen: set[tuple[str, str, str]],
) -> None:
    """Append relative day constraints such as today and ayer."""
    normalized_text: str = normalize_query_text(value=text)
    time_bucket_phrases: set[str] = {
        normalize_query_text(value=phrase)
        for matcher in LANGUAGE_MATCHERS
        for phrase in matcher.TIME_BUCKETS
    }
    for matcher in LANGUAGE_MATCHERS:
        for word, offset in matcher.RELATIVE_DAY_OFFSETS.items():
            normalized_word: str = normalize_query_text(value=word)
            if any(phrase in normalized_text and normalized_word in phrase.split() for phrase in time_bucket_phrases):
                continue
            if not re.search(rf"\b{re.escape(normalized_word)}\b", normalized_text):
                continue
            date_dt: datetime = as_of + timedelta(days=offset)
            append_day_constraint(
                constraints=constraints,
                seen=seen,
                raw=word,
                label=date_dt.date().isoformat(),
                date_dt=date_dt,
                granularity="day",
            )


def append_weekday_constraints(
    text: str,
    as_of: datetime,
    constraints: list[QueryDateConstraintDTO],
    seen: set[tuple[str, str, str]],
) -> None:
    """Append most-recent weekday constraints."""
    normalized_text: str = normalize_query_text(value=text)
    for matcher in LANGUAGE_MATCHERS:
        for word, weekday_index in matcher.WEEKDAY_INDEXES.items():
            normalized_word: str = normalize_query_text(value=word)
            if not re.search(rf"\b{re.escape(normalized_word)}\b", normalized_text):
                continue
            days_back: int = (as_of.weekday() - weekday_index) % 7
            date_dt: datetime = as_of - timedelta(days=days_back)
            append_day_constraint(
                constraints=constraints,
                seen=seen,
                raw=word,
                label=date_dt.date().isoformat(),
                date_dt=date_dt,
                granularity="weekday",
            )


def append_day_constraint(
    constraints: list[QueryDateConstraintDTO],
    seen: set[tuple[str, str, str]],
    raw: str,
    label: str,
    date_dt: datetime,
    granularity: str,
) -> None:
    """Append a full-day constraint."""
    start_dt: datetime = datetime.combine(date_dt.date(), time.min, tzinfo=date_dt.tzinfo)
    end_dt: datetime = datetime.combine(date_dt.date(), time.max.replace(microsecond=0), tzinfo=date_dt.tzinfo)
    append_constraint(
        constraints=constraints,
        seen=seen,
        raw=raw,
        label=label,
        start=start_dt,
        end=end_dt,
        granularity=granularity,
    )


def append_constraint(
    constraints: list[QueryDateConstraintDTO],
    seen: set[tuple[str, str, str]],
    raw: str,
    label: str,
    start: datetime,
    end: datetime,
    granularity: str,
) -> None:
    """Append one normalized date constraint if it is unique."""
    key: tuple[str, str, str] = (normalize_query_text(value=raw), start.isoformat(), end.isoformat())
    if key in seen:
        return
    seen.add(key)
    constraints.append(
        QueryDateConstraintDTO(
            raw=raw,
            label=label,
            start=start.isoformat(),
            end=end.isoformat(),
            granularity=granularity,
        ),
    )
