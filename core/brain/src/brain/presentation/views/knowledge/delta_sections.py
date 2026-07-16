# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Section renderers for knowledge delta review rows."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.application.knowledge.models.dtos.graph import AliasDTO, EntityDTO, RelationDTO
from brain.presentation.terminal import render_placeholders
from brain.presentation.views.knowledge.delta_formatting import (
    _alias_text,
    _confidence_text,
    _counts_text,
    _description_text,
    _entity_text,
    _label,
    _live_text,
    _number,
    _relation_text,
    _schema_text,
    _section,
    _source_id_text,
)


def _render_entities(records: list[dict[str, Any]], color_enabled: bool, title: str) -> list[str]:
    """
    Render entity records.

    Args:
        records (list[dict[str, Any]]): Entity records.
        color_enabled (bool): Whether ANSI color placeholders should render.
        title (str): Section title.

    Returns:
        list[str]: Rendered entity lines.
    """
    if not records:
        return []
    lines: list[str] = [render_placeholders(f"    {_section(title)}", color_enabled)]
    for record in records:
        entity_dto: EntityDTO = EntityDTO.model_validate(record)
        lines.append(
            render_placeholders(
                f"      {_entity_text(entity_dto=entity_dto)} "
                f"{_description_text(entity_dto.description)} "
                f"{_source_id_text(entity_dto.source_id)} {_confidence_text(entity_dto.confidence)}",
                color_enabled,
            ),
        )
    return lines


def _render_aliases(records: list[dict[str, Any]], color_enabled: bool, title: str) -> list[str]:
    """
    Render alias records.

    Args:
        records (list[dict[str, Any]]): Alias records.
        color_enabled (bool): Whether ANSI color placeholders should render.
        title (str): Section title.

    Returns:
        list[str]: Rendered alias lines.
    """
    if not records:
        return []
    lines: list[str] = [render_placeholders(f"    {_section(title)}", color_enabled)]
    for record in records:
        alias_dto: AliasDTO = AliasDTO.model_validate(record)
        lines.append(render_placeholders(f"      {_alias_text(alias_dto=alias_dto)}", color_enabled))
    return lines


def _render_relations(
    records: list[dict[str, Any]],
    color_enabled: bool,
    title: str,
    entity_lookup: dict[int, EntityDTO],
) -> list[str]:
    """
    Render relation records.

    Args:
        records (list[dict[str, Any]]): Relation records.
        color_enabled (bool): Whether ANSI color placeholders should render.
        title (str): Section title.
        entity_lookup (dict[int, EntityDTO]): Candidate entities available for endpoint rendering.

    Returns:
        list[str]: Rendered relation lines.
    """
    if not records:
        return []
    lines: list[str] = [render_placeholders(f"    {_section(title)}", color_enabled)]
    for record in records:
        relation_dto: RelationDTO = RelationDTO.model_validate(record)
        lines.append(
            render_placeholders(
                f"      {_relation_text(relation_dto=relation_dto, entity_lookup=entity_lookup)} "
                f"{_source_id_text(relation_dto.source_id)}",
                color_enabled,
            ),
        )
    return lines


def _build_entity_lookup(
    payload: dict[str, Any],
    accepted_delta: dict[str, Any],
    entity_rows: list[dict[str, Any]],
) -> dict[int, EntityDTO]:
    """
    Build a candidate entity lookup for rendering relation endpoints.

    Args:
        payload (dict[str, Any]): Proposed delta payload.
        accepted_delta (dict[str, Any]): Accepted delta payload.
        entity_rows (list[dict[str, Any]]): Persisted entities available for endpoint rendering.

    Returns:
        dict[int, EntityDTO]: Entity IDs mapped to display DTOs.
    """
    entity_lookup: dict[int, EntityDTO] = {}
    records: list[dict[str, Any]] = []
    records.extend(entity_rows)
    records.extend(payload.get("entities", []))
    records.extend(accepted_delta.get("entities", []))
    for record in records:
        try:
            entity_dto: EntityDTO = EntityDTO.model_validate(record)
        except Exception:
            continue
        if entity_dto.id is None:
            continue
        entity_lookup.setdefault(int(entity_dto.id), entity_dto)
    return entity_lookup


def _render_schema(records: list[dict[str, Any]], color_enabled: bool, title: str) -> list[str]:
    """
    Render ontology schema suggestions.

    Args:
        records (list[dict[str, Any]]): Schema suggestion records.
        color_enabled (bool): Whether ANSI color placeholders should render.
        title (str): Section title.

    Returns:
        list[str]: Rendered schema lines.
    """
    if not records:
        return []
    lines: list[str] = [render_placeholders(f"    {_section(title)}", color_enabled)]
    for record in records:
        lines.append(
            render_placeholders(
                f"      {_schema_text(record.get('suggestion_type', 'schema'))}:"
                f"{_schema_text(record.get('name', ''))} {_confidence_text(record.get('confidence', 0))}",
                color_enabled,
            ),
        )
    return lines


def _render_messages(
    title: str,
    messages: list[str],
    color_placeholder: str,
    color_enabled: bool,
) -> list[str]:
    """
    Render validation messages.

    Args:
        title (str): Message group title.
        messages (list[str]): Validation messages.
        color_placeholder (str): Placeholder color used for message markers.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        list[str]: Rendered validation message lines.
    """
    if not messages:
        return []
    lines: list[str] = [render_placeholders(f"    {_section(title)}", color_enabled)]
    for message in messages:
        lines.append(
            render_placeholders(
                f"      {color_placeholder}!__RESET__ {_live_text(message)}",
                color_enabled,
            ),
        )
    return lines


def _render_summary_lines(
    total_counts: dict[str, int],
    accepted_counts: dict[str, int],
    validation: dict[str, Any],
    color_enabled: bool,
) -> list[str]:
    """
    Render proposal, accepted, error, and warning summaries.

    Args:
        total_counts (dict[str, int]): Proposed record counts.
        accepted_counts (dict[str, int]): Accepted record counts.
        validation (dict[str, Any]): Validation payload.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        list[str]: Summary lines.
    """
    return [
        render_placeholders(f"    {_label('proposed')} {_counts_text(total_counts)}", color_enabled),
        render_placeholders(f"    {_label('accepted')} {_counts_text(accepted_counts)}", color_enabled),
        render_placeholders(f"    {_label('errors')} {_number(len(validation.get('errors', [])))}", color_enabled),
        render_placeholders(f"    {_label('warnings')} {_number(len(validation.get('warnings', [])))}", color_enabled),
    ]
