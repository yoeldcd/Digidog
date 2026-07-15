"""Runtime store migration orchestration."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path

# Application Modules Imports
from brain.infrastructure.runtime.paths import (
    get_agent_home,
    get_global_database_dir,
    get_knowledge_database_path,
    get_local_database_dir,
    get_vectorstore_dir,
)
from brain.infrastructure.runtime.migration_dtos import RuntimeMigrationReportDTO
from brain.infrastructure.runtime.migration_steps import (
    migrate_directory,
    migrate_sqlite_database,
    remove_derived_json,
    remove_empty_legacy_directory,
)
from brain.infrastructure.runtime.source_state_import import import_source_state_json


def migrate_brain_runtime_stores(
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> RuntimeMigrationReportDTO:
    """
    Move legacy runtime stores into the current database layout.

    Args:
        agent_home: Optional shared agent home.
        workspace_root: Optional workspace root.

    Returns:
        RuntimeMigrationReportDTO: Completed actions and warnings.
    """
    resolved_agent_home: Path = get_agent_home(agent_home=agent_home)
    resolved_workspace_root: Path = (workspace_root or Path.cwd()).resolve()
    report = RuntimeMigrationReportDTO()

    get_global_database_dir()
    get_local_database_dir(workspace_root=resolved_workspace_root)

    migrate_sqlite_database(
        legacy_candidates=[
            resolved_workspace_root / "$agent" / "data" / "knowledge" / "knowledge.db",
            resolved_workspace_root / "$agent" / "data" / "knowledge" / "angi_kg.sqlite3",
        ],
        target=get_knowledge_database_path(scope="local", workspace_root=resolved_workspace_root),
        report=report,
    )
    migrate_directory(
        source=resolved_workspace_root / "$agent" / "data" / "vectorstore",
        target=get_vectorstore_dir(scope="local", workspace_root=resolved_workspace_root),
        report=report,
    )
    import_source_state_json(
        source_state_path=resolved_workspace_root / "$agent" / "data" / "knowledge" / "source_state.json",
        scope="local",
        agent_home=resolved_agent_home,
        workspace_root=resolved_workspace_root,
        report=report,
    )
    remove_derived_json(source=resolved_workspace_root / "$agent" / "logs" / "index.json", report=report)
    remove_empty_legacy_directory(source=resolved_workspace_root / "$agent" / "data" / "knowledge", report=report)
    remove_empty_legacy_directory(source=resolved_workspace_root / "$agent" / "data" / "vectorstore", report=report)
    return report
