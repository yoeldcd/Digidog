"""Project canonical picture descriptions into the global knowledge graph."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from brain.application.knowledge.models.dtos.graph import EntityDTO, RelationDTO
from brain.application.knowledge.models.dtos.runtime_config import PictureGuidanceConfigDTO
from brain.application.knowledge.models.dtos.sources import SourceDTO
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.infrastructure.pictures.models import PictureRecord


def project_picture_descriptions(
    records: Iterable[PictureRecord],
    guidance: PictureGuidanceConfigDTO,
    repository: KnowledgeRepository | None = None,
) -> dict[str, Any]:
    """Project described pictures and explicitly recognized configured labels."""
    repo = repository or KnowledgeRepository(scope="global")
    projected: list[dict[str, Any]] = []
    for record in records:
        if not record.active or not record.description.strip():
            continue
        projected.append(project_picture_description(record=record, guidance=guidance, repository=repo))
    return {
        "pictures": len(projected),
        "characters": sum(len(item["characters"]) for item in projected),
        "tags": sum(len(item["tags"]) for item in projected),
        "projected": projected,
    }


def project_picture_description(
    record: PictureRecord,
    guidance: PictureGuidanceConfigDTO,
    repository: KnowledgeRepository | None = None,
) -> dict[str, Any]:
    """Persist a picture, its description, and evidence-bound character/tag relations."""
    repo = repository or KnowledgeRepository(scope="global")
    source_id = repo.upsert_source(
        SourceDTO(source_type="picture", path=f"pictures/{record.relative_path}", title=record.filename),
    )
    _replace_picture_relations(repository=repo, source_id=source_id)
    picture_id = repo.upsert_entity(
        EntityDTO(
            source_id=source_id,
            entity_class="FILE.Picture",
            canonical_name=record.relative_path,
            description=record.description,
            confidence=1.0,
        ),
    )
    description_id = repo.upsert_entity(
        EntityDTO(
            source_id=source_id,
            entity_class="MISC.Description",
            canonical_name=f"Description: {record.relative_path}",
            description=record.description,
            confidence=1.0,
        ),
    )
    _replace_entity_description(repository=repo, entity_id=picture_id, description=record.description)
    _replace_entity_description(repository=repo, entity_id=description_id, description=record.description)
    repo.upsert_relation(
        RelationDTO(
            source_id=source_id,
            subject_id=description_id,
            predicate="describes",
            object_id=picture_id,
            confidence=1.0,
        ),
    )

    recognized_characters = _recognized_labels(record.description, guidance.characters)
    recognized_tags = _recognized_labels(_semantic_tag_text(record.description), guidance.tags)
    character_ids: list[int] = []
    tag_ids: list[int] = []
    for name in recognized_characters:
        character_id = repo.upsert_entity(
            EntityDTO(
                source_id=source_id,
                entity_class="MISC.Noun",
                canonical_name=name,
                description=guidance.characters[name],
                confidence=1.0,
            ),
        )
        repo.upsert_relation(
            RelationDTO(
                source_id=source_id,
                subject_id=picture_id,
                predicate="depicts",
                object_id=character_id,
                confidence=1.0,
            ),
        )
        character_ids.append(character_id)
    for name in recognized_tags:
        tag_id = repo.upsert_entity(
            EntityDTO(
                source_id=source_id,
                entity_class="MISC.Tag",
                canonical_name=name,
                description=guidance.tags[name],
                confidence=1.0,
            ),
        )
        repo.upsert_relation(
            RelationDTO(
                source_id=source_id,
                subject_id=picture_id,
                predicate="has_tag",
                object_id=tag_id,
                confidence=1.0,
            ),
        )
        tag_ids.append(tag_id)
    return {
        "picture_id": picture_id,
        "description_id": description_id,
        "characters": recognized_characters,
        "character_ids": character_ids,
        "tags": recognized_tags,
        "tag_ids": tag_ids,
        "source_id": source_id,
    }


def _recognized_labels(text: str, configured: dict[str, str]) -> list[str]:
    """Return configured labels explicitly present as complete tokens."""
    return [
        name
        for name in sorted(configured, key=str.casefold)
        if re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text, flags=re.IGNORECASE)
    ]


def _semantic_tag_text(description: str) -> str:
    """Extract Markdown semantic-tag fields so prose does not create accidental tag assertions."""
    matches = re.findall(
        r"^\s*\*{0,2}Semantic Tags\*{0,2}\s*:\s*(.+)$",
        description,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return "\n".join(matches)


def _replace_picture_relations(repository: KnowledgeRepository, source_id: int) -> None:
    """Remove stale relations owned by one picture before re-projecting its current description."""
    with repository.session() as connection:
        connection.execute("DELETE FROM relations WHERE source_id = ?", (source_id,))
        connection.commit()


def _replace_entity_description(repository: KnowledgeRepository, entity_id: int, description: str) -> None:
    """Keep mutable source-owned picture text synchronized even when a newer description is shorter."""
    with repository.session() as connection:
        connection.execute(
            "UPDATE entities SET description = ?, updated_at = unixepoch() WHERE id = ?",
            (description, entity_id),
        )
        repository._refresh_entity_fts(connection=connection, entity_id=entity_id)
        connection.commit()
