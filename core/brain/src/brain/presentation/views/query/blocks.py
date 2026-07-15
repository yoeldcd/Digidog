"""Printable result blocks for global query terminal views."""

from __future__ import annotations

# Application Modules Imports
from brain.application.querying.dtos import GlobalQueryResultDTO
from brain.application.querying.source_refs import source_read_command_from_path
from brain.presentation.terminal import render_markdown, render_placeholders
from brain.presentation.views.query.formatting import compact_excerpt, format_confidence
from brain.presentation.views.query.grouping import source_group_key
from brain.presentation.views.query.source_labels import (
    clean_heading_title,
    knowledge_scope_suffix,
    source_fence_language,
    source_title as result_source_title,
)


def print_results_by_source(
    results: list[GlobalQueryResultDTO],
    color_enabled: bool,
    explain: bool,
    heading_level: int,
) -> None:
    """
    Print results grouped by logical source domain and reader command.

    Args:
        results (list[GlobalQueryResultDTO]): Results to render.
        color_enabled (bool): Whether ANSI placeholders should render.
        explain (bool): Whether backend rank details should be printed.
        heading_level (int): Markdown heading level for source groups.
    """
    source_groups: dict[str, list[GlobalQueryResultDTO]] = {}
    for result in results:
        source_groups.setdefault(source_group_key(result=result), []).append(result)

    for source_key, source_results in source_groups.items():
        if source_key:
            print(render_markdown(f"{'#' * heading_level} {source_key}", color_enabled))
        for result in source_results:
            print_result(result=result, color_enabled=color_enabled, explain=explain, show_source=False)
        print(render_markdown("---", color_enabled))


def print_result(
    result: GlobalQueryResultDTO,
    color_enabled: bool,
    explain: bool,
    show_source: bool = True,
) -> None:
    """
    Print one normalized query result.

    Args:
        result (GlobalQueryResultDTO): Result to render.
        color_enabled (bool): Whether ANSI color placeholders should render.
        explain (bool): Whether backend rank details should be printed.
        show_source (bool): Whether the source line should be printed inside the result.
    """
    if result.kind == "warning":
        warning_text: str = result.warning or result.title
        print(render_placeholders(f"- __YELLOW__Warning__RESET__: {warning_text}", color_enabled))
        return

    scope_text: str = knowledge_scope_suffix(result=result)
    prefix: str = f"- **{result.kind}{scope_text}**"
    if explain:
        prefix = f"- **{result.source}:{result.mechanism}:{result.kind}{scope_text}** rank={result.rank:.4f}"
    title: str = clean_heading_title(title=result.title) or "(untitled)"
    source_title: str = result_source_title(result=result)
    if not show_source and (
        (source_title and title == source_title)
        or result.source_ref.read_command.startswith("read-profile ")
    ):
        print(render_markdown(prefix, color_enabled))
    else:
        print(render_markdown(f"{prefix}: {title}", color_enabled))

    if show_source:
        print_source_ref(result=result, color_enabled=color_enabled, explain=explain)
    print_content(result=result, color_enabled=color_enabled)
    print_match(result=result, color_enabled=color_enabled, explain=explain)
    print_entities(result=result, color_enabled=color_enabled, explain=explain)
    print_relations(result=result, color_enabled=color_enabled)


def print_source_ref(result: GlobalQueryResultDTO, color_enabled: bool, explain: bool) -> None:
    """
    Print the structured source reference for a query result.

    Args:
        result (GlobalQueryResultDTO): Result to render.
        color_enabled (bool): Whether ANSI placeholders should render.
        explain (bool): Whether physical source details should be printed.
    """
    source_ref = result.source_ref
    if not source_ref.path and not source_ref.structure and not source_ref.read_command:
        return
    structure_text: str = source_ref.domain or " > ".join(source_ref.structure) or source_ref.path
    command_text: str = f" read:`{source_ref.read_command}`" if source_ref.read_command else ""
    path_text: str = f" physical:`{source_ref.path}`" if explain and source_ref.path else ""
    line_text: str = f" line {source_ref.line_number}" if source_ref.line_number else ""
    source_type_text: str = f" [{source_ref.source_type}]" if source_ref.source_type else ""
    print(render_markdown(f"  source{source_type_text}: {structure_text}{command_text}{path_text}{line_text}", color_enabled))


def print_content(result: GlobalQueryResultDTO, color_enabled: bool) -> None:
    """
    Print result content by default.

    Args:
        result (GlobalQueryResultDTO): Result to render.
        color_enabled (bool): Whether ANSI placeholders should render.
    """
    content_text: str = result.content.excerpt or result.text
    excerpt: str = compact_excerpt(text=content_text, limit=900)
    if not excerpt:
        return
    fence_language: str = source_fence_language(result=result)
    print(render_markdown(f"```{fence_language}", color_enabled))
    print(excerpt)
    print(render_markdown("```", color_enabled))


def print_match(result: GlobalQueryResultDTO, color_enabled: bool, explain: bool) -> None:
    """
    Print deep-query match diagnostics when requested.

    Args:
        result (GlobalQueryResultDTO): Result to render.
        color_enabled (bool): Whether ANSI placeholders should render.
        explain (bool): Whether match details should be printed.
    """
    if not explain or not result.match.explanation:
        return
    print(render_markdown(f"  match: {result.match.explanation}; score={result.match.adjusted_score:.4f}", color_enabled))


def print_entities(result: GlobalQueryResultDTO, color_enabled: bool, explain: bool) -> None:
    """
    Print entities involved in a query result.

    Args:
        result (GlobalQueryResultDTO): Result to render.
        color_enabled (bool): Whether ANSI placeholders should render.
        explain (bool): Whether source-scoped type assertions should be printed.
    """
    if not result.entities:
        return
    print(render_markdown("  entities:", color_enabled))
    for entity in result.entities[:8]:
        description: str = f" - {entity.description}" if entity.description else ""
        confidence: str = f" c:{format_confidence(entity.confidence)}" if entity.confidence else ""
        print(render_markdown(f"    - {entity}{confidence}{description}", color_enabled))
        if not explain:
            continue
        for assertion in entity.type_assertions[:4]:
            class_text: str = str(assertion.get("entity_class") or "")
            source_id = assertion.get("source_id")
            assertion_confidence = float(assertion.get("confidence") or 0.0)
            assertion_description: str = str(assertion.get("description") or "")
            source_text: str = f" src:{source_id}" if source_id is not None else ""
            confidence_text: str = (
                f" c:{format_confidence(assertion_confidence)}"
                if assertion_confidence
                else ""
            )
            description_text: str = f" - {assertion_description}" if assertion_description else ""
            print(
                render_markdown(
                    f"      type: {class_text}{source_text}{confidence_text}{description_text}",
                    color_enabled,
                ),
            )


def print_relations(result: GlobalQueryResultDTO, color_enabled: bool) -> None:
    """
    Print relations involved in a query result.

    Args:
        result (GlobalQueryResultDTO): Result to render.
        color_enabled (bool): Whether ANSI placeholders should render.
    """
    if not result.relations:
        return
    print(render_markdown("  relations:", color_enabled))
    for relation in result.relations[:8]:
        read_command: str = source_read_command_from_path(path=relation.source_path)
        source_text: str = f" src:`{read_command}`" if read_command else ""
        print(render_markdown(f"    - {relation}{source_text}", color_enabled))
