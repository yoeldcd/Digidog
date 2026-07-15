"""Legacy source-state JSON import helpers for runtime migration."""

from __future__ import annotations

# Standard Libraries Imports
import json
from pathlib import Path
from typing import Any, Iterable

# Application Modules Imports
from brain.infrastructure.runtime.paths import get_source_registry_path
from brain.infrastructure.runtime.migration_dtos import RuntimeMigrationReportDTO
from brain.infrastructure.runtime.migration_steps import record
from brain.infrastructure.sources.registry.consumers import mark_consumer_source_processed


def import_source_state_json(
    source_state_path: Path,
    scope: str,
    agent_home: Path,
    workspace_root: Path,
    report: RuntimeMigrationReportDTO,
) -> None:
    """Import legacy source-state JSON into `brain_sources.db`."""
    if not source_state_path.exists():
        return
    try:
        raw_data: Any = json.loads(source_state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report.warnings.append(f"Could not parse legacy source state {source_state_path}: {exc}")
        return

    imported_count: int = 0
    for consumer_name, source_path, mtime in iter_source_state_entries(raw_data=raw_data):
        mark_consumer_source_processed(
            scope=scope,
            consumer_name=consumer_name,
            source_path=canonical_source_path(source_path=source_path),
            mtime=mtime,
            agent_home=agent_home,
            workspace_root=workspace_root,
        )
        imported_count += 1

    source_state_path.unlink()
    record(
        report=report,
        action="imported",
        source=source_state_path,
        target=get_source_registry_path(scope=scope, agent_home=agent_home, workspace_root=workspace_root),
        detail=f"legacy source-state rows: {imported_count}",
    )


def iter_source_state_entries(raw_data: Any) -> Iterable[tuple[str, str, float]]:
    """Yield consumer/path/mtime triples from common legacy source-state shapes."""
    if not isinstance(raw_data, dict):
        return
    for consumer_name, consumer_payload in raw_data.items():
        if not isinstance(consumer_name, str) or not isinstance(consumer_payload, dict):
            continue
        source_payload: Any = consumer_payload.get("sources", consumer_payload)
        if not isinstance(source_payload, dict):
            continue
        for source_path, state_payload in source_payload.items():
            if not isinstance(source_path, str):
                continue
            mtime = extract_mtime(state_payload=state_payload)
            if mtime is not None:
                yield consumer_name, source_path, mtime


def canonical_source_path(source_path: str) -> str:
    """Return current stable source path for imported legacy state rows."""
    if source_path.startswith("$agent/logs/") and source_path.endswith(".log") and not source_path.endswith(".log.md"):
        return f"{source_path}.md"
    return source_path


def extract_mtime(state_payload: Any) -> float | None:
    """Extract an mtime from one legacy source-state value."""
    if isinstance(state_payload, int | float):
        return float(state_payload)
    if not isinstance(state_payload, dict):
        return None
    for key in ("processed_mtime", "mtime"):
        value = state_payload.get(key)
        if isinstance(value, int | float):
            return float(value)
    return None
