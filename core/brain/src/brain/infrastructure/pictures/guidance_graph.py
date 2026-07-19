"""Project configured picture characters into the private knowledge graph."""

from __future__ import annotations

from brain.application.knowledge.models.dtos.graph import EntityDTO, RelationDTO
from brain.application.knowledge.models.dtos.sources import SourceDTO
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


GUIDANCE_SOURCE_PATH = "configs/brain_configs.json#pictures.guidance.characters"
"""Stable graph source identity for configured character recognition guidance."""


def project_character_guidance(
    name: str,
    description: str,
    repository: KnowledgeRepository | None = None,
) -> dict[str, int | str]:
    """
    Associate one `DESCRIPTION` entity with a same-name `Noun` identity.

    Args:
        name: Configured character name used as the noun identity value.
        description: Configured visual recognition description.
        repository: Optional knowledge repository override for tests.

    Returns:
        Identifiers for the source, description, noun, and relation records.
    """
    repo = repository or KnowledgeRepository(scope="global")
    source_id = repo.upsert_source(
        SourceDTO(
            source_type="config",
            path=GUIDANCE_SOURCE_PATH,
            title="Picture character guidance",
        ),
    )
    _ensure_description_class(repository=repo, source_id=source_id)
    noun_id = repo.upsert_entity(
        EntityDTO(
            source_id=source_id,
            entity_class="MISC.Noun",
            canonical_name=name,
            description="Named identity configured for picture recognition.",
            confidence=1.0,
        ),
    )
    description_id = repo.upsert_entity(
        EntityDTO(
            source_id=source_id,
            entity_class="MISC.Description",
            canonical_name=description,
            description=f"Visual recognition guidance describing {name}.",
            confidence=1.0,
        ),
    )
    relation_id = repo.upsert_relation(
        RelationDTO(
            source_id=source_id,
            subject_id=description_id,
            predicate="describes",
            object_id=noun_id,
            confidence=1.0,
        ),
    )
    return {
        "source_id": source_id,
        "description_entity_id": description_id,
        "noun_entity_id": noun_id,
        "relation_id": relation_id,
        "noun": name,
    }


def _ensure_description_class(repository: KnowledgeRepository, source_id: int) -> None:
    """Ensure only the guidance-specific `Description` class definition exists."""
    repository.upsert_entity(
        EntityDTO(
            source_id=source_id,
            entity_class="CLS",
            canonical_name="Description",
            description="Text that describes the observable traits of another graph identity.",
            confidence=1.0,
        ),
    )
