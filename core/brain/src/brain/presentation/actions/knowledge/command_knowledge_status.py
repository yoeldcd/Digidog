"""Action module to inspect the private knowledge graph runtime."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import json

# Application Modules Imports
from brain.application.knowledge.runtime.config_store import get_shared_config_path, load_knowledge_config
from brain.application.knowledge.runtime.scopes import get_shared_config_root, iter_knowledge_roots
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.presentation.terminal import render_placeholders, log_step




def handle(args: argparse.Namespace) -> int:
    """Print knowledge graph runtime status."""
    color_enabled: bool = getattr(args, "color", False)
    try:
        log_step(args, "Retrieving knowledge status...")
        scope_payloads: list[dict] = []
        shared_config_root = get_shared_config_root()
        config_dto = load_knowledge_config(knowledge_root=shared_config_root)
        shared_config_path = get_shared_config_path()
        for scope_name, knowledge_root in iter_knowledge_roots(scope=str(args.scope)):
            repository = KnowledgeRepository(knowledge_root=knowledge_root, scope=scope_name)
            scope_payload: dict = repository.status()
            scope_payload["knowledge_root"] = knowledge_root.as_posix()
            scope_payload["config_path"] = shared_config_path.as_posix()
            scope_payload["config"] = config_dto.model_dump(mode="json")
            scope_payloads.append(scope_payload)
        payload: dict = {"ok": True, "scopes": scope_payloads}

        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            output = ["__BOLD____CYAN__Knowledge Graph Status__RESET__"]
            for scope_payload in scope_payloads:
                counts = scope_payload["counts"]
                output.extend(
                    [
                        f"## __MAGENTA__{scope_payload['scope']}__RESET__",
                        f"  Root: __YELLOW__{scope_payload['knowledge_root']}__RESET__",
                        f"  DB: __YELLOW__{scope_payload['db_path']}__RESET__",
                        f"  Entities: __GREEN__{counts['entities']}__RESET__",
                        f"  Relations: __GREEN__{counts['relations']}__RESET__",
                        f"  Sources: __GREEN__{counts['sources']}__RESET__",
                        f"  Dream runs: __GREEN__{counts['dream_runs']}__RESET__",
                    ],
                )
            print("\n".join(render_placeholders(line, color_enabled) for line in output))
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(render_placeholders(f"__RED__Error: {exc}__RESET__", color_enabled))
        return 1
