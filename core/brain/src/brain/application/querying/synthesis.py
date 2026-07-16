# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Deep answer synthesis for global query."""

from __future__ import annotations

# Standard Libraries Imports
import json
from typing import Any

# Application Modules Imports
from brain.application.querying.dtos import (
    GlobalQueryResultDTO,
    QueryContextDTO,
    QuerySelectedEntityDTO,
    QuerySubqueryDTO,
)
from brain.application.querying.llm import request_query_json


def synthesize_deep_answer(
    query_text: str,
    context: QueryContextDTO,
    subqueries: list[QuerySubqueryDTO],
    selected_entities: list[QuerySelectedEntityDTO],
    results: list[GlobalQueryResultDTO],
) -> tuple[str, list[str]]:
    """
    Synthesize a grounded answer from deep-query evidence.

    Args:
        query_text (str): Original query.
        context (QueryContextDTO): Parsed query context.
        subqueries (list[QuerySubqueryDTO]): Planned retrieval passes.
        selected_entities (list[QuerySelectedEntityDTO]): Query-relevant entities.
        results (list[GlobalQueryResultDTO]): Deduplicated evidence results.

    Returns:
        tuple[str, list[str]]: Answer text and non-blocking warnings.
    """
    usable_results: list[GlobalQueryResultDTO] = [
        result
        for result in results
        if result.kind != "warning"
    ]
    if not usable_results:
        return (
            "I could not find enough indexed knowledgebase evidence to answer this query. "
            "Run dream after source updates, or broaden the query terms.",
            [],
        )
    try:
        answer_text: str = synthesize_with_llm(
            query_text=query_text,
            context=context,
            selected_entities=selected_entities,
            results=usable_results,
        )
        if answer_text:
            return answer_text, []
    except Exception as exc:
        return (
            synthesize_deterministic_answer(
                query_text=query_text,
                context=context,
                subqueries=subqueries,
                selected_entities=selected_entities,
                results=usable_results,
            ),
            [f"LLM answer synthesis unavailable; deterministic synthesis used: {exc}"],
        )
    return (
        synthesize_deterministic_answer(
            query_text=query_text,
            context=context,
            subqueries=subqueries,
            selected_entities=selected_entities,
            results=usable_results,
        ),
        [],
    )


def synthesize_with_llm(
    query_text: str,
    context: QueryContextDTO,
    selected_entities: list[QuerySelectedEntityDTO],
    results: list[GlobalQueryResultDTO],
) -> str:
    """
    Ask the configured text model to write a cited answer.

    Args:
        query_text (str): Original query.
        context (QueryContextDTO): Parsed query context.
        selected_entities (list[QuerySelectedEntityDTO]): Query-relevant entities.
        results (list[GlobalQueryResultDTO]): Evidence results.

    Returns:
        str: Model answer.
    """
    evidence_payload: list[dict[str, Any]] = [
        evidence_payload_for_result(result=result, index=index)
        for index, result in enumerate(results[:8], 1)
    ]
    payload = request_query_json(
        system_prompt=(
            "Answer from the provided evidence only. Cite evidence IDs like [E1]. "
            "If evidence is insufficient, say so. Return JSON with one string field: answer."
        ),
        user_prompt=json.dumps(
            {
                "query": query_text,
                "keywords": context.keywords,
                "date_constraints": [constraint.model_dump(mode="json") for constraint in context.date_constraints],
                "selected_entities": [entity.model_dump(mode="json") for entity in selected_entities],
                "evidence": evidence_payload,
            },
            ensure_ascii=False,
        ),
        max_tokens=1600,
    )
    answer: str = str(payload.get("answer") or "").strip()
    if not answer:
        raise RuntimeError("text model returned an empty answer")
    return answer


def synthesize_deterministic_answer(
    query_text: str,
    context: QueryContextDTO,
    subqueries: list[QuerySubqueryDTO],
    selected_entities: list[QuerySelectedEntityDTO],
    results: list[GlobalQueryResultDTO],
) -> str:
    """
    Build a deterministic cited answer from evidence.

    Args:
        query_text (str): Original query.
        context (QueryContextDTO): Parsed query context.
        subqueries (list[QuerySubqueryDTO]): Planned retrieval passes.
        selected_entities (list[QuerySelectedEntityDTO]): Query-relevant entities.
        results (list[GlobalQueryResultDTO]): Evidence results.

    Returns:
        str: Reader-facing answer.
    """
    source_count: int = len(
        {
            result.source_ref.domain or result.source_ref.read_command
            for result in results
            if result.source_ref.domain or result.source_ref.read_command
        },
    )
    lines: list[str] = [
        (
            f'For "{query_text}", deep retrieval used {len(subqueries)} pass(es), '
            f"{len(context.keywords)} keyword(s), and {len(results)} grounded evidence item(s)"
            f"{f' across {source_count} source(s)' if source_count else ''}."
        ),
    ]
    if context.date_constraints:
        date_labels: str = ", ".join(constraint.label for constraint in context.date_constraints)
        lines.append(f"Temporal scope: {date_labels}.")
    if selected_entities:
        entity_summary: str = "; ".join(
            f'{entity.entity_class or "entity"}:"{entity.name}"'
            for entity in selected_entities[:5]
        )
        lines.append(f"Selected entities: {entity_summary}.")
    lines.extend(evidence_lines(results=results))
    return "\n".join(lines)


def evidence_lines(results: list[GlobalQueryResultDTO]) -> list[str]:
    """
    Build deterministic evidence lines with citations.

    Args:
        results (list[GlobalQueryResultDTO]): Evidence results.

    Returns:
        list[str]: Cited evidence lines.
    """
    lines: list[str] = []
    for index, result in enumerate(results[:8], 1):
        excerpt: str = compact_response_text(text=result.content.excerpt or result.text, limit=220)
        relation_text: str = summarize_result_relations(result=result)
        entity_text: str = summarize_result_entities(result=result)
        why: str = result.match.explanation or "retrieved as relevant context"
        evidence_text: str = excerpt or relation_text or entity_text or result.title
        lines.append(f'- [E{index}] {result.title}: "{evidence_text}" This matters because {why}.')
    return lines


def evidence_payload_for_result(result: GlobalQueryResultDTO, index: int) -> dict[str, Any]:
    """
    Convert one result into bounded LLM evidence.

    Args:
        result (GlobalQueryResultDTO): Evidence result.
        index (int): 1-based evidence index.

    Returns:
        dict[str, Any]: Compact evidence payload.
    """
    return {
        "id": f"E{index}",
        "title": result.title,
        "excerpt": compact_response_text(text=result.content.excerpt or result.text, limit=700),
        "entities": [str(entity) for entity in result.entities[:6]],
        "relations": [str(relation) for relation in result.relations[:4]],
        "match": result.match.model_dump(mode="json"),
        "source": result.source_ref.read_command or result.source_ref.domain,
    }


def summarize_result_entities(result: GlobalQueryResultDTO) -> str:
    """Return a compact entity summary for one result."""
    return "; ".join(str(entity) for entity in result.entities[:4])


def summarize_result_relations(result: GlobalQueryResultDTO) -> str:
    """Return a compact relation summary for one result."""
    return "; ".join(str(relation) for relation in result.relations[:3])


def compact_response_text(text: str, limit: int) -> str:
    """
    Compact response text to a bounded single line.

    Args:
        text (str): Raw text.
        limit (int): Maximum number of characters.

    Returns:
        str: Compact text.
    """
    compact_text: str = " ".join(text.split())
    if len(compact_text) <= limit:
        return compact_text
    return f"{compact_text[:max(0, limit - 3)].rstrip()}..."
