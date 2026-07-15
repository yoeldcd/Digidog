"""Interactive prune flow for knowledge graph recreation."""

from __future__ import annotations

# Standard Libraries Imports
import sys
from pathlib import Path
from typing import Any

# Application Modules Imports
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.presentation.terminal import render_placeholders


def confirm_and_prune_knowledge_graph(
    repository: KnowledgeRepository,
    color_enabled: bool,
    json_enabled: bool,
) -> KnowledgeRepository | None:
    """
    Show current graph status, confirm pruning, and recreate the knowledge database.

    Args:
        repository (KnowledgeRepository): Existing repository used to read status.
        color_enabled (bool): Whether ANSI color placeholders should render.
        json_enabled (bool): Whether command output is JSON-oriented.

    Returns:
        KnowledgeRepository | None: New repository after prune, or None when aborted.
    """
    status_payload: dict[str, Any] = repository.status()
    if json_enabled:
        return None

    print(render_prune_status(status_payload=status_payload, color_enabled=color_enabled))
    if not sys.stdin.isatty():
        print(
            render_placeholders(
                "__YELLOW__Prune requires interactive confirmation after status review.__RESET__",
                color_enabled,
            ),
        )
        return None

    confirmation = input("Recreate the entire knowledge graph? Type RECREATE to confirm: ").strip()
    if confirmation != "RECREATE":
        print(render_placeholders("__YELLOW__Prune aborted.__RESET__", color_enabled))
        return None

    db_path: Path = delete_knowledge_database_files(db_path=repository.db_path)
    print(
        render_placeholders(
            f"__GREEN__Knowledge graph pruned__RESET__: __CYAN__{db_path.as_posix()}__RESET__",
            color_enabled,
        ),
    )
    return KnowledgeRepository(db_path=db_path)


def delete_knowledge_database_files(db_path: Path) -> Path:
    """
    Delete the configured knowledge database and SQLite sidecar files.

    Args:
        db_path (Path): Active scope database path.

    Returns:
        Path: Recreated SQLite database path.
    """
    candidate_paths: tuple[Path, ...] = (
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
    )
    for candidate_path in candidate_paths:
        if candidate_path.exists():
            candidate_path.unlink()
    return db_path


def render_prune_status(status_payload: dict[str, Any], color_enabled: bool) -> str:
    """
    Render the pre-prune knowledge graph status.

    Args:
        status_payload (dict[str, Any]): Repository status payload.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        str: Human-readable status block.
    """
    counts: dict[str, int] = status_payload.get("counts", {})
    lines: list[str] = [
        render_placeholders("# __YELLOW__Knowledge Graph Prune Review__RESET__", color_enabled),
        render_placeholders(f"db: __CYAN__{status_payload.get('db_path', '')}__RESET__", color_enabled),
    ]
    for key in sorted(counts):
        lines.append(render_placeholders(f"{key}: __CYAN__{counts[key]}__RESET__", color_enabled))
    return "\n".join(lines)
