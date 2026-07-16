# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Human-readable terminal rendering for global query results."""

from __future__ import annotations

# Application Modules Imports
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryDeepResponseDTO
from brain.presentation.terminal import render_markdown, render_placeholders
from brain.presentation.views.query.blocks import print_results_by_source
from brain.presentation.views.query.grouping import ordered_evidence_groups


def print_human_results(
    results: list[GlobalQueryResultDTO],
    query_text: str,
    color_enabled: bool,
    explain: bool,
) -> None:
    """
    Print global query results for terminal users.

    Args:
        results (list[GlobalQueryResultDTO]): Query results.
        query_text (str): Original query text.
        color_enabled (bool): Whether ANSI color placeholders should render.
        explain (bool): Whether backend rank details should be printed.
    """
    if not results:
        print(render_placeholders("__YELLOW__No matches found.__RESET__", color_enabled))
        return

    print(render_placeholders(f"# Brain Query Matches for: __CYAN__{query_text}__RESET__", color_enabled))
    print()

    for group_title, group_results in ordered_evidence_groups(results=results):
        if not group_results:
            continue
        print(render_placeholders(f"## __GREEN__{group_title}__RESET__", color_enabled))
        print_results_by_source(
            results=group_results,
            color_enabled=color_enabled,
            explain=explain,
            heading_level=3,
        )
        print()


def print_human_deep_response(
    response_dto: QueryDeepResponseDTO,
    color_enabled: bool,
    explain: bool,
) -> None:
    """
    Print a contextual query response plus its supporting retrieval plan.

    Args:
        response_dto (QueryDeepResponseDTO): Contextual response DTO.
        color_enabled (bool): Whether ANSI color placeholders should render.
        explain (bool): Whether backend rank details should be printed.
    """
    print(render_placeholders(f"# Brain Deep Query for: __CYAN__{response_dto.query}__RESET__", color_enabled))
    print()
    print(render_placeholders("## __GREEN__Answer__RESET__", color_enabled))
    for line in response_dto.answer.splitlines():
        print(render_markdown(line, color_enabled))
    print()

    if response_dto.subqueries:
        print(render_placeholders("## __GREEN__Subqueries__RESET__", color_enabled))
        for subquery in response_dto.subqueries:
            match_count: int = len(subquery.results)
            print(
                render_markdown(
                    f'- [{subquery.index}] "{subquery.text}" - {subquery.reason}; matches: {match_count}',
                    color_enabled,
                ),
            )
        print()

    if response_dto.warnings:
        print(render_placeholders("## __YELLOW__Warnings__RESET__", color_enabled))
        for warning in response_dto.warnings:
            print(render_markdown(f"- {warning}", color_enabled))
        print()

    if not response_dto.results:
        return

    print(render_placeholders("## __GREEN__Evidence__RESET__", color_enabled))
    for group_title, group_results in ordered_evidence_groups(results=response_dto.results):
        if not group_results:
            continue
        print(render_placeholders(f"### __GREEN__{group_title}__RESET__", color_enabled))
        print_results_by_source(
            results=group_results,
            color_enabled=color_enabled,
            explain=explain,
            heading_level=4,
        )
