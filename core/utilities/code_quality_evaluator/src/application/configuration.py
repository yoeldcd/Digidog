"""Load isolated evaluator configuration and expose generated schema text."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from ..domain.models import (
    CodeEvaluatorConfig,
    EvaluatorSpec,
    FileEvaluationRequest,
    Language,
    LanguageQualityPolicy,
    ModelSpec,
)
from ..presentation.models import ErrorReport, EvaluationReport, FormatReport


class ConfigError(ValueError):
    """Report configuration failures without exposing secrets or source details."""


@dataclass(frozen=True, slots=True)
class SchemaSnapshot:
    """Represent one immutable generated JSON-schema document.

    Attributes:
        filename: Canonical snapshot filename.
        content: Readable Draft 2020-12 JSON text generated from a DTO.
    """

    filename: str
    content: str


_SCHEMA_MODELS: Final[tuple[tuple[str, type[object]], ...]] = (
    ("request.schema.json", FileEvaluationRequest),
    ("result.schema.json", EvaluationReport),
    ("format_result.schema.json", FormatReport),
    ("error_result.schema.json", ErrorReport),
    ("config.schema.json", CodeEvaluatorConfig),
    ("model_spec.schema.json", ModelSpec),
)


def load_config(path: Path) -> CodeEvaluatorConfig:
    """Load strict evaluator configuration from an explicit JSON path.

    Args:
        path: Existing UTF-8 configuration file selected by the caller.

    Returns:
        CodeEvaluatorConfig: Frozen validated utility configuration.

    Raises:
        ConfigError: Reading, decoding, or DTO validation fails.
    """

    try:
        serialized = path.read_text(encoding="utf-8")

        return CodeEvaluatorConfig.model_validate_json(serialized)

    except (OSError, UnicodeError, ValidationError, ValueError, TypeError) as error:
        raise ConfigError("Invalid evaluator configuration.") from error


def resolve_evaluator(
    config: CodeEvaluatorConfig,
    evaluator_id: str | None = None,
) -> EvaluatorSpec:
    """Resolve an evaluator profile or the configured default.

    Args:
        config: Immutable loaded utility configuration.
        evaluator_id: Optional explicit profile identity.

    Returns:
        EvaluatorSpec: Selected immutable evaluator profile.

    Raises:
        ConfigError: The requested profile does not exist.
    """

    selected_id = evaluator_id or config.default_evaluator_id

    for evaluator in config.evaluators:
        if evaluator.id == selected_id:
            return evaluator

    raise ConfigError("Unknown evaluator identifier.")


def resolve_language_policy(
    evaluator: EvaluatorSpec,
    language: Language,
) -> LanguageQualityPolicy:
    """Resolve one explicitly configured language policy.

    Args:
        evaluator: Immutable evaluator profile.
        language: Language whose policy is required.

    Returns:
        LanguageQualityPolicy: Exact policy configured for ``language``.

    Raises:
        ConfigError: If the evaluator has no policy for the requested language.
    """

    try:
        return evaluator.policy_for(language)

    except ValueError as error:
        raise ConfigError("Unknown language policy.") from error


def generate_schema_snapshots() -> tuple[SchemaSnapshot, ...]:
    """Generate readable immutable JSON-schema snapshots from DTO classes.

    Args:
        No arguments are accepted.

    Returns:
        tuple[SchemaSnapshot, ...]: Stable filename and schema-text pairs.
    """

    snapshots: list[SchemaSnapshot] = []

    for filename, model in _SCHEMA_MODELS:
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **model.model_json_schema(),
        }
        content = json.dumps(
            schema,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        snapshots.append(
            SchemaSnapshot(
                filename=filename,
                content=f"{content}\n",
            )
        )

    return tuple(snapshots)
