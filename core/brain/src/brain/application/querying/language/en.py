"""English query matcher definitions."""

from __future__ import annotations

# Standard Libraries Imports
from datetime import time
import re


DATE_WORDS: set[str] = {
    "today",
    "tomorrow",
    "yesterday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "this",
    "morning",
}
"""English temporal tokens excluded from retrieval keywords."""

QUERY_SEGMENT_WORDS: tuple[str, ...] = (
    "and",
    "or",
    "with",
    "about",
    "for",
    "vs",
    "versus",
)
"""English connector words that can split broad query requests."""

STOP_WORDS: set[str] = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "from",
    "is",
    "of",
    "the",
    "to",
}
"""English stopwords ignored during deterministic keyword extraction."""

RELATIVE_DAY_OFFSETS: dict[str, int] = {
    "today": 0,
    "yesterday": -1,
    "tomorrow": 1,
}
"""English relative day terms."""

WEEKDAY_INDEXES: dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
"""English weekday terms mapped to Python weekday indexes."""

TIME_BUCKETS: dict[str, tuple[time, time, str]] = {
    "this morning": (time(6, 0, 0), time(11, 59, 59), "morning"),
}
"""English relative time buckets."""

TEXT_TOKEN_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)
"""English text token pattern for direct memory text matching."""
