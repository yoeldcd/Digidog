"""Action module to delete unwanted knowledge graph deltas."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import json
import sys
from typing import Any

# Application Modules Imports
from brain.presentation.views.knowledge.delta_review import render_delta_review
from brain.application.knowledge.pipeline.delta_status import is_delta_legacy
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.presentation.terminal import render_placeholders




def handle(args: argparse.Namespace) -> int:
    """
    Delete unwanted knowledge graph deltas.

    Args:
        args (argparse.Namespace): Parsed command arguments.

    Returns:
        int: Process status code.
    """
    color_enabled: bool = getattr(args, "color", False)
    repository = KnowledgeRepository(scope=str(args.scope))
    candidate_rows: list[dict[str, Any]] = _select_candidate_rows(repository=repository, args=args)
    candidate_ids: list[int] = [int(row["id"]) for row in candidate_rows]

    if not candidate_rows:
        return _print_summary(
            args=args,
            color_enabled=color_enabled,
            payload={"deleted": 0, "ids": [], "message": "No matching deltas found."},
        )

    if not args.json:
        print(
            render_delta_review(
                rows=candidate_rows,
                color_enabled=color_enabled,
                title="Knowledge Deltas Selected For Deletion",
                compact=True,
                entity_rows=repository.list_entities(),
            ),
        )
    if not _confirm_deletion(args=args, candidate_ids=candidate_ids):
        return _print_summary(
            args=args,
            color_enabled=color_enabled,
            payload={"deleted": 0, "ids": candidate_ids, "message": "Deletion aborted."},
        )

    deleted_count = repository.delete_pending_deltas(delta_ids=candidate_ids)
    print(
        render_placeholders(
            f"__GREEN__Deleted {deleted_count} knowledge deltas.__RESET__",
            color_enabled,
        ),
    )
    return 0


def _select_candidate_rows(repository: KnowledgeRepository, args: argparse.Namespace) -> list[dict[str, Any]]:
    """
    Select deletion candidate rows.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        args (argparse.Namespace): Parsed command arguments.

    Returns:
        list[dict[str, Any]]: Pending delta rows selected for deletion.
    """
    explicit_ids: list[int] = [int(delta_id) for delta_id in getattr(args, "ids", [])]
    if explicit_ids:
        return [
            row
            for row in (repository.get_pending_delta(delta_id=delta_id) for delta_id in explicit_ids)
            if row is not None
        ]

    status_filter: str = str(args.status or "all")
    rows: list[dict[str, Any]] = repository.list_pending_deltas(limit=int(args.limit), status=status_filter)
    if bool(args.all):
        return rows
    if bool(args.legacy):
        return [row for row in rows if is_delta_legacy(row=row)]
    if args.status is not None:
        return rows
    return []


def _confirm_deletion(args: argparse.Namespace, candidate_ids: list[int]) -> bool:
    """
    Confirm deletion unless the caller explicitly bypassed prompting.

    Args:
        args (argparse.Namespace): Parsed command arguments.
        candidate_ids (list[int]): Candidate delta IDs.

    Returns:
        bool: True when deletion should proceed.
    """
    if bool(args.yes):
        return True
    if bool(args.json):
        return False
    if not sys.stdin.isatty():
        return False
    candidate_text: str = ", ".join(str(delta_id) for delta_id in candidate_ids)
    try:
        confirmation: str = input(f"Delete knowledge deltas {candidate_text}? (y/N): ").strip().casefold()
    except EOFError:
        return False
    return confirmation in ("y", "yes")


def _print_summary(args: argparse.Namespace, color_enabled: bool, payload: dict[str, Any]) -> int:
    """
    Print a deletion summary.

    Args:
        args (argparse.Namespace): Parsed command arguments.
        color_enabled (bool): Whether ANSI color placeholders should render.
        payload (dict): Summary payload.

    Returns:
        int: Process status code.
    """
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        message: str = str(payload.get("message") or f"Deleted {payload.get('deleted', 0)} knowledge deltas.")
        print(render_placeholders(f"__GREEN__{message}__RESET__", color_enabled))
    return 0
