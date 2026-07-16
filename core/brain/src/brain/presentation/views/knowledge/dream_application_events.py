# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application event line renderers for knowledge dream diagnostics."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.presentation.views.knowledge.diagnostic_formatting import (
    counts_text,
    field,
    join_delta_ids,
    live_text,
    number,
    schema_text,
)


def render_application_event_lines(event_payload: dict[str, Any]) -> list[str]:
    """
    Render structured delta application diagnostics.

    Args:
        event_payload (dict[str, Any]): Structured event emitted by delta application.

    Returns:
        list[str]: Rendered log lines.
    """
    event_name: str = str(event_payload.get("event") or "application")
    if event_name == "application_batch_start":
        return [
            (
                "__MAGENTA__[apply:start]__RESET__ "
                f"{field('selected')} {number(event_payload.get('selected', 0))} "
                f"{field('delta_ids')} {live_text(join_delta_ids(event_payload.get('delta_ids', [])))}"
            ),
        ]
    if event_name == "application_delta_start":
        return [
            (
                "__MAGENTA__[apply:delta]__RESET__ "
                f"{field('id')} {number(event_payload.get('delta_id'))} "
                f"{field('status')} {schema_text(event_payload.get('status'))} "
                f"{field('source')} {live_text(event_payload.get('source_path'))}"
            ),
        ]
    if event_name == "application_validate_start":
        return [
            (
                "__CYAN__[apply:validate]__RESET__ "
                f"{field('id')} {number(event_payload.get('delta_id'))} "
                f"{field('candidate')} {counts_text(event_payload.get('counts', {}))}"
            ),
        ]
    if event_name == "application_validate_result":
        return [
            (
                "__CYAN__[apply:validated]__RESET__ "
                f"{field('id')} {number(event_payload.get('delta_id'))} "
                f"{field('valid')} {schema_text(event_payload.get('valid'))} "
                f"{field('accepted')} {counts_text(event_payload.get('accepted_counts', {}))} "
                f"{field('errors')} {number(event_payload.get('errors', 0))} "
                f"{field('warnings')} {number(event_payload.get('warnings', 0))}"
            ),
        ]
    if event_name == "application_write_start":
        return [
            (
                "__GREEN__[apply:write]__RESET__ "
                f"{field('id')} {number(event_payload.get('delta_id'))} "
                f"{field('source_id')} {number(event_payload.get('source_id'))} "
                f"{field('accepted')} {counts_text(event_payload.get('accepted_counts', {}))}"
            ),
        ]
    if event_name == "application_delta_applied":
        return [
            (
                "__GREEN__[apply:done]__RESET__ "
                f"{field('id')} {number(event_payload.get('delta_id'))} "
                f"{field('decisions')} {number(event_payload.get('decisions', 0))}"
            ),
        ]
    if event_name == "application_delta_failed":
        return [
            (
                "__RED__[apply:error]__RESET__ "
                f"{field('id')} {number(event_payload.get('delta_id'))} "
                f"{field('error')} {live_text(event_payload.get('error'))}"
            ),
        ]
    if event_name == "application_promotion_start":
        return [
            (
                "__MAGENTA__[apply:promote]__RESET__ "
                f"{field('applied')} {number(event_payload.get('applied', 0))}"
            ),
        ]
    if event_name == "application_promotion_result":
        return [
            (
                "__GREEN__[apply:promoted]__RESET__ "
                f"{field('decisions')} {number(event_payload.get('decisions', 0))}"
            ),
        ]
    if event_name == "application_batch_complete":
        return [
            (
                "__GREEN__[apply:complete]__RESET__ "
                f"{field('applied')} {number(event_payload.get('applied', 0))} "
                f"{field('errors')} {number(event_payload.get('errors', 0))}"
            ),
        ]
    return [f"__DIM__[apply:event]__RESET__ {live_text(event_name)}"]
