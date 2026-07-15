"""Dream run DTOs for knowledge consolidation orchestration."""

from __future__ import annotations

# Third-party Libraries Imports
from pydantic import BaseModel, Field


class ConsolidationDecisionDTO(BaseModel):
    """
    Consolidation decision emitted by the dream pipeline.

    Attributes:
        action: Decision action such as `apply`, `skip`, `promote`, or `contest`.
        reason: Human-readable reason.
        entity_id: Optional related entity identifier.
        relation_id: Optional related relation identifier.
    """

    action: str = Field(...)
    reason: str = Field(default="")
    entity_id: int | None = Field(default=None)
    relation_id: int | None = Field(default=None)


class DreamRunDTO(BaseModel):
    """
    Summary of one cognitive consolidation run.

    Attributes:
        id: Optional database identifier.
        status: Run status.
        dry_run: Whether changes were only proposed.
        sources_seen: Number of changed sources inspected.
        deltas_proposed: Number of deltas generated.
        deltas_applied: Number of deltas applied.
        pending_delta_ids: Pending delta identifiers written for review.
        errors: Run errors.
        decisions: Consolidation decisions.
        summary: Human-readable run summary.
    """

    id: int | None = Field(default=None)
    status: str = Field(default="completed")
    dry_run: bool = Field(default=True)
    sources_seen: int = Field(default=0)
    deltas_proposed: int = Field(default=0)
    deltas_applied: int = Field(default=0)
    pending_delta_ids: list[int] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    decisions: list[ConsolidationDecisionDTO] = Field(default_factory=list)
    summary: str = Field(default="")
