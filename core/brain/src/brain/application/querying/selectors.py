# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Deterministic selectors and constants for global query routing."""

from __future__ import annotations

# Standard Libraries Imports
import re


QUERY_SOURCE_VALUES: set[str] = {"all", "memory", "knowledge"}
"""Supported global query sources."""

QUERY_MECHANISM_VALUES: set[str] = {"all", "graph", "vector", "text"}
"""Supported global query mechanisms."""

MAX_DEEP_SUBQUERIES = 5
"""Maximum number of segmented retrieval passes used by deep mode."""

MAX_DEEP_EVIDENCE_RESULTS = 12
"""Maximum deduplicated evidence rows retained for one deep answer."""

QUERY_TOKEN_PATTERN = re.compile(r"[\w@#./-]+", re.UNICODE)
"""Token pattern that preserves filenames, paths, handles, and dotted identifiers."""

QUOTED_QUERY_PATTERN = re.compile(r'"([^"]+)"|`([^`]+)`')
"""Quoted or backticked phrases that should become focused subqueries."""
