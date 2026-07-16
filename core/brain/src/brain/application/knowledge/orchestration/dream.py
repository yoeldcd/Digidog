# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Dream consolidation pipeline for the evolving knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
import time
from typing import Any, Callable

# Application Modules Imports
from brain.application.knowledge.runtime.config_store import load_knowledge_config
from brain.application.knowledge.pipeline.consolidation import apply_validated_delta, persist_validation_report, promote_recurrent_knowledge
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO, ValidationReportDTO
from brain.application.knowledge.models.dtos.dream import ConsolidationDecisionDTO, DreamRunDTO
from brain.application.knowledge.models.dtos.sources import SourceDTO
from brain.application.knowledge.orchestration.dream_class_catalog import (
    build_entity_class_catalog,
    merge_entity_class_catalog,
)
from brain.application.knowledge.orchestration.dream_context import (
    build_entity_resolution_context,
    build_graph_context,
)
from brain.application.knowledge.orchestration.dream_delta_rules import delta_has_records
from brain.application.knowledge.pipeline.extraction import attach_source_id, merge_deltas
from brain.application.knowledge.llm.framing import build_knowledge_frame, render_knowledge_frame_for_llm
from brain.application.knowledge.llm.events import LLMEventCallback
from brain.application.knowledge.llm.stage_sequence import generate_multistage_deltas
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.application.knowledge.sources.freshness import mark_source_processed
from brain.application.knowledge.sources.ingestion import ingest_sources
from brain.application.knowledge.validation.service import validate_delta


