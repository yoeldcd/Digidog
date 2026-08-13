"""Parse compact JSON payloads through the immutable DTO source of truth."""

from __future__ import annotations

import json
from collections.abc import Mapping

from pydantic import ValidationError

from ..domain.models import AggregateResult, FileEvaluationRequest


class SpecificationError(ValueError):
    """Report an invalid evaluator request or result without source leakage."""


def parse_request(payload: str | bytes | Mapping[str, object]) -> FileEvaluationRequest:
    """Parse one strict in-memory file-evaluation request.

    Args:
        payload: Serialized JSON bytes/text or an already decoded mapping.

    Returns:
        FileEvaluationRequest: Frozen validated request DTO.

    Raises:
        SpecificationError: If JSON decoding or DTO validation fails.
    """

    try:
        if isinstance(payload, bytes):
            serialized = payload.decode("utf-8", errors="strict")

            return FileEvaluationRequest.model_validate_json(serialized)

        if isinstance(payload, str):
            return FileEvaluationRequest.model_validate_json(payload)

        serialized = json.dumps(
            dict(payload), ensure_ascii=False, separators=(",", ":")
        )

        return FileEvaluationRequest.model_validate_json(serialized)

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        TypeError,
    ) as error:
        raise SpecificationError("Invalid code-quality evaluation request.") from error


def parse_result(payload: str | bytes | Mapping[str, object]) -> AggregateResult:
    """Parse one strict aggregate result.

    Args:
        payload: Serialized JSON bytes/text or an already decoded mapping.

    Returns:
        AggregateResult: Frozen validated aggregate DTO.

    Raises:
        SpecificationError: If JSON decoding or DTO validation fails.
    """

    try:
        if isinstance(payload, bytes):
            serialized = payload.decode("utf-8", errors="strict")

            return AggregateResult.model_validate_json(serialized)

        if isinstance(payload, str):
            return AggregateResult.model_validate_json(payload)

        serialized = json.dumps(
            dict(payload), ensure_ascii=False, separators=(",", ":")
        )

        return AggregateResult.model_validate_json(serialized)

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        TypeError,
    ) as error:
        raise SpecificationError("Invalid code-quality evaluation result.") from error
