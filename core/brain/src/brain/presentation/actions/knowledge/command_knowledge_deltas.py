# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to review and optionally apply pending knowledge graph deltas."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import json
from typing import Any

# Application Modules Imports
from brain.application.knowledge.pipeline.delta_application_review import (
    aborted_application_payload,
    applied_application_payload,
    json_confirmation_required_payload,
    no_applicable_payload,
    review_delta_application,
)
from brain.application.knowledge.pipeline.delta_apply import apply_pending_delta_rows
from brain.application.knowledge.pipeline.delta_revalidation import revalidate_pending_delta_rows
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.presentation.inputs.knowledge.delta_selection import prompt_delta_selection
from brain.presentation.terminal import render_placeholders
from brain.presentation.views.knowledge.delta_apply_summary import render_delta_apply_summary
from brain.presentation.views.knowledge.delta_review import render_delta_review




def handle(args: argparse.Namespace) -> int:
    """
    Review pending knowledge graph deltas and ask for application.

    Args:
        args (argparse.Namespace): Parsed command arguments.

    Returns:
        int: Process status code.
    """
    color_enabled: bool = getattr(args, "color", False)
    repository = KnowledgeRepository(scope=str(args.scope))

    if args.id is not None:
        row = repository.get_pending_delta(delta_id=int(args.id))
        if row is None:
            return _print_not_found(args=args, color_enabled=color_enabled)
        rows = [row]
    else:
        rows = repository.list_pending_deltas(limit=int(args.limit), status=str(args.status))
    rows = revalidate_pending_delta_rows(repository=repository, rows=rows)

    if not args.json:
        print(
            render_delta_review(
                rows=rows,
                color_enabled=color_enabled,
                title="Knowledge Delta Proposals",
                compact=False,
                entity_rows=repository.list_entities(),
            ),
        )

    return _apply_reviewed_deltas(
        args=args,
        repository=repository,
        rows=rows,
        color_enabled=color_enabled,
    )


def _print_not_found(args: argparse.Namespace, color_enabled: bool) -> int:
    """
    Print a missing delta response.

    Args:
        args (argparse.Namespace): Parsed command arguments.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        int: Process status code.
    """
    message: str = f"Pending delta {args.id} not found."
    if args.json:
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
    else:
        print(render_placeholders(f"__RED__{message}__RESET__", color_enabled))
    return 1


def _apply_reviewed_deltas(
    args: argparse.Namespace,
    repository: KnowledgeRepository,
    rows: list[dict[str, Any]],
    color_enabled: bool,
) -> int:
    """
    Apply reviewed knowledge deltas after confirmation.

    The rows are expected to have been revalidated immediately before this
    function runs. Application therefore consumes that fresh validation report
    instead of recalculating it a second time.

    Args:
        args (argparse.Namespace): Parsed command arguments.
        repository (KnowledgeRepository): Knowledge repository.
        rows (list[dict[str, Any]]): Current review rows.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        int: Process status code.
    """
    review: dict[str, Any] = review_delta_application(rows=rows)
    applicable_rows: list[dict[str, Any]] = review["applicable_rows"]

    if args.json and not bool(args.yes):
        return _print_apply_summary(
            args=args,
            color_enabled=color_enabled,
            payload=json_confirmation_required_payload(review=review),
        )

    if not applicable_rows:
        return _print_apply_summary(
            args=args,
            color_enabled=color_enabled,
            payload=no_applicable_payload(review=review, include_review_rows=bool(args.json)),
        )

    selected_rows: list[dict[str, Any]] = _select_application_rows(
        args=args,
        applicable_rows=applicable_rows,
        color_enabled=color_enabled,
    )
    if not selected_rows:
        return _print_apply_summary(
            args=args,
            color_enabled=color_enabled,
            payload=aborted_application_payload(review=review, include_review_rows=bool(args.json)),
        )

    applied_count, application_errors, _decisions = apply_pending_delta_rows(
        repository=repository,
        selected_rows=selected_rows,
        revalidate=False,
    )
    return _print_apply_summary(
        args=args,
        color_enabled=color_enabled,
        payload=applied_application_payload(
            review=review,
            selected_rows=selected_rows,
            applied_count=applied_count,
            application_errors=application_errors,
            include_review_rows=bool(args.json),
        ),
    )


def _select_application_rows(
    args: argparse.Namespace,
    applicable_rows: list[dict[str, Any]],
    color_enabled: bool,
) -> list[dict[str, Any]]:
    """
    Select applicable rows through `--yes` or an interactive y/n/ID prompt.

    Args:
        args (argparse.Namespace): Parsed command arguments.
        applicable_rows (list[dict[str, Any]]): Rows that can be applied.
        color_enabled (bool): Whether ANSI placeholders should render.

    Returns:
        list[dict[str, Any]]: Rows selected for application.
    """
    if bool(args.yes):
        return applicable_rows
    if bool(args.json):
        return []
    return prompt_delta_selection(rows=applicable_rows, color_enabled=color_enabled)


def _print_apply_summary(args: argparse.Namespace, color_enabled: bool, payload: dict[str, Any]) -> int:
    """
    Print an application summary.

    Args:
        args (argparse.Namespace): Parsed command arguments.
        color_enabled (bool): Whether ANSI color placeholders should render.
        payload (dict[str, Any]): Summary payload.

    Returns:
        int: Process status code.
    """
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    for line in render_delta_apply_summary(payload=payload):
        print(render_placeholders(line, color_enabled))
    return 0
