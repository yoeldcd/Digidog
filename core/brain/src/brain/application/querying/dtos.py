"""Data transfer objects for global brain query results."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Third-party Libraries Imports
from pydantic import BaseModel, ConfigDict, Field


class QuerySourceRefDTO(BaseModel):
    """
    Structured source reference for a query result.

    Attributes:
        scope: Knowledge or runtime scope that owns the source.
        source_type: Source family.
        domain: Logical source domain.
        read_command: CLI command that reads this source.
        path: Stable source path.
        title: Human-readable source title.
        structure: Navigable path segments.
        line_number: Optional source-local line number.
    """

    model_config = ConfigDict(extra="forbid")

    scope: str = Field(default="")
    """Knowledge or runtime scope that owns the source."""

    source_type: str = Field(default="")
    """Source family."""

    domain: str = Field(default="")
    """Logical source domain."""

    read_command: str = Field(default="")
    """CLI command that reads this source."""

    path: str = Field(default="")
    """Stable source path."""

    title: str = Field(default="")
    """Human-readable source title."""

    structure: list[str] = Field(default_factory=list)
    """Navigable path segments."""

    line_number: int | None = Field(default=None)
    """Optional source-local line number."""


class QueryContentDTO(BaseModel):
    """
    Normalized content block for a query result.

    Attributes:
        title: Result title.
        excerpt: Reader-facing excerpt.
        body: Longer content body when safe and available.
        location: Source-local section or line hint.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="")
    """Result title."""

    excerpt: str = Field(default="")
    """Reader-facing excerpt."""

    body: str = Field(default="")
    """Longer content body when safe and available."""

    location: str = Field(default="")
    """Source-local section or line hint."""


class QueryEntityDTO(BaseModel):
    """
    Entity involved in a query result.

    Attributes:
        id: Optional entity identifier.
        entity_class: Entity type/class.
        name: Canonical entity name.
        description: Entity description.
        confidence: Confidence score.
        type_assertions: Source-scoped type assertions for the stable entity.
    """

    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(default=None)
    """Optional entity identifier."""

    entity_class: str = Field(default="")
    """Entity type/class."""

    name: str = Field(default="")
    """Canonical entity name."""

    description: str = Field(default="")
    """Entity description."""

    confidence: float = Field(default=0.0)
    """Confidence score."""

    type_assertions: list[dict[str, Any]] = Field(default_factory=list)
    """Source-scoped type assertions for the stable entity."""

    def __str__(self) -> str:
        """
        Render the entity with the shared graph object syntax.

        Returns:
            str: Compact entity string.
        """
        return f'[{self.entity_class or "entity"}:"{self.name}"]'


class QueryRelationDTO(BaseModel):
    """
    Relation involved in a query result.

    Attributes:
        id: Optional relation identifier.
        predicate: Relation predicate.
        subject: Subject entity.
        object: Object entity.
        confidence: Confidence score.
        source_path: Stable source path supporting the relation.
    """

    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(default=None)
    """Optional relation identifier."""

    predicate: str = Field(default="")
    """Relation predicate."""

    subject: QueryEntityDTO = Field(default_factory=QueryEntityDTO)
    """Subject entity."""

    object: QueryEntityDTO = Field(default_factory=QueryEntityDTO)
    """Object entity."""

    confidence: float = Field(default=0.0)
    """Confidence score."""

    source_path: str = Field(default="")
    """Stable source path supporting the relation."""

    def __str__(self) -> str:
        """
        Render the relation with the shared graph edge syntax.

        Returns:
            str: Compact relation string.
        """
        confidence_text: str = "1" if self.confidence >= 0.995 else f"{self.confidence:.2f}".lstrip("0")
        return f'{self.subject} - ("{self.predicate}" at {confidence_text}) -> {self.object}'


class QueryDateConstraintDTO(BaseModel):
    """
    Normalized temporal constraint detected in a query.

    Attributes:
        raw: Raw phrase detected in the user query.
        label: Human-readable normalized date or time label.
        start: Inclusive ISO datetime boundary.
        end: Inclusive ISO datetime boundary.
        granularity: Constraint precision such as day, date, or time_bucket.
    """

    model_config = ConfigDict(extra="forbid")

    raw: str = Field(default="")
    """Raw phrase detected in the user query."""

    label: str = Field(default="")
    """Human-readable normalized date or time label."""

    start: str = Field(default="")
    """Inclusive ISO datetime boundary."""

    end: str = Field(default="")
    """Inclusive ISO datetime boundary."""

    granularity: str = Field(default="")
    """Constraint precision such as day, date, or time_bucket."""


class QueryContextDTO(BaseModel):
    """
    Structured context derived from a deep query.

    Attributes:
        query: Original user query.
        as_of: ISO datetime used to resolve relative temporal phrases.
        timezone: Runtime timezone name or offset.
        keywords: Significant retrieval keywords.
        date_constraints: Normalized temporal constraints.
    """

    model_config = ConfigDict(extra="forbid")

    query: str = Field(default="")
    """Original user query."""

    as_of: str = Field(default="")
    """ISO datetime used to resolve relative temporal phrases."""

    timezone: str = Field(default="")
    """Runtime timezone name or offset."""

    keywords: list[str] = Field(default_factory=list)
    """Significant retrieval keywords."""

    date_constraints: list[QueryDateConstraintDTO] = Field(default_factory=list)
    """Normalized temporal constraints."""


