# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

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


class MemorySearchDTO(BaseModel):
    model_config = ConfigDict(extra="allow")
    key: str = ""
    category: str = ""
    path: str = ""
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessageSearchDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = ""
    created_at: str = ""
    text: str = ""
    emotion: str = ""
    chat_id: str = ""
    language: str = "es"
    source_type: str = "speak"
    source_command: str = ""
    source_phase: str = ""
    date: str = ""
    time: str = ""


class PictureSearchDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = ""
    relative_path: str = ""
    domain: str = ""
    filename: str = ""
    extension: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    mtime_ns: int = 0
    content_hash: str = ""
    width: int = 0
    height: int = 0
    description: str = ""
    description_source: str = ""
    described_at: str = ""
    vector_fingerprint: str = ""
    active: bool = False
    created_at: str = ""
    updated_at: str = ""
    scope: str = "local"


class DiarySearchDTO(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str = ""
    date: str = ""
    time: str = ""
    content: str = ""
    read_command: str = ""


class LogSearchDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = 0
    text: str = ""
    path: str = ""
    domain: str = ""
    title: str = ""
    type: str = ""
    timestamp: str = ""
    read_command: str = ""
    similarity: float = 0.0
    recency_factor: float = 0.0
    score: float = 0.0


class KnowledgeSearchDTO(BaseModel):
    model_config = ConfigDict(extra="allow")
    entities: list[QueryEntityDTO] = Field(default_factory=list)
    relations: list[QueryRelationDTO] = Field(default_factory=list)


SourceSearchResult = MemorySearchDTO | MessageSearchDTO | PictureSearchDTO | DiarySearchDTO | LogSearchDTO | KnowledgeSearchDTO

class QueryPageDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    response: str = ""
    items: list[GlobalQueryResultDTO] = Field(default_factory=list)
    page: int = 1
    pageSize: int = 25
    totalItems: int = 0
    totalPages: int = 0
    hasPrevious: bool = False
    hasNext: bool = False
    countsBySource: dict[str, int] = Field(default_factory=dict)
class GlobalQueryResultDTO(BaseModel):
    """
    Normalized result returned by the global `query` command.

    Attributes:
        source (str): Query backend that produced the result.
        mechanism (str): Search mechanism that produced the result.
        kind (str): Backend-specific result type.
        rank (float): Numeric ordering hint from the backend.
        title (str): Human-readable result title.
        text (str): Short excerpt mirrored from `content.excerpt`.
        data (dict[str, Any]): Original backend payload.
        warning (str): Optional non-blocking warning text.
        content (QueryContentDTO): Normalized result content block.
        source_ref (QuerySourceRefDTO): Structured source reference for the result.
        entities (list[QueryEntityDTO]): Entities involved in the result.
        relations (list[QueryRelationDTO]): Relations involved in the result.
        match (QueryMatchDTO): Deep-query matching explanation and adjusted score.
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

    # Source-specific verbose contracts are represented directly in `data`.
    """The single verbose source payload is stored in `data`."""

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



def normalize_source_result(dto: SourceSearchResult, mechanism: str = "", rank: float = 0.0) -> GlobalQueryResultDTO:
    """Build a GlobalQueryResultDTO from any source-specific search DTO."""
    if isinstance(dto, MemorySearchDTO):
        return GlobalQueryResultDTO(
            source="memory", mechanism=mechanism, kind="memory", rank=rank,
            title=dto.key or dto.path, text=dto.text,
            data=dto.model_dump(mode="json"),
            content=QueryContentDTO(title=dto.key or dto.path, excerpt=dto.text[:600], body=dto.text),
            source_ref=QuerySourceRefDTO(scope="local", source_type="memory", domain=dto.category, path=dto.path, title=dto.key or dto.path),
        )
    if isinstance(dto, MessageSearchDTO):
        return GlobalQueryResultDTO(
            source="messages", mechanism=mechanism, kind="message", rank=rank,
            title=dto.source_command or f"Avatar message at {dto.created_at}", text=dto.text,
            data=dto.model_dump(mode="json"),
            content=QueryContentDTO(title=dto.source_command or "", excerpt=dto.text[:600], body=dto.text, location=dto.created_at),
            source_ref=QuerySourceRefDTO(scope="local", source_type="messages", domain="messages", path=f"$agent/database/messages.db#message:{dto.id}", title=dto.source_command or ""),
        )
    if isinstance(dto, PictureSearchDTO):
        excerpt = dto.description or f"Image file {dto.filename}"
        return GlobalQueryResultDTO(
            source="pictures", mechanism=mechanism, kind="picture", rank=rank,
            title=dto.filename, text=excerpt,
            data=dto.model_dump(mode="json"),
            content=QueryContentDTO(title=dto.filename, excerpt=excerpt, body=dto.description, location=dto.relative_path),
            source_ref=QuerySourceRefDTO(scope=dto.scope, source_type="pictures", domain=dto.domain, path=f"pictures/{dto.relative_path}", title=dto.filename),
        )
    if isinstance(dto, DiarySearchDTO):
        return GlobalQueryResultDTO(
            source="memory", mechanism=mechanism, kind="diary", rank=rank,
            title=dto.title, text=dto.content,
            data=dto.model_dump(mode="json"),
            content=QueryContentDTO(title=dto.title, excerpt=dto.content[:600], body=dto.content),
            source_ref=QuerySourceRefDTO(scope="local", source_type="diary", domain="diary", read_command=dto.read_command, title=dto.title),
        )
    if isinstance(dto, LogSearchDTO):
        return GlobalQueryResultDTO(
            source="logs", mechanism=mechanism, kind="log", rank=rank,
            title=dto.title, text=dto.text,
            data=dto.model_dump(mode="json"),
            content=QueryContentDTO(title=dto.title, excerpt=dto.text[:600], body=dto.text),
            source_ref=QuerySourceRefDTO(scope="local", source_type="logs", domain=dto.domain, read_command=dto.read_command, path=dto.path, title=dto.title),
        )
    if isinstance(dto, KnowledgeSearchDTO):
        return GlobalQueryResultDTO(
            source="knowledge", mechanism=mechanism, kind="knowledge", rank=rank,
            title="", text="",
            data=dto.model_dump(mode="json"),
            entities=list(dto.entities),
            relations=list(dto.relations),
        )
    return GlobalQueryResultDTO(source="unknown", mechanism=mechanism, kind="unknown", rank=rank, title="", text="", data={})

class QuerySubqueryDTO(BaseModel):
    """
    Planned query segment used by deep query mode.

    Attributes:
        index (int): Stable 1-based subquery index.
        text (str): Subquery text sent to the selected retrieval backends.
        reason (str): Short reason for why the segment was produced.
        keywords (list[str]): Significant retrieval keywords for the segment.
        date_constraints (list[QueryDateConstraintDTO]): Temporal constraints inherited by the segment.
        results (list[GlobalQueryResultDTO]): Normalized matches returned for this subquery.
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
        query (str): Original user query.
        answer (str): Deterministic contextual answer grounded in retrieved results.
        context (QueryContextDTO): Structured keywords and temporal query context.
        subqueries (list[QuerySubqueryDTO]): Segments used to gather evidence.
        selected_entities (list[QuerySelectedEntityDTO]): Entities selected as query anchors.
        results (list[GlobalQueryResultDTO]): Deduplicated evidence results used by the answer.
        warnings (list[str]): Non-blocking warning texts observed during retrieval.
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
