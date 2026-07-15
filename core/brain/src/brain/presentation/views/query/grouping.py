"""Grouping helpers for global query terminal views."""

from __future__ import annotations

# Application Modules Imports
from brain.application.querying.dtos import GlobalQueryResultDTO
from brain.presentation.views.query.source_labels import source_kind as result_source_kind
from brain.presentation.views.query.source_labels import source_title as result_source_title


def ordered_evidence_groups(results: list[GlobalQueryResultDTO]) -> list[tuple[str, list[GlobalQueryResultDTO]]]:
    """
    Group query results by reader-facing evidence layer.

    Args:
        results (list[GlobalQueryResultDTO]): Results to group.

    Returns:
        list[tuple[str, list[GlobalQueryResultDTO]]]: Ordered group title and results.
    """
    return [
        (
            "Matched Memory Text",
            [
                result
                for result in results
                if result.source == "memory" and result.mechanism == "text"
            ],
        ),
        (
            "Semantic Fragments",
            [
                result
                for result in results
                if result.kind != "warning"
                and not (result.source == "memory" and result.mechanism == "text")
                and result.kind != "relation"
            ],
        ),
        (
            "Knowledge Relations",
            [
                result
                for result in results
                if result.kind == "relation"
            ],
        ),
        (
            "Warnings",
            [
                result
                for result in results
                if result.kind == "warning"
            ],
        ),
    ]


def source_group_key(result: GlobalQueryResultDTO) -> str:
    """
    Return a source group title for terminal query results.

    Args:
        result (GlobalQueryResultDTO): Result to group.

    Returns:
        str: Source group title.
    """
    source_ref = result.source_ref
    source_kind: str = result_source_kind(result=result)
    source_title: str = result_source_title(result=result)
    command_text: str = f" readed `{source_ref.read_command}`" if source_ref.read_command else ""
    if not source_title and not command_text:
        return ""
    return f"source {source_kind} {source_title}{command_text}".strip()