class QueryMatchDTO(BaseModel):
    """
    Explanation of how one result matched a deep query.

    Attributes:
        keyword_hits: Query keywords found in the result.
        keyword_misses: Query keywords not found in the result.
        date_match: Temporal match status: none, matched, or missed.
        entity_match: Whether selected entities were present in the result.
        explanation: Reader-facing match explanation.
        adjusted_score: Deep-mode score where lower values rank earlier.
    """

    model_config = ConfigDict(extra="forbid")

    keyword_hits: list[str] = Field(default_factory=list)
    """Query keywords found in the result."""

    keyword_misses: list[str] = Field(default_factory=list)
    """Query keywords not found in the result."""

    date_match: str = Field(default="none")
    """Temporal match status: none, matched, or missed."""

    entity_match: bool = Field(default=False)
    """Whether selected entities were present in the result."""

    explanation: str = Field(default="")
    """Reader-facing match explanation."""

    adjusted_score: float = Field(default=0.0)
    """Deep-mode score where lower values rank earlier."""


class QuerySelectedEntityDTO(BaseModel):
    """
    Entity selected as important to a deep query.

    Attributes:
        id: Optional entity identifier.
        name: Canonical entity name.
        entity_class: Entity type/class.
        confidence: Selector confidence score.
        selector_source: Selector implementation: deterministic or llm.
    """

    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(default=None)
    """Optional entity identifier."""

    name: str = Field(default="")
    """Canonical entity name."""

    entity_class: str = Field(default="")
    """Entity type/class."""

    confidence: float = Field(default=0.0)
    """Selector confidence score."""

    selector_source: str = Field(default="deterministic")
    """Selector implementation: deterministic or llm."""


class GlobalQueryResultDTO(BaseModel):
    """
    Normalized result returned by the global `query` command.

    Attributes:
        source: Query backend that produced the result.
        mechanism: Search mechanism that produced the result.
        kind: Backend-specific result type.
        rank: Numeric ordering hint from the backend.
        title: Human-readable result title.
        text: Short excerpt mirrored from `content.excerpt`.
        data: Original backend payload.
        warning: Optional non-blocking warning text.
        content: Normalized result content block.
        source_ref: Structured source reference for the result.
        entities: Entities involved in the result.
        relations: Relations involved in the result.
    """

    model_config = ConfigDict(extra="forbid")

    source: str = Field(...)
    """Query backend that produced the result."""

    mechanism: str = Field(default="")
    """Search mechanism that produced the result."""

    kind: str = Field(...)
    """Backend-specific result type."""

    rank: float = Field(default=0.0)
    """Numeric ordering hint from the backend."""

    title: str = Field(default="")
    """Human-readable result title."""

    text: str = Field(default="")
    """Short excerpt mirrored from `content.excerpt`."""

    data: dict[str, Any] = Field(default_factory=dict)
    """Original backend payload."""

    warning: str = Field(default="")
    """Optional non-blocking warning text."""

    content: QueryContentDTO = Field(default_factory=QueryContentDTO)
    """Normalized result content block."""

    source_ref: QuerySourceRefDTO = Field(default_factory=QuerySourceRefDTO)
    """Structured source reference for the result."""

    entities: list[QueryEntityDTO] = Field(default_factory=list)
    """Entities involved in the result."""

    relations: list[QueryRelationDTO] = Field(default_factory=list)
    """Relations involved in the result."""

    match: QueryMatchDTO = Field(default_factory=QueryMatchDTO)
    """Deep-query match explanation."""


class QuerySubqueryDTO(BaseModel):
    """
    Planned query segment used by deep query mode.

    Attributes:
        index: Stable 1-based subquery index.
        text: Subquery text sent to the selected retrieval backends.
        reason: Short reason for why the segment was produced.
        results: Normalized matches returned for this subquery.
    """

    model_config = ConfigDict(extra="forbid")

    index: int = Field(...)
    """Stable 1-based subquery index."""

    text: str = Field(...)
    """Subquery text sent to the selected retrieval backends."""

    reason: str = Field(default="")
    """Short reason for why the segment was produced."""

    keywords: list[str] = Field(default_factory=list)
    """Keywords used to plan this segment."""

    date_constraints: list[QueryDateConstraintDTO] = Field(default_factory=list)
    """Temporal constraints attached to this segment."""

    results: list[GlobalQueryResultDTO] = Field(default_factory=list)
    """Normalized matches returned for this subquery."""


class QueryDeepResponseDTO(BaseModel):
    """
    Deep answer synthesized from segmented knowledgebase retrieval.

    Attributes:
        query: Original user query.
        answer: Deterministic contextual answer grounded in retrieved results.
        subqueries: Segments used to gather evidence.
        results: Deduplicated evidence results used by the answer.
        warnings: Non-blocking warning texts observed during retrieval.
    """

    model_config = ConfigDict(extra="forbid")

    query: str = Field(...)
    """Original user query."""

    answer: str = Field(default="")
    """Deterministic contextual answer grounded in retrieved results."""

    context: QueryContextDTO = Field(default_factory=QueryContextDTO)
    """Structured query context used by deep retrieval."""

    subqueries: list[QuerySubqueryDTO] = Field(default_factory=list)
    """Segments used to gather evidence."""

    selected_entities: list[QuerySelectedEntityDTO] = Field(default_factory=list)
    """Entities selected as most relevant to the query."""

    results: list[GlobalQueryResultDTO] = Field(default_factory=list)
    """Deduplicated evidence results used by the answer."""

    warnings: list[str] = Field(default_factory=list)
    """Non-blocking warning texts observed during retrieval."""
