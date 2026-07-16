# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Source and orchestration event renderers for knowledge dream diagnostics."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.presentation.views.knowledge.diagnostic_formatting import counts_text, field, live_text, number, schema_text


def render_dream_event_lines(event_payload: dict[str, Any]) -> list[str]:
    """
    Render structured dream source/orchestration diagnostics.

    Args:
        event_payload: Structured event emitted by dream orchestration.

    Returns:
        Rendered terminal lines.
    """
    event_name: str = str(event_payload.get("event") or "dream")
    if event_name == "dream_run_start":
        return [
            (
                "__MAGENTA__[dream:run]__RESET__ "
                f"{field('scope')} {schema_text(event_payload.get('scope'))} "
                f"{field('domain')} {schema_text(event_payload.get('domain'))} "
                f"{field('limit')} {number(event_payload.get('limit'))} "
                f"{field('dry_run')} {schema_text(event_payload.get('dry_run'))} "
                f"{field('min_conf')} {number(event_payload.get('minimum_confidence'))}"
            ),
        ]
    if event_name == "ingest_start":
        return [
            (
                "__MAGENTA__[dream:ingest]__RESET__ "
                f"{field('scope')} {schema_text(event_payload.get('scope'))} "
                f"{field('domain')} {schema_text(event_payload.get('domain'))} "
                f"{field('limit')} {number(event_payload.get('limit'))} "
                f"{field('force_all')} {schema_text(event_payload.get('force_all'))}"
            ),
        ]
    if event_name == "source_discovered":
        return [_source_line("[dream:discover]", event_payload)]
    if event_name == "ingest_diff":
        return [
            (
                "__CYAN__[dream:diff]__RESET__ "
                f"{field('scope')} {schema_text(event_payload.get('scope'))} "
                f"{field('discovered')} {number(event_payload.get('discovered', 0))} "
                f"{field('changed')} {number(event_payload.get('changed', 0))} "
                f"{field('deleted')} {number(event_payload.get('deleted', 0))}"
            ),
        ]
    if event_name == "source_deleted":
        return [
            (
                "__YELLOW__[dream:deleted]__RESET__ "
                f"{field('scope')} {schema_text(event_payload.get('scope'))} "
                f"{field('source')} {live_text(event_payload.get('source_path'))}"
            ),
        ]
    if event_name == "source_skipped":
        return [_source_line("[dream:skip]", event_payload, reason=event_payload.get("reason"))]
    if event_name == "source_read_start":
        return [_source_line("[dream:read:start]", event_payload)]
    if event_name == "source_read":
        return [
            _source_line("[dream:read]", event_payload, extra=f"{field('chars')} {number(event_payload.get('chars', 0))}"),
        ]
    if event_name == "ingest_limit_reached":
        return [
            (
                "__YELLOW__[dream:limit]__RESET__ "
                f"{field('scope')} {schema_text(event_payload.get('scope'))} "
                f"{field('limit')} {number(event_payload.get('limit'))}"
            ),
        ]
    if event_name == "ingest_complete":
        return [
            (
                "__GREEN__[dream:ingest:done]__RESET__ "
                f"{field('scope')} {schema_text(event_payload.get('scope'))} "
                f"{field('discovered')} {number(event_payload.get('discovered', 0))} "
                f"{field('changed')} {number(event_payload.get('changed', 0))} "
                f"{field('skipped')} {number(event_payload.get('skipped', 0))} "
                f"{field('deleted')} {number(event_payload.get('deleted', 0))}"
            ),
        ]
    if event_name == "class_catalog_loaded":
        classes: list[Any] = list(event_payload.get("classes") or [])
        return [
            (
                "__CYAN__[dream:classes]__RESET__ "
                f"{field('scope')} {schema_text(event_payload.get('scope'))} "
                f"{field('count')} {number(len(classes))} "
                f"{field('objects')} {live_text(', '.join(str(item) for item in classes))}"
            ),
        ]
    if event_name == "dream_source_start":
        return [
            (
                "__MAGENTA__[dream:source]__RESET__ "
                f"{field('scope')} {schema_text(event_payload.get('scope'))} "
                f"{field('source')} {live_text(event_payload.get('source_path'))} "
                f"{field('type')} {schema_text(event_payload.get('source_type'))} "
                f"{field('chars')} {number(event_payload.get('chars', 0))}"
            ),
        ]
    if event_name == "dream_source_skipped":
        return [
            (
                "__YELLOW__[dream:source:skip]__RESET__ "
                f"{field('source')} {live_text(event_payload.get('source_path'))} "
                f"{field('reason')} {live_text(event_payload.get('reason'))}"
            ),
        ]
    if event_name == "dream_frame_built":
        return [
            (
                "__CYAN__[dream:frame]__RESET__ "
                f"{field('source')} {live_text(event_payload.get('source_path'))} "
                f"{field('kind')} {schema_text(event_payload.get('frame_kind'))} "
                f"{field('title')} {live_text(event_payload.get('frame_title'))}"
            ),
            (
                f"    {field('objects')} "
                f"source_chars {number(event_payload.get('source_chars', 0))}  "
                f"model_chars {number(event_payload.get('model_chars', 0))}  "
                f"graph_context_chars {number(event_payload.get('graph_context_chars', 0))}  "
                f"entity_candidates {number(event_payload.get('entity_resolution_candidates', 0))}"
            ),
        ]
    if event_name == "dream_stage_warning":
        return [
            (
                "__YELLOW__[dream:stage:warning]__RESET__ "
                f"{field('source')} {live_text(event_payload.get('source_path'))} "
                f"{field('warning')} {live_text(event_payload.get('warning'))}"
            ),
        ]
    if event_name == "dream_stage_merged":
        return [
            (
                "__GREEN__[dream:stage]__RESET__ "
                f"{field('source')} {live_text(event_payload.get('source_path'))} "
                f"{field('stage')} {schema_text(event_payload.get('stage'))} "
                f"{field('delta')} {counts_text(event_payload.get('delta_counts', {}))} "
                f"{field('accumulated')} {counts_text(event_payload.get('accumulated_counts', {}))}"
            ),
        ]
    if event_name == "source_upserted":
        return [
            (
                "__CYAN__[dream:source:db]__RESET__ "
                f"{field('source')} {live_text(event_payload.get('source_path'))} "
                f"{field('source_id')} {number(event_payload.get('source_id'))}"
            ),
        ]
    if event_name == "delta_validated":
        return [
            (
                "__CYAN__[dream:validate]__RESET__ "
                f"{field('source')} {live_text(event_payload.get('source_path'))} "
                f"{field('source_id')} {number(event_payload.get('source_id'))} "
                f"{field('valid')} {schema_text(event_payload.get('valid'))}"
            ),
            (
                f"    {field('delta')} "
                f"candidate {counts_text(event_payload.get('candidate_counts', {}))}  "
                f"accepted {counts_text(event_payload.get('accepted_counts', {}))}  "
                f"errors {number(event_payload.get('errors', 0))}  "
                f"warnings {number(event_payload.get('warnings', 0))}"
            ),
        ]
    if event_name == "pending_delta_persisted":
        return [
            (
                "__GREEN__[dream:pending]__RESET__ "
                f"{field('delta_id')} {number(event_payload.get('delta_id'))} "
                f"{field('source_id')} {number(event_payload.get('source_id'))} "
                f"{field('source')} {live_text(event_payload.get('source_path'))} "
                f"{field('accepted')} {counts_text(event_payload.get('accepted_counts', {}))}"
            ),
        ]
    if event_name == "source_marked_processed":
        return [
            (
                "__GREEN__[dream:processed]__RESET__ "
                f"{field('source')} {live_text(event_payload.get('source_path'))} "
                f"{field('mtime')} {number(event_payload.get('mtime'))}"
            ),
        ]
    if event_name == "pending_delta_status_updated":
        return [
            (
                "__GREEN__[dream:status]__RESET__ "
                f"{field('delta_id')} {number(event_payload.get('delta_id'))} "
                f"{field('status')} {schema_text(event_payload.get('status'))}"
            ),
        ]
    if event_name == "dream_run_recorded":
        return [
            (
                "__GREEN__[dream:recorded]__RESET__ "
                f"{field('scope')} {schema_text(event_payload.get('scope'))} "
                f"{field('dream_id')} {number(event_payload.get('dream_id'))} "
                f"{field('sources')} {number(event_payload.get('sources_seen', 0))} "
                f"{field('proposed')} {number(event_payload.get('deltas_proposed', 0))} "
                f"{field('applied')} {number(event_payload.get('deltas_applied', 0))} "
                f"{field('status')} {schema_text(event_payload.get('status'))}"
            ),
        ]
    return [f"__DIM__[dream:event]__RESET__ {live_text(event_name)}"]


def _source_line(prefix: str, event_payload: dict[str, Any], reason: Any = None, extra: str = "") -> str:
    """Render one source-object line."""
    reason_text = f" {field('reason')} {live_text(reason)}" if reason else ""
    extra_text = f" {extra}" if extra else ""
    return (
        f"__DIM__{prefix}__RESET__ "
        f"{field('source')} {live_text(event_payload.get('source_path'))} "
        f"{field('type')} {schema_text(event_payload.get('source_type'))} "
        f"{field('title')} {live_text(event_payload.get('title'))} "
        f"{field('fs')} {live_text(event_payload.get('filesystem_path'))} "
        f"{field('mtime')} {number(event_payload.get('mtime'))}"
        f"{reason_text}{extra_text}"
    )
