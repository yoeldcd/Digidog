"""Knowledge delta DTOs for validation and persistence workflows."""

from __future__ import annotations

# Third-party Libraries Imports
from pydantic import BaseModel, ConfigDict, Field

# Application Modules Imports
from brain.application.knowledge.models.dtos.graph import AliasDTO, EntityDTO, RelationDTO


class SchemaSuggestionDTO(BaseModel):
    """
    Ontology evolution proposal from a model or consolidation pass.

    Attributes:
        suggestion_type: Either `entity_class` or `relation_type`.
        name: Suggested ontology key.
        description: Suggested semantic description.
        confidence: Suggestion confidence score.
    """

    model_config = ConfigDict(extra="forbid")

    suggestion_type: str = Field(...)
    name: str = Field(...)
    description: str = Field(default="")
    confidence: float = Field(default=0.65, ge=0.0, le=1.0)


class KnowledgeDeltaDTO(BaseModel):
    """
    Proposed graph change set generated for one source.

    Attributes:
        source_path: Stable source path the delta was generated from.
        entities: Entity candidates.
        aliases: Legacy/manual alias candidates. Model-backed dream extraction leaves this empty.
        relations: Relation candidates.
        schema_suggestions: Ontology evolution suggestions.
        rationale: Short explanation of the proposed changes.
    """

    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(default="")
    entities: list[EntityDTO] = Field(default_factory=list)
    aliases: list[AliasDTO] = Field(default_factory=list)
    relations: list[RelationDTO] = Field(default_factory=list)
    schema_suggestions: list[SchemaSuggestionDTO] = Field(default_factory=list)
    rationale: str = Field(default="")


class ValidationReportDTO(BaseModel):
    """
    Deterministic validation result for a proposed knowledge delta.

    Attributes:
        valid: Whether the delta can be applied.
        errors: Blocking validation failures.
        warnings: Non-blocking validation observations.
        accepted_delta: Delta filtered down to valid records.
    """

    valid: bool = Field(default=False)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    accepted_delta: KnowledgeDeltaDTO = Field(default_factory=KnowledgeDeltaDTO)
