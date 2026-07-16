# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Prompt rendering for knowledge LLM extraction stages."""

from __future__ import annotations

# Standard Libraries Imports
import json
from typing import Any

# Application Modules Imports
from brain.config import (
    KNOWLEDGE_MAX_ENTITY_DETECTION_ITEMS as MAX_ENTITY_DETECTION_ITEMS,
    KNOWLEDGE_MAX_PROMPT_CONTENT_CHARS as MAX_PROMPT_CONTENT_CHARS,
    KNOWLEDGE_MAX_RELATION_EXTRACTION_ITEMS as MAX_RELATION_EXTRACTION_ITEMS,
    KNOWLEDGE_MAX_RELATION_PROMPT_ENTITIES as MAX_RELATION_PROMPT_ENTITIES,
)
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO
from brain.application.knowledge.models.entity_classes import build_entity_class_catalog
from brain.infrastructure.prompts import render_stage_prompt


def build_delta_prompt(
    stage_name: str,
    source_path: str,
    content: str,
    prior_delta: KnowledgeDeltaDTO | None = None,
    graph_context: str = "",
    entity_class_catalog: dict[str, str] | None = None,
) -> str:
    """
    Build the extraction prompt for a source.

    Args:
        stage_name (str): Configured processing stage.
        source_path (str): Stable source path.
        content (str): Source content.
        prior_delta (KnowledgeDeltaDTO | None): Accumulated delta from earlier stages.
        graph_context (str): Compact read-only graph context.
        entity_class_catalog (dict[str, str] | None): Known class definitions for NER prompts.

    Returns:
        str: Prompt text.
    """
    clipped_content: str = content[:MAX_PROMPT_CONTENT_CHARS]
    prior_delta_json: str = _build_prior_delta_prompt_json(
        stage_name=stage_name,
        prior_delta=prior_delta,
    )
    classifier_catalog: str = _build_classifier_catalog_prompt(
        stage_name=stage_name,
        entity_class_catalog=entity_class_catalog,
    )
    return render_stage_prompt(
        stage_name=stage_name,
        values={
            "stage_name": stage_name,
            "max_entity_detection_items": str(MAX_ENTITY_DETECTION_ITEMS),
            "max_relation_extraction_items": str(MAX_RELATION_EXTRACTION_ITEMS),
            "graph_context": graph_context[:6000],
            "classifier_catalog": classifier_catalog,
            "prior_delta_json": prior_delta_json[:4000],
            "response_format_summary": _build_response_format_summary(stage_name=stage_name),
            "response_format_rules": _build_response_format_rules(stage_name=stage_name),
            "content": clipped_content,
        },
    )


def _build_response_format_summary(stage_name: str) -> str:
    """
    Build the stage-specific response format summary.

    Args:
        stage_name (str): Active LLM stage name.

    Returns:
        str: One-line response format instruction.
    """
    if stage_name == "relation_extraction":
        return (
            f"Analyze the provided content for stage `{stage_name}` and return compact relation triplet lines."
        )
    return f"Analyze the provided content for stage `{stage_name}` and propose a compact JSON KnowledgeDeltaDTO."


def _build_response_format_rules(stage_name: str) -> str:
    """
    Build stage-specific response format rules.

    Args:
        stage_name (str): Active LLM stage name.

    Returns:
        str: Markdown bullet rules rendered into the prompt.
    """
    if stage_name == "relation_extraction":
        return "\n".join(
            [
                "- Return raw text only. Do not return JSON and do not wrap it in Markdown fences.",
                '- Emit one relation per line using exactly: ("subject_name","predicate","object_name").',
                "- Escape internal double quotes with a backslash.",
                "- Do not include confidence values; the local pipeline assigns relation confidence.",
                "- Return exactly NONE when the stage has no useful relation to add.",
            ],
        )
    return "\n".join(
        [
            "- Return raw JSON only. Do not wrap it in Markdown fences.",
            "- Emit only these top-level keys: entities, relations, rationale.",
            "- Raw relation proposal shape for JSON stages is only: subject_name, object_name, predicate, confidence.",
        ],
    )


def _build_classifier_catalog_prompt(
    stage_name: str,
    entity_class_catalog: dict[str, str] | None,
) -> str:
    """
    Build the classifier catalog shown to entity detection.

    Args:
        stage_name (str): Active LLM stage name.
        entity_class_catalog (dict[str, str] | None): Known class definitions.

    Returns:
        str: Prompt catalog or a stage-specific omission note.
    """
    if stage_name != "entity_detection":
        return "Omitted for this stage; relation extraction uses entity names from prior deltas."
    return build_entity_class_catalog(known_classes=entity_class_catalog)


def _build_prior_delta_prompt_json(stage_name: str, prior_delta: KnowledgeDeltaDTO | None) -> str:
    """
    Render prior stage output for the model without exposing local endpoint IDs.

    Args:
        stage_name (str): Stage receiving the prior delta.
        prior_delta (KnowledgeDeltaDTO | None): Accumulated stage delta.

    Returns:
        str: JSON text safe for model-side exact-name references.
    """
    if prior_delta is None:
        return "{}"
    if stage_name != "relation_extraction":
        return prior_delta.model_dump_json(indent=2)
    payload: dict[str, Any] = {
        "entities": [
            {
                "entity_class": entity_dto.entity_class,
                "canonical_name": entity_dto.canonical_name,
                "description": entity_dto.description,
                "confidence": entity_dto.confidence,
            }
            for entity_dto in prior_delta.entities[:MAX_RELATION_PROMPT_ENTITIES]
        ],
        "relations": [],
        "rationale": prior_delta.rationale,
    }
    return json.dumps(payload, indent=2)
