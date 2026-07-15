"""Knowledge delta extraction from source text."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO
from brain.application.knowledge.models.dtos.graph import EntityDTO, RelationDTO
from brain.application.knowledge.models.dtos.sources import SourceDTO


def extract_heuristic_delta(source_dto: SourceDTO, content: str) -> KnowledgeDeltaDTO:
    """
    Return an empty deterministic delta because KG building is LLM-only.

    Args:
        source_dto (SourceDTO): Source metadata.
        content (str): Source content accepted by the extraction contract.

    Returns:
        KnowledgeDeltaDTO: Empty knowledge delta.
    """
    del content
    return KnowledgeDeltaDTO(
        source_path=source_dto.path,
        rationale="Heuristic extraction disabled; use LLM-only dream extraction.",
    )


def merge_deltas(primary_delta: KnowledgeDeltaDTO, secondary_delta: KnowledgeDeltaDTO) -> KnowledgeDeltaDTO:
    """
    Merge a deterministic delta with an optional model-generated delta.

    Args:
        primary_delta (KnowledgeDeltaDTO): Base delta.
        secondary_delta (KnowledgeDeltaDTO): Additional delta.

    Returns:
        KnowledgeDeltaDTO: Merged delta.
    """
    entities: list[EntityDTO] = _dedupe_entities(primary_delta.entities + secondary_delta.entities)
    relations: list[RelationDTO] = primary_delta.relations + secondary_delta.relations
    schema_suggestions = primary_delta.schema_suggestions + secondary_delta.schema_suggestions
    rationale: str = "; ".join(
        part
        for part in (primary_delta.rationale, secondary_delta.rationale)
        if part
    )
    return KnowledgeDeltaDTO(
        source_path=primary_delta.source_path or secondary_delta.source_path,
        entities=entities,
        aliases=[],
        relations=relations,
        schema_suggestions=schema_suggestions,
        rationale=rationale,
    )


def attach_source_id(delta_dto: KnowledgeDeltaDTO, source_id: int) -> KnowledgeDeltaDTO:
    """
    Attach a source identifier to every entity and relation candidate.

    Args:
        delta_dto (KnowledgeDeltaDTO): Delta generated for one source.
        source_id (int): SQLite source identifier.

    Returns:
        KnowledgeDeltaDTO: Delta with source identifiers filled.
    """
    entities: list[EntityDTO] = [
        entity_dto.model_copy(update={"source_id": entity_dto.source_id or source_id})
        for entity_dto in delta_dto.entities
    ]
    relations: list[RelationDTO] = [
        relation_dto.model_copy(update={"source_id": relation_dto.source_id or source_id})
        for relation_dto in delta_dto.relations
    ]
    return delta_dto.model_copy(update={"entities": entities, "relations": relations})


def _dedupe_entities(entities: list[EntityDTO]) -> list[EntityDTO]:
    """
    Deduplicate entity candidates by class and casefolded name.

    Args:
        entities (list[EntityDTO]): Entity candidates.

    Returns:
        list[EntityDTO]: Deduplicated entity candidates.
    """
    seen: set[tuple[str, str]] = set()
    results: list[EntityDTO] = []
    for entity_dto in entities:
        key: tuple[str, str] = (entity_dto.entity_class, entity_dto.canonical_name.casefold())
        if key in seen:
            continue
        seen.add(key)
        results.append(entity_dto)
    return results
