"""Action module to export the private knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import json

# Application Modules Imports
from brain.application.knowledge.runtime.scopes import iter_knowledge_roots
from brain.presentation.views.knowledge.jsonld_export import export_jsonld
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.presentation.terminal import render_placeholders, log_step




def handle(args: argparse.Namespace) -> int:
    """Export the knowledge graph."""
    color_enabled: bool = getattr(args, "color", False)
    try:
        log_step(args, "Exporting knowledge graph...")
        if args.format.lower() != "jsonld":
            print(render_placeholders("__RED__Error: only jsonld export is supported.__RESET__", color_enabled))
            return 1
        exports: dict = {}
        for scope_name, knowledge_root in iter_knowledge_roots(scope=str(args.scope)):
            repository = KnowledgeRepository(knowledge_root=knowledge_root, scope=scope_name)
            exports[scope_name] = export_jsonld(repository=repository)
        payload = exports if str(args.scope).casefold().strip() == "all" else next(iter(exports.values()))
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(render_placeholders(f"__RED__Error: {exc}__RESET__", color_enabled))
        return 1
