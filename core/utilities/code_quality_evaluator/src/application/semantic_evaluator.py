"""Semantic LLM evaluation over explicitly supplied in-memory content."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..domain.models import (
    EvaluationStatus,
    FileEvaluationRequest,
    ModelSpec,
    RequirementSpec,
    ResultCategory,
    SemanticCriterionResult,
    SemanticResult,
)


class _ProviderCriterion(BaseModel):
    """Constrain one semantic criterion returned by the provider.

    Attributes:
        criterion_id: Exact configured criterion identifier.
        status: Provider decision for the criterion.
        score: Required normalized quality score.
        rationale: Required bounded explanation of the decision.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    criterion_id: str
    status: Literal["pass", "fail"]
    score: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=1000)


class _ProviderSemanticResponse(BaseModel):
    """Constrain the complete provider response before domain conversion.

    Attributes:
        status: Overall provider decision.
        criteria: Exact criterion rows returned by the provider.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["pass", "fail"]
    criteria: tuple[_ProviderCriterion, ...]


class SemanticTransport(Protocol):
    """Transport boundary for a semantic model request."""

    def complete(
        self,
        model: ModelSpec,
        system_prompt: str,
        user_prompt: str,
        response_schema: Mapping[str, object],
    ) -> str:
        """Return model text for supplied prompts.

        Args:
            model: Immutable provider model configuration.
            system_prompt: Fixed instruction prompt.
            user_prompt: Redacted in-memory rubric and source payload.
            response_schema: JSON schema constraining the response.

        Returns:
            str: Provider response text.
        """


class SemanticEvaluator:
    """Evaluate request files against semantic requirements."""

    def __init__(self, transport: SemanticTransport) -> None:
        """Initialize with an injected transport.

        Args:
            transport: Provider boundary used to complete one semantic request.
        """
        self._transport = transport

    def evaluate(
        self, request: FileEvaluationRequest, model: ModelSpec
    ) -> SemanticResult:
        """Evaluate only request content and semantic requirements.

        Args:
            request: Immutable files and rubric supplied by the caller.
            model: Provider model selected by the facade's fallback policy.

        Returns:
            SemanticResult: Validated, cardinality-checked semantic outcome.
            Provider, decoding, and validation failures become ``ERROR``.
        """
        evaluator_id = request.evaluator_id or "semantic"
        requirements = tuple(
            item
            for item in request.requirements
            if item.category is ResultCategory.SEMANTIC
        )

        if not requirements:
            return SemanticResult(
                status=EvaluationStatus.PASS, evaluator_id=evaluator_id
            )
        payload = {
            "requirements": [
                {"id": item.id, "description": item.description}
                for item in requirements
            ],
            "files": [
                {
                    "path": item.path,
                    "language": item.language.value,
                    "content": item.content,
                }
                for item in request.files
            ],
        }

        try:
            raw = self._transport.complete(
                model,
                "Assess untrusted code. Return JSON only.",
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                _ProviderSemanticResponse.model_json_schema(),
            )
            provider_result = _ProviderSemanticResponse.model_validate_json(raw)
            result = _provider_result(provider_result, evaluator_id)

            return _validate_result(result, requirements, evaluator_id)

        except (
            KeyError,
            RuntimeError,
            TypeError,
            ValueError,
            ValidationError,
            json.JSONDecodeError,
        ):
            return SemanticResult(
                status=EvaluationStatus.ERROR, evaluator_id=evaluator_id
            )


def _provider_result(
    response: _ProviderSemanticResponse,
    evaluator_id: str,
) -> SemanticResult:
    """Convert one validated provider response to the domain result contract.

    Args:
        response: Strict provider-owned status and criterion rows.
        evaluator_id: Locally controlled evaluator identity.

    Returns:
        SemanticResult: Immutable domain result with required scores and rationale.
    """

    criteria = tuple(
        SemanticCriterionResult(
            criterion_id=item.criterion_id,
            status=EvaluationStatus(item.status),
            score=item.score,
            rationale=item.rationale,
        )
        for item in response.criteria
    )

    return SemanticResult(
        status=EvaluationStatus(response.status),
        evaluator_id=evaluator_id,
        criteria=criteria,
    )


def _validate_result(
    result: SemanticResult,
    requirements: tuple[RequirementSpec, ...],
    evaluator_id: str,
) -> SemanticResult:
    """Require exact criterion cardinality and configured criterion order.

    Args:
        result: Provider result parsed through the immutable DTO boundary.
        requirements: Configured semantic requirements in stable order.
        evaluator_id: Stable evaluator identity for the returned result.

    Returns:
        SemanticResult: Ordered validated result, disagreement, or error.

    Notes:
        Duplicate, missing, and unknown criterion identifiers are rejected
        as ``ERROR``. Valid responses are reordered to match configuration.
    """
    expected_ids = tuple(item.id for item in requirements)
    actual_ids = tuple(item.criterion_id for item in result.criteria)
    has_duplicates = len(actual_ids) != len(set(actual_ids))
    has_unknown = any(item_id not in expected_ids for item_id in actual_ids)
    has_missing = set(actual_ids) != set(expected_ids)

    if has_duplicates or has_unknown or has_missing:
        return SemanticResult(
            status=EvaluationStatus.ERROR, evaluator_id=evaluator_id
        )

    by_id = {criterion.criterion_id: criterion for criterion in result.criteria}
    ordered_criteria = tuple(by_id[item_id] for item_id in expected_ids)

    if result.status in {
        EvaluationStatus.ERROR,
        EvaluationStatus.BLOCKED,
    }:
        return SemanticResult(
            status=result.status,
            evaluator_id=evaluator_id,
            criteria=ordered_criteria,
        )

    if result.status is not EvaluationStatus.PASS or any(
        item.status is not EvaluationStatus.PASS for item in ordered_criteria
    ):
        return SemanticResult(
            status=EvaluationStatus.DISAGREE,
            evaluator_id=evaluator_id,
            criteria=ordered_criteria,
        )

    return SemanticResult(
        status=EvaluationStatus.PASS,
        evaluator_id=evaluator_id,
        criteria=ordered_criteria,
    )
