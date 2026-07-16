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
        repository = KnowledgeRepository(scope=str(args.scope))
        modes = selected_modes(args)
        active_filter_text = filter_text(args=args, modes=modes)

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
