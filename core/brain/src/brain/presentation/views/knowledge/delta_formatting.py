# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Terminal formatting primitives for knowledge delta reviews."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.config import KNOWLEDGE_DELTA_MAX_LIVE_TEXT_LENGTH as MAX_LIVE_TEXT_LENGTH
from brain.application.knowledge.models.dtos.graph import AliasDTO, EntityDTO, RelationDTO


def _counts_text(counts: dict[str, int]) -> str:
    """
    Format a semantic count summary.

    Args:
        counts (dict[str, int]): Count values.

    Returns:
        str: Count summary with descriptive labels.
    """
    return "  ".join(
        (
            f"{_metric_label('Et')} {_number(counts['entities'])}",
            f"{_metric_label('Re')} {_number(counts['relations'])}",
            f"{_metric_label('Ale')} {_number(counts['aliases'])}",
            f"{_metric_label('Sch')} {_number(counts['schema'])}",
        ),
    )


def _index_text(index: Any) -> str:
    """
    Render a display index.

    Args:
        index (Any): Persisted delta ID, with display-order fallback for synthetic rows.

    Returns:
        str: Rendered index placeholder text.
    """
    return f"__BOLD____CYAN__[{index}]__RESET__"


def _label(label: str) -> str:
    """
    Render a field label.

    Args:
        label (str): Human-readable field label.

    Returns:
        str: Placeholder label string.
    """
    return f"__DIM__{label}:__RESET__"


def _legend_text() -> str:
    """
    Render the metric shortcut legend.

    Returns:
        str: Placeholder legend line.
    """
    return (
        f"{_label('legend')} "
        f"{_metric_label('Et')}=entities  "
        f"{_metric_label('Re')}=relations  "
        f"{_metric_label('Ale')}=aliases  "
        f"{_metric_label('Sch')}=schema"
    )


def _metric_label(label: str) -> str:
    """
    Render a metric label inside a summary line.

    Args:
        label (str): Metric label.

    Returns:
        str: Placeholder metric label.
    """
    return f"__DIM__{label}__RESET__"


def _section(title: str) -> str:
    """
    Render a section heading.

    Args:
        title (str): Section title.

    Returns:
        str: Placeholder section heading.
    """
    return f"__GREEN__{title}__RESET__"


def _status_text(status: str) -> str:
    """
    Render a status value with semantic color.

    Args:
        status (str): Status label.

    Returns:
        str: Placeholder status text.
    """
    if status == "applicable":
        return "__GREEN__applicable__RESET__"
    if status == "legacy":
        return "__YELLOW__legacy__RESET__"
    if status in ("failed", "error", "rejected"):
        return f"__RED__{status}__RESET__"
    return f"__YELLOW__{status}__RESET__"


def _schema_text(value: Any) -> str:
    """
    Render an ontology class or schema token.

    Args:
        value (Any): Raw token value.

    Returns:
        str: Placeholder schema token.
    """
    return f"__MAGENTA__{_clean_inline_text(value=value)}__RESET__"


def _entity_text(entity_dto: EntityDTO) -> str:
    """
    Render an entity DTO with semantic color placeholders.

    Args:
        entity_dto (EntityDTO): Entity to render.

    Returns:
        str: Placeholder entity syntax.
    """
    return f"[{_schema_text(entity_dto.entity_class)}:{_live_text(entity_dto.canonical_name)}]"


def _alias_text(alias_dto: AliasDTO) -> str:
    """
    Render an alias DTO with semantic color placeholders.

    Args:
        alias_dto (AliasDTO): Alias to render.

    Returns:
        str: Placeholder alias syntax.
    """
    return f"{{{_number(alias_dto.entity_ref)}}} alias {_live_text(alias_dto.alias)}"


def _relation_text(relation_dto: RelationDTO, entity_lookup: dict[int, EntityDTO]) -> str:
    """
    Render a relation DTO with semantic color placeholders.

    Args:
        relation_dto (RelationDTO): Relation to render.
        entity_lookup (dict[int, EntityDTO]): Candidate entities available for endpoint rendering.

    Returns:
        str: Placeholder relation syntax.
    """
    subject_text: str = _endpoint_text(endpoint_id=relation_dto.subject_id, entity_lookup=entity_lookup)
    object_text: str = _endpoint_text(endpoint_id=relation_dto.object_id, entity_lookup=entity_lookup)
    return (
        f"{subject_text} - "
        f"(\"{_procedure_text(relation_dto.predicate)}\" at "
        f"{_number(_format_confidence(relation_dto.confidence))}) "
        f"-> {object_text}"
    )


