# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Source freshness checks for the knowledge graph consumer."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path

# Application Modules Imports
from brain.application.knowledge.runtime.scopes import normalize_knowledge_scope
from brain.application.knowledge.sources.discovery import discover_sources
from brain.application.knowledge.sources.models import KNOWLEDGE_CONSUMER_NAME, SourceCandidate
from brain.application.sources.registry_service import diff_sources_for_consumer
from brain.domain.sources.classification import memory_source_type
from brain.domain.sources.models import SourceRegistryRecordDTO
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.infrastructure.runtime.paths import get_agent_home, get_source_registry_path, get_workspace_root
from brain.infrastructure.sources.registry.consumers import list_changed_records_for_consumer, mark_consumer_source_processed
from brain.infrastructure.sources.registry.records import refresh_registry_records
from brain.infrastructure.sources.scanning import scan_log_source_records


def check_source_updates(
    repository: KnowledgeRepository,
    domain: str = "all",
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
    source_scope: str | None = None,
) -> dict:
    """
    Compare source registry mtimes with the knowledge graph consumer state without reading files.

    Args:
        repository: Knowledge repository that owns the consumer state file.
        domain: Source domain filter.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.
        source_scope: Optional source scope override.

    Returns:
        dict: Fast diff summary for query-time staleness checks.
    """
    resolved_source_scope: str = source_scope or repository.scope
    candidates: list[SourceCandidate] = discover_sources(
        domain=domain,
        agent_home=agent_home,
        workspace_root=workspace_root,
        source_scope=resolved_source_scope,
    )
    changed_paths, deleted_paths = changed_source_paths(
        repository=repository,
        domain=domain,
        agent_home=agent_home,
        workspace_root=workspace_root,
        source_scope=resolved_source_scope,
        force_all=False,
    )
    relevant_changed_paths: set[str] = {
        candidate.source_dto.path
        for candidate in candidates
        if candidate.source_dto.path in changed_paths
    }
    return {
        "ok": True,
        "discovered": len(candidates),
        "changed": len(relevant_changed_paths),
        "deleted": len(deleted_paths),
        "changed_paths": sorted(relevant_changed_paths),
        "deleted_paths": deleted_paths,
    }


def mark_source_processed(repository: KnowledgeRepository, source_path: str, mtime: float) -> None:
    """
    Mark one source as processed by the knowledge graph consumer.

    Args:
        repository: Knowledge repository that owns the consumer state file.
        source_path: Stable source path.
        mtime: Processed filesystem modification timestamp.
    """
    mark_consumer_source_processed(
        scope=repository.scope,
        consumer_name=KNOWLEDGE_CONSUMER_NAME,
        source_path=source_path,
        mtime=mtime,
    )


def changed_source_paths(
    repository: KnowledgeRepository,
    domain: str,
    agent_home: Path | None,
    workspace_root: Path | None,
    source_scope: str,
    force_all: bool,
) -> tuple[set[str], list[str]]:
    """
    Return changed source paths by comparing source registries to consumer state.

    Args:
        repository: Knowledge repository.
        domain: Source domain filter.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.
        source_scope: Physical source scope.
        force_all: Whether every indexed source should be marked changed.

    Returns:
        tuple[set[str], list[str]]: Changed paths and deleted paths.
    """
    normalized_domain: str = domain.casefold().strip()
    normalized_scope: str = normalize_knowledge_scope(scope=source_scope)
    resolved_agent_home: Path = agent_home or get_agent_home()
    resolved_workspace_root: Path = workspace_root or get_workspace_root()
    changed_paths: set[str] = set()
    deleted_paths: list[str] = []

    if normalized_scope == "global" and normalized_domain in ("all", "memory", "diary", "profiles"):
        memory_check = diff_sources_for_consumer(
            scope=normalized_scope,
            consumer_name=KNOWLEDGE_CONSUMER_NAME,
            root=resolved_agent_home / "memory",
            root_prefix="memory",
            suffixes=(".md",),
            source_type_resolver=memory_source_type,
            force_all=force_all,
            agent_home=resolved_agent_home,
            workspace_root=resolved_workspace_root,
        )
        changed_paths.update(
            record.path
            for record in memory_check.changed
            if _record_matches_domain(record=record, domain=normalized_domain)
        )
        deleted_paths.extend(memory_check.deleted)

    if normalized_scope == "local" and normalized_domain in ("all", "logs"):
        records = scan_log_source_records(workspace_root=resolved_workspace_root)
        root_prefix = "$agent/database" if any(record.path.startswith("$agent/database/") for record in records) else "$agent/logs"
        registry_path = get_source_registry_path(
            scope=normalized_scope,
            agent_home=resolved_agent_home,
            workspace_root=resolved_workspace_root,
        )
        refresh_registry_records(
            registry_path=registry_path,
            scope=normalized_scope,
            records=records,
            root_prefix=root_prefix,
        )
        changed_records, current_deleted = list_changed_records_for_consumer(
            registry_path=registry_path,
            scope=normalized_scope,
            consumer_name=KNOWLEDGE_CONSUMER_NAME,
            root_prefix=root_prefix,
            force_all=force_all,
        )
        changed_paths.update(record.path for record in changed_records)
        deleted_paths.extend(current_deleted)
        if root_prefix == "$agent/database":
            refresh_registry_records(
                registry_path=registry_path,
                scope=normalized_scope,
                records=[],
                root_prefix="$agent/logs",
            )
            _old_changed, old_deleted = list_changed_records_for_consumer(
                registry_path=registry_path,
                scope=normalized_scope,
                consumer_name=KNOWLEDGE_CONSUMER_NAME,
                root_prefix="$agent/logs",
                force_all=False,
            )
            deleted_paths.extend(old_deleted)

    return changed_paths, sorted(set(deleted_paths))


def _record_matches_domain(record: SourceRegistryRecordDTO, domain: str) -> bool:
    """
    Return whether a memory index record belongs to the selected domain.

    Args:
        record: Source index record.
        domain: Normalized domain selector.

    Returns:
        bool: True when the record should be considered.
    """
    if domain == "all":
        return True
    return memory_source_type(source_path=record.path) == domain
