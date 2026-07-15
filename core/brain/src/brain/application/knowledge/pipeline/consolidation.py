"""Delta application and consolidation rules for the knowledge graph."""

from __future__ import annotations

# Application Modules Imports
from .deduplication import should_merge_alias, upsert_deduped_entity
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO, ValidationReportDTO
from brain.application.knowledge.models.dtos.dream import ConsolidationDecisionDTO
from brain.application.knowledge.models.dtos.graph import EntityDTO, RelationDTO
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def apply_validated_delta(
    repository: KnowledgeRepository,
    source_id: int,
    delta_dto: KnowledgeDeltaDTO,
    source_content: str,
) -> list[ConsolidationDecisionDTO]:
    """
    Apply a validated delta to the repository.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        source_id (int): Source identifier.
        delta_dto (KnowledgeDeltaDTO): Validated delta.
        source_content (str): Source content.

    Returns:
        list[ConsolidationDecisionDTO]: Application decisions.
    """
    decisions: list[ConsolidationDecisionDTO] = []
    entity_ids_by_candidate: dict[int, int] = {}
    entity_ids_by_name: dict[str, int] = {}

    ordered_entities: list[EntityDTO] = sorted(
        delta_dto.entities,
        key=lambda entity_dto: 0 if entity_dto.entity_class == "CLS" else 1,
    )
    for entity_dto in ordered_entities:
        source_entity_dto: EntityDTO = entity_dto.model_copy(
            update={"source_id": entity_dto.source_id or source_id},
        )
        entity_id: int = upsert_deduped_entity(repository=repository, entity_dto=source_entity_dto)
        if entity_dto.id is not None:
            entity_ids_by_candidate[int(entity_dto.id)] = entity_id
        entity_ids_by_name[entity_dto.canonical_name.casefold()] = entity_id
        decisions.append(
            ConsolidationDecisionDTO(
                action="apply",
                reason=f"Entity `{entity_dto.canonical_name}` applied or reused.",
                entity_id=entity_id,
            ),
        )

    for alias_dto in delta_dto.aliases:
        entity_id = _resolve_entity_id(
            repository=repository,
            entity_ref=alias_dto.entity_ref,
            entity_ids_by_name=entity_ids_by_name,
        )
        if entity_id is None:
            decisions.append(
                ConsolidationDecisionDTO(
                    action="skip",
                    reason=f"Alias `{alias_dto.alias}` has no entity.",
                ),
            )
            continue
        entity_row = repository.find_entity_by_ref(entity_ref=entity_id)
        if entity_row and should_merge_alias(candidate_name=entity_row["canonical_name"], alias=alias_dto.alias):
            repository.add_alias(entity_id=entity_id, alias=alias_dto.alias)

    for relation_dto in delta_dto.relations:
        relation_id: int = repository.upsert_relation(
            relation_dto=_resolve_relation_ids(
                relation_dto=relation_dto,
                source_id=source_id,
                entity_ids_by_candidate=entity_ids_by_candidate,
            ),
        )
        decisions.append(
            ConsolidationDecisionDTO(
                action="apply",
                reason=f"Relation `{relation_dto.predicate}` applied or reused.",
                relation_id=relation_id,
            ),
        )

    for suggestion_dto in delta_dto.schema_suggestions:
        repository.add_schema_suggestion(
            suggestion_type=suggestion_dto.suggestion_type,
            name=suggestion_dto.name,
            description=suggestion_dto.description,
            confidence=suggestion_dto.confidence,
        )
        if suggestion_dto.suggestion_type == "entity_class":
            repository.ensure_entity_class(
                name=suggestion_dto.name,
                description=suggestion_dto.description,
            )
        if suggestion_dto.suggestion_type == "relation_type":
            repository.ensure_relation_type(
                name=suggestion_dto.name,
                description=suggestion_dto.description,
            )
        decisions.append(
            ConsolidationDecisionDTO(
                action="apply",
                reason=f"Schema suggestion `{suggestion_dto.name}` registered and activated.",
            ),
        )

    repository.record_applied_delta(source_id=source_id, payload=delta_dto.model_dump(mode="json"))
    return decisions


