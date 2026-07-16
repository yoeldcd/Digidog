# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Filesystem discovery for knowledge source candidates."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path

# Application Modules Imports
from brain.application.knowledge.models.dtos.sources import SourceDTO
from brain.application.knowledge.runtime.scopes import normalize_knowledge_scope
from brain.application.knowledge.sources.models import SOURCE_DOMAINS, WORKSPACE_LOG_SOURCE_TYPE, SourceCandidate
from brain.domain.sources.classification import memory_source_type
from brain.domain.sources.models import SourceRegistryRecordDTO
from brain.infrastructure.runtime.paths import get_agent_home, get_workspace_root
from brain.infrastructure.sources.scanning import scan_log_source_records, scan_memory_source_records


def discover_sources(
    domain: str = "all",
    limit: int | None = None,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
    source_scope: str = "global",
) -> list[SourceCandidate]:
    """
    Discover source files from current filesystem mtimes.

    Args:
        domain: Source domain filter.
        limit: Optional maximum source count.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.
        source_scope: Physical knowledge scope whose corpus should be discovered.

    Returns:
        list[SourceCandidate]: Source metadata paired with mtime and file path.
    """
    normalized_domain: str = domain.casefold().strip()
    if normalized_domain not in SOURCE_DOMAINS:
        raise ValueError(f"Unsupported knowledge source domain: {domain}")

    normalized_scope: str = normalize_knowledge_scope(scope=source_scope)
    resolved_agent_home: Path = agent_home or get_agent_home()
    resolved_workspace_root: Path = workspace_root or get_workspace_root()
    discovered: list[SourceCandidate] = []

    if normalized_scope == "global" and normalized_domain in ("all", "memory", "diary", "profiles"):
        discovered.extend(
            _discover_memory_candidates(agent_home=resolved_agent_home, domain=normalized_domain),
        )

    if normalized_scope == "local" and normalized_domain in ("all", "logs"):
        _ensure_log_database_for_discovery(workspace_root=resolved_workspace_root)
        discovered.extend(_discover_log_candidates(workspace_root=resolved_workspace_root))

    discovered.sort(key=lambda candidate: candidate.mtime, reverse=True)
    if limit is not None:
        return discovered[:limit]
    return discovered


def _discover_memory_candidates(agent_home: Path, domain: str) -> list[SourceCandidate]:
    """
    Discover global memory candidates from filesystem mtimes.

    Args:
        agent_home: Agent home directory.
        domain: Source domain filter.

    Returns:
        list[SourceCandidate]: Memory-backed source candidates.
    """
    records: list[SourceRegistryRecordDTO] = scan_memory_source_records(agent_home=agent_home)
    candidates: list[SourceCandidate] = []
    for record in records:
        source_type: str = memory_source_type(source_path=record.path)
        if domain != "all" and source_type != domain:
            continue
        file_path: Path = agent_home / Path(record.path)
        if not file_path.exists() or not file_path.is_file():
            continue
        candidates.append(
            SourceCandidate(
                source_dto=SourceDTO(
                    source_type=source_type,
                    path=record.path,
                    title=file_path.stem,
                    active=True,
                ),
                path=file_path,
                mtime=record.mtime,
            ),
        )
    return candidates


def _ensure_log_database_for_discovery(workspace_root: Path) -> None:
    """
    Populate the DB-backed log source before local log discovery when needed.

    Args:
        workspace_root: Workspace root directory.
    """
    try:
        from brain.application.logs.index_service import migrate_legacy_log_files_to_database, migrate_log_files_to_database
        from brain.application.logs.store import log_database_summary

        entry_count, _domain_count, _latest_count = log_database_summary(workspace_root=workspace_root)
        if entry_count > 0:
            return
        migrate_legacy_log_files_to_database(workspace_root=workspace_root, archive_sources=False)
        migrate_log_files_to_database(workspace_root=workspace_root, archive_sources=False)
    except Exception:
        return


def _discover_log_candidates(workspace_root: Path) -> list[SourceCandidate]:
    """
    Discover local log candidates from filesystem mtimes.

    Args:
        workspace_root: Workspace root directory.

    Returns:
        list[SourceCandidate]: Log-backed source candidates.
    """
    records: list[SourceRegistryRecordDTO] = scan_log_source_records(workspace_root=workspace_root)
    candidates: list[SourceCandidate] = []
    for record in records:
        file_path: Path = workspace_root / Path(record.path)
        if not file_path.exists() or not file_path.is_file():
            continue
        candidates.append(
            SourceCandidate(
                source_dto=SourceDTO(
                    source_type=WORKSPACE_LOG_SOURCE_TYPE,
                    path=record.path,
                    title=file_path.stem,
                    active=True,
                ),
                path=file_path,
                mtime=record.mtime,
            ),
        )
    return candidates
