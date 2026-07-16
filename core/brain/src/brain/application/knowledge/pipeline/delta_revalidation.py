# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Revalidation workflow for reviewed knowledge deltas."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO, ValidationReportDTO
from brain.application.knowledge.pipeline.delta_events import (
    ApplicationEventCallback,
    delta_counts,
    emit_application_event,
)
from brain.application.knowledge.pipeline.delta_source_content import read_source_content
from brain.application.knowledge.runtime.config_store import load_knowledge_config
from brain.application.knowledge.runtime.scopes import get_shared_config_root
from brain.application.knowledge.validation.service import validate_delta
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def revalidate_pending_delta_rows(
    repository: KnowledgeRepository,
    rows: list[dict[str, Any]],
    event_callback: ApplicationEventCallback | None = None,
) -> list[dict[str, Any]]:
    """
    Recompute validation for pending deltas using the current rules.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        rows (list[dict[str, Any]]): Pending delta rows.
        event_callback (ApplicationEventCallback | None): Optional diagnostic event sink.

    Returns:
        list[dict[str, Any]]: Rows with fresh validation payloads.
    """
    return [
        revalidate_pending_delta_row(
            repository=repository,
            row=row,
            event_callback=event_callback,
        )
        for row in rows
    ]


def revalidate_pending_delta_row(
    repository: KnowledgeRepository,
    row: dict[str, Any],
    event_callback: ApplicationEventCallback | None = None,
) -> dict[str, Any]:
    """
    Recompute validation for one pending delta using the current rules.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        row (dict[str, Any]): Pending delta row.
        event_callback (ApplicationEventCallback | None): Optional diagnostic event sink.

    Returns:
        dict[str, Any]: Row with a fresh validation payload.
    """
    minimum_confidence: float = load_knowledge_config(
        knowledge_root=get_shared_config_root(),
    ).minimum_confidence
    refreshed_row: dict[str, Any] = dict(row)
    delta_id: int | None = int(row["id"]) if row.get("id") is not None else None
    try:
        delta_dto = KnowledgeDeltaDTO.model_validate(row.get("payload", {}))
        source_content: str = read_source_content(row=row)
        emit_application_event(
            event_callback=event_callback,
            payload={
                "event": "application_validate_start",
                "delta_id": delta_id,
                "counts": delta_counts(delta_dto=delta_dto),
            },
        )
        validation_report = validate_delta(
            delta_dto=delta_dto,
            source_content=source_content,
            minimum_confidence=minimum_confidence,
            repository=repository,
        )
    except Exception as exc:
        validation_report = ValidationReportDTO(
            valid=False,
            errors=[f"Delta payload no longer satisfies the current contract: {exc}"],
            warnings=[],
            accepted_delta=KnowledgeDeltaDTO(source_path=str(row.get("source_path") or "")),
        )
    validation_payload: dict[str, Any] = validation_report.model_dump(mode="json")
    refreshed_row["validation"] = validation_payload
    if delta_id is not None:
        repository.update_pending_delta_validation(delta_id=delta_id, validation=validation_payload)
    emit_application_event(
        event_callback=event_callback,
        payload={
            "event": "application_validate_result",
            "delta_id": delta_id,
            "valid": validation_report.valid,
            "errors": len(validation_report.errors),
            "warnings": len(validation_report.warnings),
            "accepted_counts": delta_counts(delta_dto=validation_report.accepted_delta),
        },
    )
    return refreshed_row
