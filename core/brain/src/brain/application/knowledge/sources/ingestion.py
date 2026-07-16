# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Knowledge source ingestion service."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path
from typing import Any, Callable

# Application Modules Imports
from brain.application.knowledge.sources.discovery import discover_sources
from brain.application.knowledge.sources.file_reader import read_source_text
from brain.application.knowledge.sources.freshness import changed_source_paths
from brain.application.knowledge.sources.models import KNOWLEDGE_CONSUMER_NAME, SourceCandidate
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.infrastructure.sources.registry.consumers import remove_consumer_sources


def ingest_sources(
    repository: KnowledgeRepository,
    domain: str = "all",
    limit: int | None = None,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
    source_scope: str | None = None,
    force_all: bool = False,
    event_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict:
    """
    Return source content changed for the knowledge graph consumer.

    Args:
        repository: Knowledge repository that owns the consumer state file.
        domain: Source domain filter.
        limit: Optional maximum source count.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.
        source_scope: Optional source scope override.
        force_all: Whether every discovered source should be returned as changed.
        event_callback: Optional structured diagnostic event sink.

    Returns:
        dict: Ingestion summary with changed source records.
    """
    resolved_source_scope: str = source_scope or repository.scope
    _emit_event(
        event_callback=event_callback,
        payload={
            "event": "ingest_start",
            "scope": resolved_source_scope,
            "domain": domain,
            "limit": limit,
            "force_all": force_all,
        },
    )
    source_candidates: list[SourceCandidate] = discover_sources(
        domain=domain,
        agent_home=agent_home,
        workspace_root=workspace_root,
        source_scope=resolved_source_scope,
    )
    for source_candidate in source_candidates:
        _emit_source_event(
            event_callback=event_callback,
            event_name="source_discovered",
            source_candidate=source_candidate,
        )
    changed_paths, deleted_paths = changed_source_paths(
        repository=repository,
        domain=domain,
        agent_home=agent_home,
        workspace_root=workspace_root,
        source_scope=resolved_source_scope,
        force_all=force_all,
    )
    _emit_event(
        event_callback=event_callback,
        payload={
            "event": "ingest_diff",
            "scope": resolved_source_scope,
            "domain": domain,
            "discovered": len(source_candidates),
            "changed": len(changed_paths),
            "deleted": len(deleted_paths),
        },
    )
    if deleted_paths:
        remove_consumer_sources(
            scope=resolved_source_scope,
            consumer_name=KNOWLEDGE_CONSUMER_NAME,
            source_paths=deleted_paths,
            agent_home=agent_home,
            workspace_root=workspace_root,
        )
        for deleted_path in deleted_paths:
            _emit_event(
                event_callback=event_callback,
                payload={
                    "event": "source_deleted",
                    "scope": resolved_source_scope,
                    "source_path": deleted_path,
                },
            )

    changed_sources: list[dict] = []
    skipped_count: int = 0
    for source_candidate in source_candidates:
        source_path: str = source_candidate.source_dto.path
        if source_path not in changed_paths:
            skipped_count += 1
            _emit_source_event(
                event_callback=event_callback,
                event_name="source_skipped",
                source_candidate=source_candidate,
                reason="unchanged_for_consumer",
            )
            continue
        _emit_source_event(
            event_callback=event_callback,
            event_name="source_read_start",
            source_candidate=source_candidate,
        )
        content = read_source_text(path=source_candidate.path)
        changed_sources.append(
            {
                "source": source_candidate.source_dto,
                "content": content,
                "mtime": source_candidate.mtime,
            },
        )
        _emit_source_event(
            event_callback=event_callback,
            event_name="source_read",
            source_candidate=source_candidate,
            chars=len(content),
        )
        if limit is not None and len(changed_sources) >= limit:
            _emit_event(
                event_callback=event_callback,
                payload={
                    "event": "ingest_limit_reached",
                    "scope": resolved_source_scope,
                    "limit": limit,
                },
            )
            break

    _emit_event(
        event_callback=event_callback,
        payload={
            "event": "ingest_complete",
            "scope": resolved_source_scope,
            "domain": domain,
            "discovered": len(source_candidates),
            "changed": len(changed_sources),
            "skipped": skipped_count,
            "deleted": len(deleted_paths),
        },
    )
    return {
        "ok": True,
        "discovered": len(source_candidates),
        "changed": len(changed_sources),
        "skipped": skipped_count,
        "deleted": len(deleted_paths),
        "changed_sources": changed_sources,
    }


def _emit_source_event(
    event_callback: Callable[[dict[str, Any]], None] | None,
    event_name: str,
    source_candidate: SourceCandidate,
    **extra: Any,
) -> None:
    """Emit one source-candidate diagnostic event."""
    payload: dict[str, Any] = {
        "event": event_name,
        "source_path": source_candidate.source_dto.path,
        "source_type": source_candidate.source_dto.source_type,
        "title": source_candidate.source_dto.title,
        "filesystem_path": source_candidate.path.as_posix(),
        "mtime": source_candidate.mtime,
    }
    payload.update(extra)
    _emit_event(event_callback=event_callback, payload=payload)


def _emit_event(
    event_callback: Callable[[dict[str, Any]], None] | None,
    payload: dict[str, Any],
) -> None:
    """Emit a structured ingestion diagnostic when verbose logging is enabled by the caller."""
    if event_callback is not None:
        event_callback(payload)
