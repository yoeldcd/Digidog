# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to inspect knowledge graph records."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import json
from typing import Any

# Application Modules Imports
from brain.application.knowledge.querying.show_payloads import (
    entity_payload,
    filter_text,
    listing_payload,
    overview_payload,
    selected_modes,
)
from brain.application.knowledge.runtime.scopes import iter_knowledge_roots
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.presentation.terminal import log_step, render_markdown, render_placeholders
from brain.presentation.views.knowledge.graph_show import render_entity, render_listing, render_overview


def handle(args: argparse.Namespace) -> int:
    """
    Show one entity, graph listings, or a compact graph overview.

    Args:
        args (argparse.Namespace): Parsed CLI arguments.

    Returns:
        int: Process exit code.
    """
    color_enabled: bool = getattr(args, "color", False)
    try:
        log_step(args, "Loading knowledge graph records...")
        modes = selected_modes(args)
        active_filter_text = filter_text(args=args, modes=modes)

        if str(args.scope) == "all":
            payload = _all_scopes_payload(
                modes=modes or {"entities", "relations", "classes"},
                filter_value=active_filter_text,
            )
            _print_payload(args=args, payload=payload, text=render_listing(payload), color_enabled=color_enabled)
            return 0

        repository = KnowledgeRepository(scope=str(args.scope))

        if args.entity is not None and not modes and not active_filter_text:
            payload = entity_payload(repository=repository, entity=str(args.entity))
            if payload is None:
                print(render_placeholders("__YELLOW__Knowledge entity not found.__RESET__", color_enabled))
                return 0
            _print_payload(args=args, payload=payload, text=render_entity(payload), color_enabled=color_enabled)
            return 0

        if not modes and not active_filter_text:
            payload = overview_payload(repository=repository, scope=str(args.scope))
            _print_payload(args=args, payload=payload, text=render_overview(payload), color_enabled=color_enabled)
            return 0

        payload = listing_payload(
            repository=repository,
            scope=str(args.scope),
            modes=modes or {"entities", "relations", "classes"},
            filter_value=active_filter_text,
        )
        _print_payload(args=args, payload=payload, text=render_listing(payload), color_enabled=color_enabled)
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(render_placeholders(f"__RED__Error: {exc}__RESET__", color_enabled))
        return 1


def _all_scopes_payload(modes: set[str], filter_value: str) -> dict[str, Any]:
    """Aggregate listing rows from both physical knowledge databases."""
    payload: dict[str, Any] = {
        "ok": True,
        "scope": "all",
        "filter": filter_value,
        "entities": [],
        "relations": [],
        "classes": [],
    }
    for scope_name, knowledge_root in iter_knowledge_roots(scope="all"):
        repository = KnowledgeRepository(knowledge_root=knowledge_root, scope=scope_name)
        scoped = listing_payload(
            repository=repository,
            scope=scope_name,
            modes=modes,
            filter_value=filter_value,
        )
        payload["entities"].extend(
            _scope_entity(row=row, scope=scope_name)
            for row in scoped.get("entities", [])
        )
        payload["relations"].extend(
            _scope_relation(row=row, scope=scope_name)
            for row in scoped.get("relations", [])
        )
        payload["classes"].extend(
            {**row, "knowledge_scope": scope_name, "id": f"{scope_name}:class:{row.get('name', '')}"}
            for row in scoped.get("classes", [])
        )
    return {key: value for key, value in payload.items() if key not in {"entities", "relations", "classes"} or key in modes}


def _scope_entity(row: dict[str, Any], scope: str) -> dict[str, Any]:
    """Namespace one entity identifier while retaining its canonical identity."""
    entity_id = str(row.get("id") or row.get("entity_id") or "")
    return {
        **row,
        "knowledge_scope": scope,
        "entity_id": f"{scope}:{entity_id}",
        "id": f"{scope}:{entity_id}",
        "physical_entity_id": entity_id,
    }


def _scope_relation(row: dict[str, Any], scope: str) -> dict[str, Any]:
    """Namespace a relation and both endpoints for collision-safe aggregation."""
    relation_id = str(row.get("id") or "")
    subject_id = str(row.get("subject_entity_id") or "")
    object_id = str(row.get("object_entity_id") or "")
    return {
        **row,
        "knowledge_scope": scope,
        "id": f"{scope}:{relation_id}",
        "physical_relation_id": relation_id,
        "subject_entity_id": f"{scope}:{subject_id}",
        "object_entity_id": f"{scope}:{object_id}",
    }


def _print_payload(args: argparse.Namespace, payload: dict[str, Any], text: str, color_enabled: bool) -> None:
    """
    Print JSON or human-readable Markdown.

    Args:
        args (argparse.Namespace): Parsed CLI arguments.
        payload (dict[str, Any]): JSON-safe command payload.
        text (str): Human-readable Markdown output.
        color_enabled (bool): Whether terminal color placeholders should render.
    """
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(render_markdown(text, color_enabled))
