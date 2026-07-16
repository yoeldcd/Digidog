# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Multi-stage LLM sequencing for knowledge delta generation."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.llm.errors import KnowledgeLLMError
from brain.application.knowledge.llm.events import LLMEventCallback
from brain.application.knowledge.llm.stage_runner import generate_delta_with_llm
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO
from brain.config import KNOWLEDGE_DEFAULT_LLM_STAGE_NAMES as DEFAULT_LLM_STAGE_NAMES


def generate_multistage_deltas(
    source_path: str,
    content: str,
    base_delta: KnowledgeDeltaDTO,
    graph_context: str = "",
    entity_name_to_id: dict[str, int] | None = None,
    entity_class_catalog: dict[str, str] | None = None,
    stage_names: tuple[str, ...] = DEFAULT_LLM_STAGE_NAMES,
    event_callback: LLMEventCallback | None = None,
) -> tuple[list[tuple[str, KnowledgeDeltaDTO]], list[str]]:
    """
    Run every configured LLM stage and collect structured deltas.

    Args:
        source_path (str): Stable source path.
        content (str): Source text to analyze.
        base_delta (KnowledgeDeltaDTO): Starting delta accumulated before stage calls.
        graph_context (str): Compact read-only graph context.
        entity_name_to_id (dict[str, int] | None): Hidden exact-name resolver for existing entities.
        entity_class_catalog (dict[str, str] | None): Known class definitions for NER prompts.
        stage_names (tuple[str, ...]): Ordered model stages to execute.
        event_callback (LLMEventCallback | None): Optional live event sink.

    Returns:
        tuple[list[tuple[str, KnowledgeDeltaDTO]], list[str]]: Successful stage deltas and warnings.
    """
    stage_deltas: list[tuple[str, KnowledgeDeltaDTO]] = []
    warnings: list[str] = []
    accumulated_delta: KnowledgeDeltaDTO = base_delta

    for stage_name in stage_names:
        try:
            stage_delta: KnowledgeDeltaDTO = generate_delta_with_llm(
                stage_name=stage_name,
                source_path=source_path,
                content=content,
                prior_delta=accumulated_delta,
                graph_context=graph_context,
                entity_name_to_id=entity_name_to_id,
                entity_class_catalog=entity_class_catalog,
                event_callback=event_callback,
            )
        except KnowledgeLLMError as exc:
            warnings.append(str(exc))
            continue
        stage_deltas.append((stage_name, stage_delta))
        accumulated_delta = merge_stage_delta(
            accumulated_delta=accumulated_delta,
            stage_delta=stage_delta,
        )

    return stage_deltas, warnings


def merge_stage_delta(
    accumulated_delta: KnowledgeDeltaDTO,
    stage_delta: KnowledgeDeltaDTO,
) -> KnowledgeDeltaDTO:
    """
    Merge two stage deltas without importing extraction helpers.

    Args:
        accumulated_delta (KnowledgeDeltaDTO): Existing accumulated delta.
        stage_delta (KnowledgeDeltaDTO): Newly generated stage delta.

    Returns:
        KnowledgeDeltaDTO: Merged delta.
    """
    merged_entities = accumulated_delta.entities + stage_delta.entities
    merged_relations = accumulated_delta.relations + stage_delta.relations
    merged_suggestions = accumulated_delta.schema_suggestions + stage_delta.schema_suggestions
    rationale_parts: list[str] = [
        part
        for part in (accumulated_delta.rationale, stage_delta.rationale)
        if part
    ]
    return KnowledgeDeltaDTO(
        source_path=accumulated_delta.source_path or stage_delta.source_path,
        entities=merged_entities,
        aliases=[],
        relations=merged_relations,
        schema_suggestions=merged_suggestions,
        rationale="; ".join(rationale_parts),
    )
