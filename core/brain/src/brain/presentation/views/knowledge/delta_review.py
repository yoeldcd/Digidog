# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Composed terminal view for knowledge delta review buffers."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.application.knowledge.models.dtos.graph import EntityDTO
from brain.presentation.terminal import render_placeholders
from brain.presentation.views.knowledge.delta_formatting import (
    _description_text,
    _index_text,
    _label,
    _legend_text,
    _live_text,
    _notice_text,
    _source_text,
    _status_text,
)
from brain.presentation.views.knowledge.delta_sections import (
    _build_entity_lookup,
    _render_aliases,
    _render_entities,
    _render_messages,
    _render_relations,
    _render_schema,
    _render_summary_lines,
)
from brain.application.knowledge.pipeline.delta_status import (
    delta_counts,
    empty_delta_counts,
    is_delta_applicable,
    is_legacy_delta,
)


def render_delta_review(
    rows: list[dict[str, Any]],
    color_enabled: bool,
    title: str = "Knowledge Delta Proposals",
    compact: bool = False,
    show_review_hint: bool = False,
    entity_rows: list[dict[str, Any]] | None = None,
) -> str:
    """
    Render persisted knowledge deltas using a semantic terminal syntax.

    Args:
        rows (list[dict[str, Any]]): Pending delta review rows.
        color_enabled (bool): Whether ANSI color placeholders should render.
        title (str): Heading text for the review block. Defaults to `Knowledge Delta Proposals`.
        compact (bool): Whether to omit proposed record details. Defaults to False.
        show_review_hint (bool): Whether to show the follow-up review command. Defaults to False.
        entity_rows (list[dict[str, Any]] | None): Persisted entities available for relation endpoint labels.

    Returns:
        str: Rendered terminal text.
    """
    if not rows:
        return render_placeholders("__YELLOW__No knowledge deltas found.__RESET__", color_enabled)

    lines: list[str] = [
        render_placeholders(f"# __GREEN__{title}__RESET__", color_enabled),
        render_placeholders(f"  {_legend_text()}", color_enabled),
        "",
    ]
    for index, row in enumerate(rows, start=1):
        lines.extend(
            _render_delta_row(
                index=index,
                row=row,
                color_enabled=color_enabled,
                compact=compact,
                entity_rows=entity_rows or [],
            ),
        )
        lines.append("")

    if show_review_hint:
        review_hint: str = "py '.\\$agent\\scripts\\brain.py' knowledge-deltas --limit 10"
        lines.append(
            render_placeholders(
                f"{_label('review')} {_live_text(review_hint)}",
                color_enabled,
            ),
        )
    return "\n".join(lines).rstrip()


def _render_delta_row(
    index: int,
    row: dict[str, Any],
    color_enabled: bool,
    compact: bool,
    entity_rows: list[dict[str, Any]],
) -> list[str]:
    """
    Render one numbered delta row.

    Args:
        index (int): One-based display index.
        row (dict[str, Any]): Pending delta review row.
        color_enabled (bool): Whether ANSI color placeholders should render.
        compact (bool): Whether to omit detailed proposed records.
        entity_rows (list[dict[str, Any]]): Persisted entities available for relation endpoint labels.

    Returns:
        list[str]: Rendered row lines.
    """
    payload: dict[str, Any] = row["payload"]
    validation: dict[str, Any] = row["validation"]
    accepted_delta: dict[str, Any] = validation.get("accepted_delta", {})
    entity_lookup: dict[int, EntityDTO] = _build_entity_lookup(
        payload=payload,
        accepted_delta=accepted_delta,
        entity_rows=entity_rows,
    )
    is_legacy: bool = is_legacy_delta(delta=payload)
    total_counts: dict[str, int] = delta_counts(delta=payload)
    accepted_counts: dict[str, int] = empty_delta_counts() if is_legacy else delta_counts(delta=accepted_delta)
    status_text: str = "legacy" if is_legacy else "applicable" if is_delta_applicable(row=row) else "not applicable"
    status_block: str = _status_text(status=status_text)
    display_index: Any = row.get("id") or index

    lines: list[str] = [
        render_placeholders(
            f"{_index_text(index=display_index)} {status_block} {_source_text(row.get('source_path', ''))}",
            color_enabled,
        ),
    ]
    lines.extend(
        _render_summary_lines(
            total_counts=total_counts,
            accepted_counts=accepted_counts,
            validation=validation,
            color_enabled=color_enabled,
        ),
    )
    if is_legacy:
        lines.append(
            render_placeholders(
                f"    {_notice_text('legacy contract hidden; regenerate this source with dream')}",
                color_enabled,
            ),
        )
        return lines
    if payload.get("rationale"):
        lines.append(
            render_placeholders(
                f"    {_label('why')} {_live_text(payload.get('rationale', ''))}",
                color_enabled,
            ),
        )
    if compact:
        return lines

    lines.extend(
        _render_entities(
            records=payload.get("entities", []),
            color_enabled=color_enabled,
            title="proposed entities",
        ),
    )
    lines.extend(
        _render_aliases(
            records=payload.get("aliases", []),
            color_enabled=color_enabled,
            title="proposed aliases",
        ),
    )
    lines.extend(
        _render_relations(
            records=payload.get("relations", []),
            color_enabled=color_enabled,
            title="proposed relations",
            entity_lookup=entity_lookup,
        ),
    )
    lines.extend(
        _render_schema(
            records=payload.get("schema_suggestions", []),
            color_enabled=color_enabled,
            title="proposed schema suggestions",
        ),
    )
    lines.extend(
        _render_messages(
            title="errors",
            messages=validation.get("errors", []),
            color_placeholder="__RED__",
            color_enabled=color_enabled,
        ),
    )
    lines.extend(
        _render_messages(
            title="warnings",
            messages=validation.get("warnings", []),
            color_placeholder="__YELLOW__",
            color_enabled=color_enabled,
        ),
    )
    return lines
