# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Models and constants for knowledge source processing."""

from __future__ import annotations

# Standard Libraries Imports
from dataclasses import dataclass
from pathlib import Path

# Application Modules Imports
from brain.application.knowledge.models.dtos.sources import SourceDTO


SOURCE_DOMAINS: set[str] = {
    "all",
    "memory",
    "diary",
    "logs",
    "profiles",
}
"""Supported source domains for knowledge dream runs."""

WORKSPACE_LOG_SOURCE_TYPE = "workspace_logs"
"""Persistent source type used for repository-local log files."""

KNOWLEDGE_CONSUMER_NAME = "knowledge_graph"
"""Consumer namespace used in source registry state."""


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    """Discovered source candidate with external update metadata."""

    source_dto: SourceDTO
    path: Path
    mtime: float
