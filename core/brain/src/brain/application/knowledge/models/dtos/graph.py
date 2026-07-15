"""Entity and relation DTOs for knowledge graph mutations."""

from __future__ import annotations

# Third-party Libraries Imports
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Application Modules Imports
from brain.application.knowledge.models.entity_classes import canonical_class_name, canonical_entity_class
from brain.application.knowledge.models.relation_types import canonical_relation_type


class EntityDTO(BaseModel):
    """
    Knowledge graph entity.

    Attributes:
        id: Optional database identifier.
        source_id: Source document identifier that originated the entity label.
        entity_class: Discovered ontology class key.
        canonical_name: Canonical display label.
        description: Short explanatory description.
        confidence: Entity confidence score.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int | None = Field(default=None)
    source_id: int | None = Field(default=None, alias="sourceId")
    entity_class: str = Field(default="MISC.Concept")
    canonical_name: str = Field(...)
    description: str = Field(default="")
    confidence: float = Field(default=0.65, ge=0.0, le=1.0)

    def __str__(self) -> str:
        """
        Render the entity using the compact graph object syntax.

        Returns:
            str: Entity display string in `[class:"name"]` form.
        """
        return f'[{self.entity_class}:"{self.canonical_name}"]'

    @field_validator("entity_class")
    @classmethod
    def validate_entity_class(cls, value: str) -> str:
        """
        Normalize entity classes into safe discovered ontology keys.

        Args:
            value (str): Raw entity class value.

        Returns:
            str: Canonical entity class key.
        """
        return canonical_entity_class(value)

    @model_validator(mode="after")
    def normalize_cls_name(self) -> "EntityDTO":
        """
        Normalize class-definition entity names into the CLS contract.

        Returns:
            EntityDTO: Entity with PascalCase `CLS` canonical name.
        """
        if self.entity_class == "CLS":
            self.canonical_name = canonical_class_name(self.canonical_name)
        return self


class AliasDTO(BaseModel):
    """
    Legacy or manual alternate name for an entity.

    Attributes:
        id: Optional database identifier.
        entity_ref: Entity ID or canonical name reference.
        alias: Alternate surface form. Current LLM dream extraction does not emit aliases.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None)
    entity_ref: int | str = Field(...)
    alias: str = Field(...)


class RelationDTO(BaseModel):
    """
    Knowledge graph relation candidate or persisted relation.

    Attributes:
        id: Optional database identifier.
        source_id: Source document identifier that originated the relation.
        subject_id: Subject entity identifier.
        object_id: Object entity identifier.
        predicate: Canonical discovered relation predicate.
        confidence: Relation confidence score.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int | None = Field(default=None)
    source_id: int | None = Field(default=None, alias="sourceId")
    subject_id: int | None = Field(default=None, alias="subjectId")
    object_id: int | None = Field(default=None, alias="objectId")
    predicate: str = Field(default="related_to")
    confidence: float = Field(default=0.65, ge=0.0, le=1.0)

    def __str__(self) -> str:
        """
        Render the relation using the compact graph edge syntax.

        Returns:
            str: Relation display string in `{sub} - ("predicate" at confidence) -> {obj}` form.
        """
        subject_text: str = str(self.subject_id) if self.subject_id is not None else "?"
        object_text: str = str(self.object_id) if self.object_id is not None else "?"
        return f'{{{subject_text}}} - ("{self.predicate}" at {self.confidence:.2f}) -> {{{object_text}}}'

    @field_validator("predicate")
    @classmethod
    def validate_predicate(cls, value: str) -> str:
        """
        Normalize relation predicates into safe discovered ontology keys.

        Args:
            value (str): Raw predicate value.

        Returns:
            str: Canonical relation predicate.
        """
        return canonical_relation_type(value)
