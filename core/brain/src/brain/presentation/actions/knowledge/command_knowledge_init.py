# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to initialize the private knowledge graph runtime."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import json
from pathlib import Path

# Application Modules Imports
from brain.application.knowledge.runtime.config_store import (
    ensure_knowledge_config,
    ensure_knowledge_root,
    get_database_path,
    get_shared_config_path,
)
from brain.application.knowledge.runtime.scopes import get_shared_config_root, iter_knowledge_roots
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.presentation.terminal import render_placeholders, log_step




def handle(args: argparse.Namespace) -> int:
    """Initialize the knowledge graph runtime."""
    color_enabled: bool = getattr(args, "color", False)
    try:
        log_step(args, "[1/2] Preparing knowledge runtime...")
        selected_roots = iter_knowledge_roots(scope=str(args.scope))
        if getattr(args, "reset", False) and not getattr(args, "yes", False):
            confirmation: str = input("Reset selected private knowledge database(s)? (y/N): ").strip().lower()
            if confirmation not in ("y", "yes"):
                print("Aborted.")
                return 0

        status_payloads: list[dict] = []
        shared_config_root: Path = get_shared_config_root()
        config_dto = ensure_knowledge_config(knowledge_root=shared_config_root)
        shared_config_path: Path = get_shared_config_path()
        for scope_name, knowledge_root in selected_roots:
            ensure_knowledge_root(knowledge_root=knowledge_root)
            db_path = get_database_path(
                config_dto=config_dto,
                knowledge_root=knowledge_root,
                scope=scope_name,
            )
            if getattr(args, "reset", False):
                _delete_database_files(db_path=db_path)
            log_step(args, f"[2/2] Applying SQLite schema for {scope_name} scope...")
            repository = KnowledgeRepository(db_path=db_path, scope=scope_name)
            scope_payload: dict = repository.status()
            scope_payload["knowledge_root"] = knowledge_root.as_posix()
            scope_payload["config_path"] = shared_config_path.as_posix()
            status_payloads.append(scope_payload)

        status_payload: dict = {
            "ok": True,
            "scopes": status_payloads,
        }

        if args.json:
            print(json.dumps(status_payload, ensure_ascii=False, indent=2))
        else:
            for scope_payload in status_payloads:
                msg = (
                    f"__GREEN__Knowledge runtime ready__RESET__ "
                    f"({scope_payload['scope']}): __CYAN__{scope_payload['db_path']}__RESET__"
                )
                print(render_placeholders(msg, color_enabled))
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(render_placeholders(f"__RED__Error: {exc}__RESET__", color_enabled))
        return 1


def _delete_database_files(db_path: Path) -> None:
    """Delete a SQLite database and its sidecar files."""
    reset_paths = (
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
    )
    for candidate_path in reset_paths:
        if candidate_path.exists():
            candidate_path.unlink()
