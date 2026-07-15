"""Spanish query matcher definitions."""

from __future__ import annotations

# Standard Libraries Imports
from datetime import time
import re


DATE_WORDS: set[str] = {
    "hoy",
    "manana",
    "mañana",
    "ayer",
    "lunes",
    "martes",
    "miercoles",
    "miércoles",
    "jueves",
    "viernes",
    "sabado",
    "sábado",
    "domingo",
    "esta",
}
"""Spanish temporal tokens excluded from retrieval keywords."""

QUERY_SEGMENT_WORDS: tuple[str, ...] = (
    "y",
    "o",
    "con",
    "sobre",
    "para",
    "versus",
)
"""Spanish connector words that can split broad query requests."""

STOP_WORDS: set[str] = {
    "al",
    "como",
    "con",
    "de",
    "del",
    "el",
    "en",
    "la",
    "las",
    "le",
    "lo",
    "los",
    "me",
    "o",
    "para",
    "por",
    "que",
    "se",
    "sobre",
    "un",
    "una",
    "y",
}
"""Spanish stopwords ignored during deterministic keyword extraction."""

RELATIVE_DAY_OFFSETS: dict[str, int] = {
    "hoy": 0,
    "ayer": -1,
    "manana": 1,
    "mañana": 1,
}
"""Spanish relative day terms."""

WEEKDAY_INDEXES: dict[str, int] = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}
"""Spanish weekday terms mapped to Python weekday indexes."""

TIME_BUCKETS: dict[str, tuple[time, time, str]] = {
    "esta manana": (time(6, 0, 0), time(11, 59, 59), "morning"),
    "esta mañana": (time(6, 0, 0), time(11, 59, 59), "morning"),
}
"""Spanish relative time buckets."""

TEXT_TOKEN_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)
"""Spanish text token pattern for direct memory text matching."""