def promote_recurrent_knowledge(
    repository: KnowledgeRepository,
    min_sources: int = 2,
) -> list[ConsolidationDecisionDTO]:
    """
    Promote repeated graph relations into semantic facts.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        min_sources (int): Minimum distinct source count.

    Returns:
        list[ConsolidationDecisionDTO]: Promotion decisions.
    """
    decisions: list[ConsolidationDecisionDTO] = []
    recurrent_rows: list[dict] = repository.recurrent_literal_relations(min_sources=min_sources)
    for row in recurrent_rows:
        predicate: str = str(row.get("predicate") or "related_to")
        subject_name: str = str(row.get("subject_name") or "").strip()
        object_name: str = str(row.get("object_name") or "").strip()
        if not subject_name or not object_name:
            continue
        fact_name: str = f"Consolidated {subject_name} {predicate} {object_name}"[:180]
        entity_id: int = repository.upsert_entity(
            EntityDTO(
                source_id=int(row["source_id"]) if row.get("source_id") else None,
                entity_class="MISC.ConsolidatedClaim",
                canonical_name=fact_name,
                description=f"Promoted from {row['source_count']} distinct sources.",
                confidence=float(row.get("confidence") or 0.7),
            ),
        )
        decisions.append(
            ConsolidationDecisionDTO(
                action="promote",
                reason=f"Promoted recurrent relation `{predicate}` into a consolidated claim.",
                entity_id=entity_id,
            ),
        )
    return decisions


def persist_validation_report(
    repository: KnowledgeRepository,
    source_id: int,
    delta_dto: KnowledgeDeltaDTO,
    report_dto: ValidationReportDTO,
) -> int:
    """
    Persist a pending delta validation audit record.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        source_id (int): Source identifier.
        delta_dto (KnowledgeDeltaDTO): Original delta.
        report_dto (ValidationReportDTO): Validation report.

    Returns:
        int: Pending delta identifier.
    """
    return repository.record_pending_delta(
        source_id=source_id,
        payload=delta_dto.model_dump(mode="json"),
        validation=report_dto.model_dump(mode="json"),
    )


def _resolve_entity_id(
    repository: KnowledgeRepository,
    entity_ref: int | str,
    entity_ids_by_name: dict[str, int],
) -> int | None:
    """
    Resolve an entity reference through local and repository state.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        entity_ref (int | str): Entity reference.
        entity_ids_by_name (dict[str, int]): Local name-to-id map.

    Returns:
        int | None: Entity identifier when found.
    """
    if isinstance(entity_ref, int):
        return entity_ref
    local_entity_id: int | None = entity_ids_by_name.get(entity_ref.casefold())
    if local_entity_id is not None:
        return local_entity_id
    entity_row: dict | None = repository.find_entity_by_ref(entity_ref=entity_ref)
    return int(entity_row["id"]) if entity_row else None


def _resolve_relation_ids(
    relation_dto: RelationDTO,
    source_id: int,
    entity_ids_by_candidate: dict[int, int],
) -> RelationDTO:
    """
    Replace candidate-local relation endpoint IDs with persisted entity IDs.

    Args:
        relation_dto (RelationDTO): Relation candidate.
        source_id (int): Source identifier for the relation.
        entity_ids_by_candidate (dict[int, int]): Candidate ID to persisted ID map.

    Returns:
        RelationDTO: Updated relation DTO.
    """
    subject_id: int | None = relation_dto.subject_id
    object_id: int | None = relation_dto.object_id
    if subject_id is not None:
        subject_id = entity_ids_by_candidate.get(subject_id, subject_id)
    if object_id is not None:
        object_id = entity_ids_by_candidate.get(object_id, object_id)
    return relation_dto.model_copy(
        update={
            "source_id": relation_dto.source_id or source_id,
            "subject_id": subject_id,
            "object_id": object_id,
        },
    )
