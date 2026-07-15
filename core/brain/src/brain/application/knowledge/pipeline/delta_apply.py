"""Application workflow for reviewed knowledge deltas."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO, ValidationReportDTO
from brain.application.knowledge.models.dtos.dream import ConsolidationDecisionDTO
from brain.application.knowledge.pipeline.consolidation import apply_validated_delta, promote_recurrent_knowledge
from brain.application.knowledge.pipeline.delta_events import (
    ApplicationEventCallback,
    delta_counts,
    emit_application_event,
)
from brain.application.knowledge.pipeline.delta_ordering import class_definition_sort_key
from brain.application.knowledge.pipeline.delta_source_content import read_source_content
from brain.application.knowledge.runtime.config_store import load_knowledge_config
from brain.application.knowledge.runtime.scopes import get_shared_config_root
from brain.application.knowledge.validation.service import validate_delta
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def apply_pending_delta_rows(
    repository: KnowledgeRepository,
    selected_rows: list[dict],
    event_callback: ApplicationEventCallback | None = None,
    revalidate: bool = True,
) -> tuple[int, list[str], list[ConsolidationDecisionDTO]]:
    """
    Apply selected, validated pending deltas.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        selected_rows (list[dict]): Pending delta rows selected by the user.
        event_callback (ApplicationEventCallback | None): Optional verbose application event sink.
        revalidate (bool): Whether to recompute validation from the raw delta payload before writing.

    Returns:
        tuple[int, list[str], list[ConsolidationDecisionDTO]]: Applied count, errors, and decisions.
    """
    applied_count: int = 0
    application_errors: list[str] = []
    decisions: list[ConsolidationDecisionDTO] = []
    minimum_confidence: float = load_knowledge_config(
        knowledge_root=get_shared_config_root(),
    ).minimum_confidence
    sorted_rows: list[dict] = sorted(selected_rows, key=class_definition_sort_key)
    emit_application_event(
        event_callback=event_callback,
        payload={
            "event": "application_batch_start",
            "selected": len(sorted_rows),
            "delta_ids": [int(row["id"]) for row in sorted_rows if row.get("id") is not None],
        },
    )

    for row in sorted_rows:
        try:
            emit_application_event(
                event_callback=event_callback,
                payload={
                    "event": "application_delta_start",
                    "delta_id": int(row["id"]),
                    "source_path": row.get("source_path", ""),
                    "status": row.get("status", ""),
                },
            )
            source_content: str = read_source_content(row=row)
            if revalidate:
                delta_dto = KnowledgeDeltaDTO.model_validate(row.get("payload", {}))
                emit_application_event(
                    event_callback=event_callback,
                    payload={
                        "event": "application_validate_start",
                        "delta_id": int(row["id"]),
                        "counts": delta_counts(delta_dto=delta_dto),
                    },
                )
                validation_report = validate_delta(
                    delta_dto=delta_dto,
                    source_content=source_content,
                    minimum_confidence=minimum_confidence,
                    repository=repository,
                )
                repository.update_pending_delta_validation(
                    delta_id=int(row["id"]),
                    validation=validation_report.model_dump(mode="json"),
                )
                emit_application_event(
                    event_callback=event_callback,
                    payload={
                        "event": "application_validate_result",
                        "delta_id": int(row["id"]),
                        "valid": validation_report.valid,
                        "errors": len(validation_report.errors),
                        "warnings": len(validation_report.warnings),
                        "accepted_counts": delta_counts(delta_dto=validation_report.accepted_delta),
                    },
                )
            else:
                validation_report = ValidationReportDTO.model_validate(row.get("validation", {}))
            if not validation_report.valid:
                error_text = "; ".join(validation_report.errors or validation_report.warnings)
                raise ValueError(f"delta no longer satisfies the current contract: {error_text}")
            emit_application_event(
                event_callback=event_callback,
                payload={
                    "event": "application_write_start",
                    "delta_id": int(row["id"]),
                    "source_id": int(row["source_id"]),
                    "accepted_counts": delta_counts(delta_dto=validation_report.accepted_delta),
                },
            )
            decisions.extend(
                apply_validated_delta(
                    repository=repository,
                    source_id=int(row["source_id"]),
                    delta_dto=validation_report.accepted_delta,
                    source_content=source_content,
                ),
            )
            repository.update_pending_delta_status(delta_id=int(row["id"]), status="applied")
            applied_count += 1
            emit_application_event(
                event_callback=event_callback,
                payload={
                    "event": "application_delta_applied",
                    "delta_id": int(row["id"]),
                    "decisions": len(decisions),
                },
            )
        except Exception as exc:
            repository.update_pending_delta_status(delta_id=int(row["id"]), status="failed")
            application_errors.append(f"Selected delta {row.get('id')} failed during application: {exc}")
            emit_application_event(
                event_callback=event_callback,
                payload={
                    "event": "application_delta_failed",
                    "delta_id": row.get("id"),
                    "error": str(exc),
                },
            )

    if applied_count:
        emit_application_event(
            event_callback=event_callback,
            payload={"event": "application_promotion_start", "applied": applied_count},
        )
        promotion_decisions = promote_recurrent_knowledge(repository=repository, min_sources=2)
        decisions.extend(promotion_decisions)
        emit_application_event(
            event_callback=event_callback,
            payload={
                "event": "application_promotion_result",
                "decisions": len(promotion_decisions),
            },
        )
    emit_application_event(
        event_callback=event_callback,
        payload={
            "event": "application_batch_complete",
            "applied": applied_count,
            "errors": len(application_errors),
        },
    )
    return applied_count, application_errors, decisions