class DreamRunner:
    """
    Orchestrates cognitive consolidation from changed sources.

    Attributes:
        repository: Knowledge graph repository.
    """

    repository: KnowledgeRepository
    """Knowledge graph repository."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        """
        Initialize the dream runner.

        Args:
            repository (KnowledgeRepository): Knowledge graph repository.
        """
        self.repository = repository

    def run(
        self,
        domain: str = "all",
        limit: int | None = None,
        dry_run: bool = True,
        use_llm: bool = True,
        minimum_confidence: float | None = None,
        llm_event_callback: LLMEventCallback | None = None,
        orchestration_event_callback: Callable[[dict[str, Any]], None] | None = None,
        force_all: bool = False,
    ) -> DreamRunDTO:
        """
        Execute one dream consolidation run.

        Args:
            domain (str): Source domain filter.
            limit (int | None): Optional source limit.
            dry_run (bool): Whether to avoid applying valid deltas.
            use_llm (bool): Whether to allow model-backed proposals. LLM-only dream skips sources when false.
            minimum_confidence (float | None): Optional confidence threshold override.
            llm_event_callback (LLMEventCallback | None): Optional real-time sink for LLM execution events.
            orchestration_event_callback: Optional real-time sink for source and consolidation events.
            force_all (bool): Whether to treat every discovered source as changed.

        Returns:
            DreamRunDTO: Run summary.
        """
        started_at: float = time.time()
        config_dto = load_knowledge_config()
        threshold: float = minimum_confidence if minimum_confidence is not None else config_dto.minimum_confidence
        _emit_event(
            event_callback=orchestration_event_callback,
            payload={
                "event": "dream_run_start",
                "scope": self.repository.scope,
                "domain": domain,
                "limit": limit,
                "dry_run": dry_run,
                "minimum_confidence": threshold,
                "force_all": force_all,
            },
        )
        ingestion_result: dict = ingest_sources(
            repository=self.repository,
            domain=domain,
            limit=limit,
            source_scope=self.repository.scope,
            force_all=force_all,
            event_callback=orchestration_event_callback,
        )
        changed_sources: list[dict] = ingestion_result["changed_sources"]
        decisions: list[ConsolidationDecisionDTO] = []
        errors: list[str] = []
        pending_delta_ids: list[int] = []
        proposed_count: int = 0
        applied_count: int = 0
        entity_class_catalog: dict[str, str] = build_entity_class_catalog(repository=self.repository)
        _emit_event(
            event_callback=orchestration_event_callback,
            payload={
                "event": "class_catalog_loaded",
                "scope": self.repository.scope,
                "classes": sorted(entity_class_catalog),
            },
        )

        for changed_source in changed_sources:
            source_dto: SourceDTO = changed_source["source"]
            source_mtime: float = float(changed_source.get("mtime") or 0.0)
            content: str = changed_source["content"]
            _emit_event(
                event_callback=orchestration_event_callback,
                payload={
                    "event": "dream_source_start",
                    "scope": self.repository.scope,
                    "source_path": source_dto.path,
                    "source_type": source_dto.source_type,
                    "title": source_dto.title,
                    "mtime": source_mtime,
                    "chars": len(content),
                },
            )
            if not use_llm:
                errors.append(f"LLM-only dream skipped `{source_dto.path}` because model stages were disabled.")
                _emit_event(
                    event_callback=orchestration_event_callback,
                    payload={
                        "event": "dream_source_skipped",
                        "scope": self.repository.scope,
                        "source_path": source_dto.path,
                        "reason": "llm_disabled",
                    },
                )
                continue

            delta_dto: KnowledgeDeltaDTO = KnowledgeDeltaDTO(
                source_path=source_dto.path,
                rationale="LLM-only structural extraction.",
            )
            knowledge_frame = build_knowledge_frame(source_dto=source_dto, content=content)
            model_content: str = render_knowledge_frame_for_llm(
                frame_dto=knowledge_frame,
            )
            graph_context: str = build_graph_context(repository=self.repository)
            entity_name_to_id: dict[str, int] = build_entity_resolution_context(repository=self.repository)
            _emit_event(
                event_callback=orchestration_event_callback,
                payload={
                    "event": "dream_frame_built",
                    "scope": self.repository.scope,
                    "source_path": source_dto.path,
                    "frame_kind": knowledge_frame.frame_kind,
                    "frame_title": knowledge_frame.title,
                    "source_chars": len(content),
                    "model_chars": len(model_content),
                    "graph_context_chars": len(graph_context),
                    "entity_resolution_candidates": len(entity_name_to_id),
                },
            )
            if llm_event_callback is None:
                stage_deltas, stage_warnings = generate_multistage_deltas(
                    source_path=source_dto.path,
                    content=model_content,
                    base_delta=delta_dto,
                    graph_context=graph_context,
                    entity_name_to_id=entity_name_to_id,
                    entity_class_catalog=entity_class_catalog,
                )
            else:
                stage_deltas, stage_warnings = generate_multistage_deltas(
                    source_path=source_dto.path,
                    content=model_content,
                    base_delta=delta_dto,
                    graph_context=graph_context,
                    entity_name_to_id=entity_name_to_id,
                    entity_class_catalog=entity_class_catalog,
                    event_callback=llm_event_callback,
                )
            errors.extend(stage_warnings)
            for warning in stage_warnings:
                _emit_event(
                    event_callback=orchestration_event_callback,
                    payload={
                        "event": "dream_stage_warning",
                        "scope": self.repository.scope,
                        "source_path": source_dto.path,
                        "warning": warning,
                    },
                )
            for stage_name, stage_delta in stage_deltas:
                delta_dto = merge_deltas(primary_delta=delta_dto, secondary_delta=stage_delta)
                _emit_event(
                    event_callback=orchestration_event_callback,
                    payload={
                        "event": "dream_stage_merged",
                        "scope": self.repository.scope,
                        "source_path": source_dto.path,
                        "stage": stage_name,
                        "delta_counts": _delta_counts(delta_dto=stage_delta),
                        "accumulated_counts": _delta_counts(delta_dto=delta_dto),
                    },
                )
                decisions.append(
                    ConsolidationDecisionDTO(
                        action="propose",
                        reason=f"LLM stage `{stage_name}` produced a KnowledgeDeltaDTO.",
                    ),
                )
            source_processed: bool = bool(stage_deltas) and not stage_warnings
            if not delta_has_records(delta_dto=delta_dto):
                decisions.append(
                    ConsolidationDecisionDTO(
                        action="skip",
                        reason=f"No model-backed KnowledgeDeltaDTO records were produced for `{source_dto.path}`.",
                    ),
                )
                if source_processed:
                    mark_source_processed(
                        repository=self.repository,
                        source_path=source_dto.path,
                        mtime=source_mtime,
                    )
                    _emit_event(
                        event_callback=orchestration_event_callback,
                        payload={
                            "event": "source_marked_processed",
                            "scope": self.repository.scope,
                            "source_path": source_dto.path,
                            "mtime": source_mtime,
                        },
                    )
                continue

            source_id: int = self.repository.upsert_source(source_dto=source_dto)
            _emit_event(
                event_callback=orchestration_event_callback,
                payload={
                    "event": "source_upserted",
                    "scope": self.repository.scope,
                    "source_path": source_dto.path,
                    "source_id": source_id,
                },
            )
            delta_dto = attach_source_id(delta_dto=delta_dto, source_id=source_id)
            report_dto: ValidationReportDTO = validate_delta(
                delta_dto=delta_dto,
                source_content=content,
                minimum_confidence=threshold,
                repository=self.repository,
                known_class_names=set(entity_class_catalog),
            )
            _emit_event(
                event_callback=orchestration_event_callback,
                payload={
                    "event": "delta_validated",
                    "scope": self.repository.scope,
                    "source_path": source_dto.path,
                    "source_id": source_id,
                    "valid": report_dto.valid,
                    "candidate_counts": _delta_counts(delta_dto=delta_dto),
                    "accepted_counts": _delta_counts(delta_dto=report_dto.accepted_delta),
                    "errors": len(report_dto.errors),
                    "warnings": len(report_dto.warnings),
                },
            )
            merge_entity_class_catalog(
                entity_class_catalog=entity_class_catalog,
                delta_dto=report_dto.accepted_delta,
            )
            pending_delta_id: int = persist_validation_report(
                repository=self.repository,
                source_id=source_id,
                delta_dto=delta_dto,
                report_dto=report_dto,
            )
            _emit_event(
                event_callback=orchestration_event_callback,
                payload={
                    "event": "pending_delta_persisted",
                    "scope": self.repository.scope,
                    "source_path": source_dto.path,
                    "source_id": source_id,
                    "delta_id": pending_delta_id,
                    "accepted_counts": _delta_counts(delta_dto=report_dto.accepted_delta),
                },
            )
            pending_delta_ids.append(pending_delta_id)
            proposed_count += 1
            if source_processed:
                mark_source_processed(
                    repository=self.repository,
                    source_path=source_dto.path,
                    mtime=source_mtime,
                )
                _emit_event(
                    event_callback=orchestration_event_callback,
                    payload={
                        "event": "source_marked_processed",
                        "scope": self.repository.scope,
                        "source_path": source_dto.path,
                        "mtime": source_mtime,
                    },
                )

            if dry_run or not report_dto.valid:
                if not dry_run and not report_dto.valid:
                    self.repository.update_pending_delta_status(
                        delta_id=pending_delta_id,
                        status="rejected",
                    )
                    _emit_event(
                        event_callback=orchestration_event_callback,
                        payload={
                            "event": "pending_delta_status_updated",
                            "scope": self.repository.scope,
                            "delta_id": pending_delta_id,
                            "status": "rejected",
                        },
                    )
                    skip_reason: str = f"Delta for `{source_dto.path}` rejected by deterministic validation."
                else:
                    skip_reason = (
                        f"Delta for `{source_dto.path}` kept pending; "
                        f"dry_run={dry_run}, valid={report_dto.valid}."
                    )
                decisions.append(
                    ConsolidationDecisionDTO(
                        action="skip",
                        reason=skip_reason,
                    ),
                )
                continue

            apply_decisions: list[ConsolidationDecisionDTO] = apply_validated_delta(
                repository=self.repository,
                source_id=source_id,
                delta_dto=report_dto.accepted_delta,
                source_content=content,
            )
            self.repository.update_pending_delta_status(
                delta_id=pending_delta_id,
                status="applied",
            )
            _emit_event(
                event_callback=orchestration_event_callback,
                payload={
                    "event": "pending_delta_status_updated",
                    "scope": self.repository.scope,
                    "delta_id": pending_delta_id,
                    "status": "applied",
                },
            )
            decisions.extend(apply_decisions)
            applied_count += 1

        if not dry_run:
            decisions.extend(promote_recurrent_knowledge(repository=self.repository, min_sources=2))

        status: str = "completed_with_warnings" if errors else "completed"
        summary: str = (
            f"Dream inspected {len(changed_sources)} changed sources, proposed {proposed_count} deltas, "
            f"and applied {applied_count} deltas."
        )
        dream_dto: DreamRunDTO = DreamRunDTO(
            status=status,
            dry_run=dry_run,
            sources_seen=len(changed_sources),
            deltas_proposed=proposed_count,
            deltas_applied=applied_count,
            pending_delta_ids=pending_delta_ids,
            errors=errors,
            decisions=decisions,
            summary=summary,
        )
        dream_id: int = self.repository.record_dream_run(
            {
                "started_at": started_at,
                "finished_at": time.time(),
                "status": status,
                "dry_run": dry_run,
                "sources_seen": len(changed_sources),
                "deltas_proposed": proposed_count,
                "deltas_applied": applied_count,
                "errors": errors,
                "summary": summary,
            },
        )
        _emit_event(
            event_callback=orchestration_event_callback,
            payload={
                "event": "dream_run_recorded",
                "scope": self.repository.scope,
                "dream_id": dream_id,
                "sources_seen": len(changed_sources),
                "deltas_proposed": proposed_count,
                "deltas_applied": applied_count,
                "status": status,
            },
        )
        return dream_dto.model_copy(update={"id": dream_id})


def _delta_counts(delta_dto: KnowledgeDeltaDTO | None) -> dict[str, int]:
    """Return compact counts for dream verbose diagnostics."""
    if delta_dto is None:
        return {"Et": 0, "Re": 0, "Ale": 0, "Sch": 0}
    return {
        "Et": len(delta_dto.entities),
        "Re": len(delta_dto.relations),
        "Ale": len(delta_dto.aliases),
        "Sch": len(delta_dto.schema_suggestions),
    }


def _emit_event(
    event_callback: Callable[[dict[str, Any]], None] | None,
    payload: dict[str, Any],
) -> None:
    """Emit a structured dream diagnostic event."""
    if event_callback is not None:
        event_callback(payload)
