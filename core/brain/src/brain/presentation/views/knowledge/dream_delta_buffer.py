# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Pending delta buffer views for knowledge dream runs."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
from typing import Any

# Application Modules Imports
from brain.presentation.views.knowledge.delta_review import render_delta_review
from brain.application.knowledge.pipeline.delta_status import is_delta_applicable, is_delta_legacy
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.presentation.terminal import render_placeholders
from brain.presentation.views.knowledge.diagnostic_formatting import join_delta_ids


def handle_pending_delta_buffer(
    args: argparse.Namespace,
    repository: KnowledgeRepository,
    scope_name: str,
    pending_rows: list[dict[str, Any]],
    color_enabled: bool,
) -> int:
    """
    Stop dream when pending deltas must be resolved first.

    Args:
        args (argparse.Namespace): Parsed command arguments.
        repository (KnowledgeRepository): Knowledge repository.
        scope_name (str): Active writable scope.
        pending_rows (list[dict[str, Any]]): Pending deltas blocking a new dream pass.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        int: Nonzero process status indicating a blocked dream cycle.
    """
    delta_status: dict[str, Any] = build_delta_status(scope_name=scope_name, rows=pending_rows)
    if bool(args.json):
        return 2

    print(
        render_placeholders(
            "__YELLOW__Dream blocked__RESET__: pending knowledge deltas must be applied or deleted first.",
            color_enabled,
        ),
    )
    print(render_delta_status(delta_status=delta_status, color_enabled=color_enabled))
    print(render_delta_buffer_helper(scope_name=scope_name, color_enabled=color_enabled))
    print(
        render_delta_review(
            rows=pending_rows[:20],
            color_enabled=color_enabled,
            title="Pending Delta Buffer",
            compact=True,
            show_review_hint=False,
            entity_rows=repository.list_entities(),
        ),
    )
    return 2


def build_pending_delta_buffer_payload(scope_name: str, pending_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build the JSON payload for a scope blocked by pending deltas.

    Args:
        scope_name (str): Active knowledge scope.
        pending_rows (list[dict[str, Any]]): Pending delta rows.

    Returns:
        dict[str, Any]: Machine-readable blocking status.
    """
    return {
        "ok": False,
        "scope": scope_name,
        "blocked": True,
        "reason": "pending_delta_buffer_not_empty",
        "delta_status": build_delta_status(scope_name=scope_name, rows=pending_rows),
        "helper": build_delta_buffer_helper(scope_name=scope_name),
        "pending_deltas": pending_rows,
    }


def build_delta_status(scope_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build a compact lifecycle summary for pending delta buffers.

    Args:
        scope_name (str): Active knowledge scope.
        rows (list[dict[str, Any]]): Pending delta rows.

    Returns:
        dict[str, Any]: Status counts and relevant delta IDs.
    """
    applicable_ids: list[int] = []
    legacy_ids: list[int] = []
    blocked_ids: list[int] = []
    for row in rows:
        row_id: int = int(row["id"])
        if is_delta_applicable(row=row):
            applicable_ids.append(row_id)
        elif is_delta_legacy(row=row):
            legacy_ids.append(row_id)
        else:
            blocked_ids.append(row_id)
    return {
        "scope": scope_name,
        "pending": len(rows),
        "applicable": len(applicable_ids),
        "legacy": len(legacy_ids),
        "blocked": len(blocked_ids),
        "applicable_ids": applicable_ids,
        "legacy_ids": legacy_ids,
        "blocked_ids": blocked_ids,
    }


def render_delta_status(delta_status: dict[str, Any], color_enabled: bool) -> str:
    """
    Render pending delta lifecycle status for the terminal.

    Args:
        delta_status (dict[str, Any]): Status produced by `build_delta_status`.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        str: Human-readable status block.
    """
    lines: list[str] = [
        render_placeholders("# __CYAN__delta-status__RESET__", color_enabled),
        render_placeholders(f"scope: __MAGENTA__{delta_status['scope']}__RESET__", color_enabled),
        render_placeholders(f"pending: __CYAN__{delta_status['pending']}__RESET__", color_enabled),
        render_placeholders(f"applicable: __GREEN__{delta_status['applicable']}__RESET__", color_enabled),
        render_placeholders(f"legacy: __YELLOW__{delta_status['legacy']}__RESET__", color_enabled),
        render_placeholders(f"blocked: __RED__{delta_status['blocked']}__RESET__", color_enabled),
    ]
    if delta_status["applicable_ids"]:
        lines.append(
            render_placeholders(
                f"applicable_ids: __CYAN__{join_delta_ids(delta_status['applicable_ids'])}__RESET__",
                color_enabled,
            ),
        )
    if delta_status["legacy_ids"]:
        lines.append(
            render_placeholders(
                f"legacy_ids: __CYAN__{join_delta_ids(delta_status['legacy_ids'])}__RESET__",
                color_enabled,
            ),
        )
    if delta_status["blocked_ids"]:
        lines.append(
            render_placeholders(
                f"blocked_ids: __CYAN__{join_delta_ids(delta_status['blocked_ids'])}__RESET__",
                color_enabled,
            ),
        )
    return "\n".join(lines)


def build_delta_buffer_helper(scope_name: str) -> dict[str, str]:
    """
    Build exact operator commands for resolving a pending delta buffer.

    Args:
        scope_name (str): Active knowledge scope.

    Returns:
        dict[str, str]: Inspect, apply, and delete helper commands.
    """
    return {
        "inspect": f"py '$agent/scripts/brain.py' knowledge-deltas --scope {scope_name} --status pending --limit 20 --color",
        "apply": f"py '$agent/scripts/brain.py' knowledge-deltas --scope {scope_name} --status pending --limit 20 --color",
        "delete": f"py '$agent/scripts/brain.py' delete-knowledge-deltas --scope {scope_name} --all --status pending --color",
    }


def render_delta_buffer_helper(scope_name: str, color_enabled: bool) -> str:
    """
    Render operator helper commands for resolving pending deltas.

    Args:
        scope_name (str): Active knowledge scope.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        str: Human-readable helper block.
    """
    helper: dict[str, str] = build_delta_buffer_helper(scope_name=scope_name)
    lines: list[str] = [render_placeholders("# __GREEN__helper__RESET__", color_enabled)]
    for key, command in helper.items():
        lines.append(render_placeholders(f"{key}: __BLUE__\"{command}\"__RESET__", color_enabled))
    return "\n".join(lines)
