# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Source registry domain DTOs and callable contracts."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Callable

# Third-party Libraries Imports
from pydantic import BaseModel, ConfigDict, Field


DEFAULT_IGNORED_NAMES: frozenset[str] = frozenset({".ignore", ".gitkeep", "index.md"})
"""Filesystem names ignored by source scans."""


class SourceRegistryRecordDTO(BaseModel):
    """
    Data transfer object for one source file registered in `brain_sources.db`.

    Attributes:
        id: Optional registry row identifier.
        path: Stable source path.
        mtime: Filesystem modification timestamp.
        size: Human-readable file size.
        lines: Human-readable line count.
        entries: Lightweight entry count.
        source_type: Source family.
        title: Human-readable source title.
        active: Whether the source currently exists.
    """

    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(default=None)
    path: str = Field(...)
    mtime: float = Field(default=0.0)
    size: str = Field(default="0KB")
    lines: str = Field(default="0")
    entries: int = Field(default=0)
    source_type: str = Field(default="")
    title: str = Field(default="")
    active: bool = Field(default=True)


class SourceRegistryCheckDTO(BaseModel):
    """
    Data transfer object for refreshing or comparing a source registry.

    Attributes:
        registry_path: SQLite source registry path.
        scanned: Number of source records discovered.
        changed: Source records changed for the selected consumer.
        deleted: Source paths that disappeared from the scanned source tree.
    """

    model_config = ConfigDict(extra="forbid")

    registry_path: str = Field(default="")
    scanned: int = Field(default=0)
    changed: list[SourceRegistryRecordDTO] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)


SourceTypeResolver = Callable[[str], str]
"""Callable that maps stable source paths to source family labels."""