def _endpoint_text(endpoint_id: int | None, entity_lookup: dict[int, EntityDTO]) -> str:
    """
    Render one relation endpoint as an entity when available.

    Args:
        endpoint_id (int | None): Relation endpoint identifier.
        entity_lookup (dict[int, EntityDTO]): Candidate entities available for endpoint rendering.

    Returns:
        str: Placeholder endpoint syntax.
    """
    if endpoint_id is None:
        return f"{{{_number('?')}}}"
    entity_dto: EntityDTO | None = entity_lookup.get(int(endpoint_id))
    if entity_dto is None:
        return f"{{{_number(endpoint_id)}}}"
    return _entity_text(entity_dto=entity_dto)


def _source_text(value: Any) -> str:
    """
    Render a source path with a concise label.

    Args:
        value (Any): Source path value.

    Returns:
        str: Placeholder source text.
    """
    return f"{_label('src')} {_live_text(value)}"


def _source_id_text(value: Any) -> str:
    """
    Render a compact source ID tag.

    Args:
        value (Any): Source identifier.

    Returns:
        str: Placeholder source identifier.
    """
    return f"{_label('src')} {_number(value or '?')}"


def _confidence_text(value: Any) -> str:
    """
    Render a compact confidence tag.

    Args:
        value (Any): Confidence value.

    Returns:
        str: Placeholder confidence tag.
    """
    try:
        numeric_value: float = float(value)
    except (TypeError, ValueError):
        return f"{_label('c')} {_number('?')}"
    return f"{_label('c')} {_number(_format_confidence(numeric_value))}"


def _description_text(value: Any) -> str:
    """
    Render a compact entity description field.

    Args:
        value (Any): Description value.

    Returns:
        str: Placeholder description text.
    """
    return f"{_label('dc')} {_live_text(value)}"


def _format_confidence(value: float) -> str:
    """
    Format a confidence value for compact terminal display.

    Args:
        value (float): Confidence score.

    Returns:
        str: `1` for full confidence, otherwise `.XY` style.
    """
    if value >= 0.995:
        return "1"
    return f"{max(0.0, min(1.0, value)):.2f}".lstrip("0")


def _notice_text(value: str) -> str:
    """
    Render a compact notice line.

    Args:
        value (str): Notice text.

    Returns:
        str: Placeholder notice text.
    """
    return f"__YELLOW__{_clean_inline_text(value)}__RESET__"


def _procedure_text(value: Any) -> str:
    """
    Render a relation predicate or procedural token.

    Args:
        value (Any): Raw predicate value.

    Returns:
        str: Placeholder procedure token.
    """
    return f"__BOLD____MAGENTA__{_clean_inline_text(value=value)}__RESET__"


def _number(value: Any) -> str:
    """
    Render a numeric value.

    Args:
        value (Any): Raw numeric value.

    Returns:
        str: Placeholder numeric value.
    """
    return f"__CYAN__{value}__RESET__"


def _live_text(value: Any) -> str:
    """
    Render live textual content using blue quoted syntax.

    Args:
        value (Any): Raw text value.

    Returns:
        str: Placeholder text wrapped in blue double quotes.
    """
    clean_text: str = _clean_inline_text(value=value)
    if len(clean_text) > MAX_LIVE_TEXT_LENGTH:
        clean_text = f"{clean_text[: MAX_LIVE_TEXT_LENGTH - 3]}..."
    escaped_text: str = clean_text.replace('"', '\\"')
    return f"__BLUE__\"{escaped_text}\"__RESET__"


def _clean_inline_text(value: Any) -> str:
    """
    Normalize a value for single-line terminal rendering.

    Args:
        value (Any): Raw value.

    Returns:
        str: Single-line normalized text.
    """
    return " ".join(str(value or "").split())
