"""Markdown renderers for knowledge graph show payloads."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any


def render_overview(payload: dict[str, Any]) -> str:
    """
    Render the no-argument overview.

    Args:
        payload (dict[str, Any]): Overview payload.

    Returns:
        str: Markdown text.
    """
    counts = payload.get("counts", {})
    return "\n".join(
        [
            "# Knowledge Graph Show",
            "",
            f"- **Scope**: {payload['scope']}",
            f"- **Entities**: {counts.get('entities', 0)}",
            f"- **Relations**: {counts.get('relations', 0)}",
            f"- **Classes**: {counts.get('entity_classes', 0)}",
            "",
            "Use `--entities`, `--relations`, `--classes`, or `--filter <TEXT>` to inspect graph records.",
        ],
    )


def render_entity(payload: dict[str, Any]) -> str:
    """
    Render one entity with contextual type assertions and outgoing relations.

    Args:
        payload (dict[str, Any]): Entity payload.

    Returns:
        str: Markdown text.
    """
    lines = [
        f"# {payload['canonical_name']}",
        "",
        f"- **ID**: {payload['id']}",
        f"- **Class**: {payload['entity_class']}",
        f"- **Confidence**: {confidence(payload.get('confidence'))}",
        f"- **Status**: {payload['status']}",
        f"- **Description**: {payload['description']}",
    ]
    if payload.get("type_assertions"):
        lines.extend(["", "## Type Assertions"])
        for assertion in payload["type_assertions"]:
            lines.append(
                f"- {assertion.get('entity_class', '')} "
                f"c: {confidence(assertion.get('confidence'))} "
                f"src: {assertion.get('source_id', '')} "
                f'dc: "{assertion.get("description", "")}"',
            )
    if payload.get("relations"):
        lines.extend(["", "## Relations"])
        subject = f'[{payload.get("entity_class", "")}:"{payload.get("canonical_name", "")}"]'
        for relation in payload["relations"]:
            lines.append(
                f'- {subject} - ("{relation.get("predicate", "")}" at {confidence(relation.get("confidence"))}) '
                f'-> ["{relation.get("object_name", relation.get("object_entity_id", ""))}"]',
            )
    return "\n".join(lines)


def render_listing(payload: dict[str, Any]) -> str:
    """
    Render graph listing sections.

    Args:
        payload (dict[str, Any]): Listing payload.

    Returns:
        str: Markdown text.
    """
    lines = ["# Knowledge Graph Records", "", f"- **Scope**: {payload['scope']}"]
    if payload.get("filter"):
        lines.append(f'- **Filter**: "{payload["filter"]}"')
    section_renderers = (
        ("entities", "Entities", render_entities),
        ("relations", "Relations", render_relations),
        ("classes", "Classes", render_classes),
    )
    for key, title, renderer in section_renderers:
        if key in payload:
            rows = payload[key]
            lines.extend(["", f"## {title} ({len(rows)})"])
            lines.extend(renderer(rows))
    return "\n".join(lines)


def render_entities(rows: list[dict[str, Any]]) -> list[str]:
    """
    Render entity listing rows.

    Args:
        rows (list[dict[str, Any]]): Entity rows.

    Returns:
        list[str]: Markdown lines.
    """
    if not rows:
        return ["- No entities found."]
    lines: list[str] = []
    for row in rows:
        lines.append(
            f'- [{row.get("id")}] [{row.get("entity_class")}:"{row.get("canonical_name")}"] '
            f"c: {confidence(row.get('confidence'))}{source(row)}",
        )
        if row.get("description"):
            lines.append(f'  dc: "{row["description"]}"')
    return lines


def render_relations(rows: list[dict[str, Any]]) -> list[str]:
    """
    Render relation listing rows.

    Args:
        rows (list[dict[str, Any]]): Relation rows.

    Returns:
        list[str]: Markdown lines.
    """
    if not rows:
        return ["- No relations found."]
    return [
        f'- [{row.get("id")}] [{row.get("subject_class", "")}:"{row.get("subject_name", "")}"] '
        f'- ("{row.get("predicate", "")}" at {confidence(row.get("confidence"))}) -> '
        f'[{row.get("object_class", "")}:"{row.get("object_name", "")}"]{source(row)}'
        for row in rows
    ]


def render_classes(rows: list[dict[str, Any]]) -> list[str]:
    """
    Render class listing rows.

    Args:
        rows (list[dict[str, Any]]): Class rows.

    Returns:
        list[str]: Markdown lines.
    """
    if not rows:
        return ["- No classes found."]
    lines: list[str] = []
    for row in rows:
        lines.append(f"- [{row.get('name')}] status: {row.get('status', '')}")
        if row.get("description"):
            lines.append(f'  dc: "{row["description"]}"')
    return lines


def source(row: dict[str, Any]) -> str:
    """
    Render source suffix.

    Args:
        row (dict[str, Any]): Graph row.

    Returns:
        str: Source suffix.
    """
    source_id = row.get("source_id")
    source_path = str(row.get("source_path") or "")
    if source_id and source_path:
        return f' src: {source_id} "{source_path}"'
    if source_id:
        return f" src: {source_id}"
    return ""


def confidence(value: Any) -> str:
    """
    Render compact confidence values.

    Args:
        value (Any): Raw confidence value.

    Returns:
        str: Compact confidence string.
    """
    try:
        value_as_float = float(value)
    except (TypeError, ValueError):
        return "0"
    if value_as_float >= 1.0:
        return "1"
    return f"{value_as_float:.2f}".lstrip("0")
