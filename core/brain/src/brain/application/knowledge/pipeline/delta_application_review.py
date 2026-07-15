"""Application payload builders for reviewed knowledge delta application."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.application.knowledge.pipeline.delta_status import is_delta_applicable


def review_delta_application(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Classify reviewed delta rows for application.

    Args:
        rows (list[dict[str, Any]]): Revalidated delta rows.

    Returns:
        dict[str, Any]: Candidate, applicable, and blocked row metadata.
    """
    candidate_rows: list[dict[str, Any]] = rows
    applicable_rows: list[dict[str, Any]] = [
        row
        for row in candidate_rows
        if is_pending_delta_row(row=row) and is_delta_applicable(row=row)
    ]
    blocked_ids: list[int] = [
        int(row["id"])
        for row in candidate_rows
        if is_pending_delta_row(row=row) and not is_delta_applicable(row=row)
    ]
    return {
        "candidate_rows": candidate_rows,
        "applicable_rows": applicable_rows,
        "candidate_ids": delta_row_ids(rows=candidate_rows),
        "blocked_ids": blocked_ids,
    }


def json_confirmation_required_payload(review: dict[str, Any]) -> dict[str, Any]:
    """
    Build the JSON-mode confirmation payload.

    Args:
        review (dict[str, Any]): Delta application review metadata.

    Returns:
        dict[str, Any]: JSON-safe summary payload.
    """
    return {
        "ok": False,
        "applied": 0,
        "review_rows": review["candidate_rows"],
        "candidate_ids": review["candidate_ids"],
        "blocked_ids": review["blocked_ids"],
        "message": "Application confirmation is implicit; JSON mode requires --yes to apply.",
    }


def no_applicable_payload(review: dict[str, Any], include_review_rows: bool) -> dict[str, Any]:
    """
    Build a payload for reviews without applicable rows.

    Args:
        review (dict[str, Any]): Delta application review metadata.
        include_review_rows (bool): Whether to include full review rows.

    Returns:
        dict[str, Any]: JSON-safe summary payload.
    """
    return {
        "ok": False,
        "applied": 0,
        "review_rows": review["candidate_rows"] if include_review_rows else [],
        "candidate_ids": review["candidate_ids"],
        "blocked_ids": review["blocked_ids"],
        "message": "No applicable deltas selected.",
    }


def aborted_application_payload(review: dict[str, Any], include_review_rows: bool) -> dict[str, Any]:
    """
    Build a payload for aborted application.

    Args:
        review (dict[str, Any]): Delta application review metadata.
        include_review_rows (bool): Whether to include full review rows.

    Returns:
        dict[str, Any]: JSON-safe summary payload.
    """
    return {
        "ok": False,
        "applied": 0,
        "review_rows": review["candidate_rows"] if include_review_rows else [],
        "candidate_ids": review["candidate_ids"],
        "blocked_ids": review["blocked_ids"],
        "message": "Application aborted.",
    }


def applied_application_payload(
    review: dict[str, Any],
    selected_rows: list[dict[str, Any]],
    applied_count: int,
    application_errors: list[str],
    include_review_rows: bool,
) -> dict[str, Any]:
    """
    Build a payload for completed application.

    Args:
        review (dict[str, Any]): Delta application review metadata.
        selected_rows (list[dict[str, Any]]): Rows selected for application.
        applied_count (int): Number of rows applied.
        application_errors (list[str]): Application error messages.
        include_review_rows (bool): Whether to include full review rows.

    Returns:
        dict[str, Any]: JSON-safe summary payload.
    """
    return {
        "ok": not application_errors,
        "applied": applied_count,
        "review_rows": review["candidate_rows"] if include_review_rows else [],
        "applied_ids": delta_row_ids(rows=selected_rows),
        "blocked_ids": review["blocked_ids"],
        "errors": application_errors,
        "message": f"Applied {applied_count} knowledge deltas.",
    }


def is_pending_delta_row(row: dict[str, Any]) -> bool:
    """
    Return whether a review row is still pending.

    Args:
        row (dict[str, Any]): Pending delta row.

    Returns:
        bool: True when the row can be applied.
    """
    return str(row.get("status") or "").casefold() == "pending"


def delta_row_ids(rows: list[dict[str, Any]]) -> list[int]:
    """
    Return persisted integer IDs from delta rows.

    Args:
        rows (list[dict[str, Any]]): Delta rows.

    Returns:
        list[int]: Persisted row identifiers.
    """
    return [int(row["id"]) for row in rows]
