# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Deterministic sanitizers for model-authored knowledge deltas."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.config import (
    KNOWLEDGE_LOCAL_ENTITY_ID_BASE as LOCAL_ENTITY_ID_BASE,
    KNOWLEDGE_MAX_ENTITY_DETECTION_ITEMS as MAX_ENTITY_DETECTION_ITEMS,
    KNOWLEDGE_MAX_RELATION_EXTRACTION_ITEMS as MAX_RELATION_EXTRACTION_ITEMS,
)
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO
from brain.application.knowledge.models.entity_classes import canonical_class_name, canonical_entity_class


def _sanitize_model_delta_payload(
    stage_name: str,
    payload: dict[str, Any],
    prior_delta: KnowledgeDeltaDTO | None = None,
    entity_name_to_id: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Remove source anchoring and unsupported fields from a model delta payload.

    Args:
        stage_name (str): Processing stage that produced the payload.
        payload (dict[str, Any]): Raw parsed model payload.
        prior_delta (KnowledgeDeltaDTO | None): Prior stage output used for exact-name relation resolution.
        entity_name_to_id (dict[str, int] | None): Hidden resolver for existing entity names.

    Returns:
        dict[str, Any]: DTO-compatible payload owned by semantic content only.
    """
    entity_payloads: list[dict[str, Any]] = []
    relation_payloads: list[dict[str, Any]] = []
    if stage_name == "entity_detection":
        entity_payloads = _sanitize_entity_payloads(payloads=payload.get("entities", []))
    if stage_name == "relation_extraction":
        resolved_entity_ids: dict[str, int] = _build_entity_name_resolver(
            prior_delta=prior_delta,
            entity_name_to_id=entity_name_to_id,
        )
        relation_payloads = [
            _sanitize_relation_payload(
                payload=relation_payload,
                entity_name_to_id=resolved_entity_ids,
            )
            for relation_payload in payload.get("relations", [])[:MAX_RELATION_EXTRACTION_ITEMS]
            if isinstance(relation_payload, dict)
        ]
    return {
        "source_path": payload.get("source_path", ""),
        "entities": entity_payloads,
        "aliases": [],
        "relations": relation_payloads,
        "schema_suggestions": [],
        "rationale": str(payload.get("rationale") or "")[:300],
    }


def _sanitize_entity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Keep only semantic entity DTO fields emitted by the model.

    Args:
        payload (dict[str, Any]): Raw entity payload.

    Returns:
        dict[str, Any]: Entity DTO payload without source anchoring.
    """
    entity_class: str = canonical_entity_class(str(payload.get("entity_class", "MISC.Concept")))
    canonical_name: str = str(payload.get("canonical_name", "")).strip()
    if entity_class == "CLS":
        canonical_name = canonical_class_name(canonical_name)
    return {
        "id": None,
        "entity_class": entity_class,
        "canonical_name": canonical_name,
        "description": str(payload.get("description") or "")[:160],
        "confidence": payload.get("confidence", 0.65),
    }


def _sanitize_entity_payloads(payloads: Any) -> list[dict[str, Any]]:
    """
    Keep entity records and assign harness-only local IDs.

    Args:
        payloads (Any): Raw entity array emitted by the model.

    Returns:
        list[dict[str, Any]]: Entity DTO payloads with deterministic local IDs.
    """
    if not isinstance(payloads, list):
        return []
    entity_payloads: list[dict[str, Any]] = []
    for index, entity_payload in enumerate(payloads[:MAX_ENTITY_DETECTION_ITEMS], start=1):
        if not isinstance(entity_payload, dict):
            continue
        sanitized_payload: dict[str, Any] = _sanitize_entity_payload(payload=entity_payload)
        sanitized_payload["id"] = LOCAL_ENTITY_ID_BASE + index
        entity_payloads.append(sanitized_payload)
    return entity_payloads


def _sanitize_relation_payload(payload: dict[str, Any], entity_name_to_id: dict[str, int]) -> dict[str, Any]:
    """
    Keep only semantic relation fields and resolve exact entity names to IDs.

    Args:
        payload (dict[str, Any]): Raw relation payload.
        entity_name_to_id (dict[str, int]): Normalized entity names mapped to local or persisted IDs.

    Returns:
        dict[str, Any]: Relation DTO payload without source anchoring.
    """
    subject_name: str = _relation_endpoint_name(
        payload=payload,
        field_names=("subject_name", "subjectName", "subject"),
    )
    object_name: str = _relation_endpoint_name(
        payload=payload,
        field_names=("object_name", "objectName", "object"),
    )
    return {
        "id": None,
        "subject_id": _resolve_entity_name(entity_name=subject_name, entity_name_to_id=entity_name_to_id),
        "object_id": _resolve_entity_name(entity_name=object_name, entity_name_to_id=entity_name_to_id),
        "predicate": payload.get("predicate", "related_to"),
        "confidence": payload.get("confidence", 0.65),
    }


def _build_entity_name_resolver(
    prior_delta: KnowledgeDeltaDTO | None,
    entity_name_to_id: dict[str, int] | None,
) -> dict[str, int]:
    """
    Build an exact-name resolver for model-proposed relation endpoints.

    Args:
        prior_delta (KnowledgeDeltaDTO | None): Accumulated stage delta with local entity IDs.
        entity_name_to_id (dict[str, int] | None): Existing persisted entity names to IDs.

    Returns:
        dict[str, int]: Normalized canonical names mapped to entity IDs.
    """
    resolved_entity_ids: dict[str, int] = {}
    for entity_name, entity_id in (entity_name_to_id or {}).items():
        resolved_entity_ids[_normalize_entity_name(entity_name)] = int(entity_id)
    if prior_delta is None:
        return resolved_entity_ids
    for entity_dto in prior_delta.entities:
        if entity_dto.id is None:
            continue
        resolved_entity_ids[_normalize_entity_name(entity_dto.canonical_name)] = int(entity_dto.id)
    return resolved_entity_ids


def _relation_endpoint_name(payload: dict[str, Any], field_names: tuple[str, ...]) -> str:
    """
    Extract an endpoint canonical name from model relation JSON.

    Args:
        payload (dict[str, Any]): Raw relation payload.
        field_names (tuple[str, ...]): Accepted endpoint name fields.

    Returns:
        str: Endpoint name or empty text.
    """
    for field_name in field_names:
        value: Any = payload.get(field_name)
        if isinstance(value, str):
            return value.strip()
    return ""


def _resolve_entity_name(entity_name: str, entity_name_to_id: dict[str, int]) -> int | None:
    """
    Resolve an exact canonical entity name to an entity ID.

    Args:
        entity_name (str): Model-proposed endpoint name.
        entity_name_to_id (dict[str, int]): Normalized entity names mapped to IDs.

    Returns:
        int | None: Resolved entity ID, or None when the name is unknown.
    """
    if not entity_name:
        return None
    return entity_name_to_id.get(_normalize_entity_name(entity_name))


def _normalize_entity_name(value: str) -> str:
    """
    Normalize entity names for exact relation endpoint matching.

    Args:
        value (str): Raw entity name.

    Returns:
        str: Case-folded, whitespace-normalized name.
    """
    return " ".join(str(value).split()).casefold()
