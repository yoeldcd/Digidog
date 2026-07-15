"""Source, evidence, and framing DTOs for knowledge ingestion."""

from __future__ import annotations

# Third-party Libraries Imports
from pydantic import BaseModel, ConfigDict, Field


class SourceDTO(BaseModel):
    """
    Source document indexed into the knowledge graph.

    Attributes:
        id: Optional database identifier.
        source_type: Source family such as `memory`, `diary`, `profiles`, or `workspace_logs`.
        path: Stable relative path for the source.
        title: Human-readable source title.
        active: Whether the source is currently present.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None)
    source_type: str = Field(...)
    path: str = Field(...)
    title: str = Field(default="")
    active: bool = Field(default=True)


class EvidenceDTO(BaseModel):
    """
    Text evidence anchored to a source.

    Attributes:
        id: Optional database identifier.
        source_id: Parent source identifier.
        quote: Exact or near-exact quoted support text.
        location: Source-local line, section, or path hint.
        content_hash: SHA-256 digest of the quote.
        confidence: Evidence extraction confidence.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None)
    source_id: int = Field(...)
    quote: str = Field(...)
    location: str = Field(default="")
    content_hash: str = Field(default="")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class KnowledgeFrameDTO(BaseModel):
    """
    Semantic frame prepared by the harness before model extraction.

    Attributes:
        frame_kind: Semantic frame family.
        title: Human-readable frame title derived from content.
        body: Model-ready text without source paths or filesystem metadata.
        source_type: Internal source family used by the harness.
        original_chars: Character count of the raw source content.
    """

    model_config = ConfigDict(extra="forbid")

    frame_kind: str = Field(default="knowledge_record")
    """Semantic frame family."""

    title: str = Field(default="")
    """Human-readable frame title derived from content."""

    body: str = Field(default="")
    """Model-ready text without source paths or filesystem metadata."""

    source_type: str = Field(default="memory")
    """Internal source family used by the harness."""

    original_chars: int = Field(default=0, ge=0)
    """Character count of the raw source content."""
