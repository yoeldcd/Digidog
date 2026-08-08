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
    "messages",
    "profiles",
}
"""Supported source domains for knowledge dream runs."""

WORKSPACE_LOG_SOURCE_TYPE = "workspace_logs"
"""Persistent source type used for repository-local log files."""

WORKSPACE_MESSAGE_SOURCE_TYPE = "workspace_messages"
"""Persistent source type used for repository-local avatar messages."""

KNOWLEDGE_CONSUMER_NAME = "knowledge_graph"
"""Consumer namespace used in source registry state."""


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    """Discovered source candidate with external update metadata.

    Attributes:
        source_dto (SourceDTO): Registry-facing source identity and classification.
        path (Path): Absolute filesystem path used to read the source.
        mtime (float): Last-modified timestamp used for incremental discovery.
    """

    source_dto: SourceDTO
    path: Path
    mtime: float
