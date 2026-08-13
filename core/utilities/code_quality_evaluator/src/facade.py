"""Public in-memory facade for deterministic and semantic code evaluation."""

from __future__ import annotations

import time
from pathlib import PurePosixPath

from .application.checks.registry import DEFAULT_DISPATCHER
from .application.checks.shared.aggregation import aggregate_gates
from .application.checks.shared.artifact import evaluate_artifact
from .application.semantic_evaluator import SemanticEvaluator, SemanticTransport
from .domain.models import (
    AggregateResult,
    DeterministicResult,
    EvaluationStatus,
    EvaluatorSpec,
    Evidence,
    FileEvaluationRequest,
    GateResult,
    InMemoryFile,
    LanguageQualityPolicy,
    RequirementSpec,
    SemanticCriterionResult,
    SemanticResult,
)
from .infrastructure.command_runner import InMemoryCommandRunner

_PRECEDENCE = {
    EvaluationStatus.PASS: 1,
    EvaluationStatus.FAIL: 2,
    EvaluationStatus.DISAGREE: 2,
    EvaluationStatus.BLOCKED: 3,
    EvaluationStatus.ERROR: 4,
}


def _status(values: tuple[EvaluationStatus, ...]) -> EvaluationStatus:
    """Return the highest-severity status, preserving deterministic precedence.

    Args:
        values: Immutable statuses produced by one evaluation layer.

    Returns:
        EvaluationStatus: Highest-severity status, or ``PASS`` when empty.
    """

    return max(
        values, key=lambda value: _PRECEDENCE[value], default=EvaluationStatus.PASS
    )


def _path_matches(path: str, pattern: str) -> bool:
    """Match one relative path, including top-level files for recursive patterns.

    Args:
        path: Workspace-relative POSIX path.
        pattern: Configured glob-style selection pattern.

    Returns:
        bool: True when the pattern selects the path.
    """

    candidate = PurePosixPath(path)

    if candidate.match(pattern):
        return True

    if pattern.startswith("**/"):
        return candidate.match(pattern.removeprefix("**/"))

    return False


def _policy_for_artifact(
    evaluator: EvaluatorSpec,
    artifact: InMemoryFile,
) -> LanguageQualityPolicy | None:
    """Resolve an artifact policy while keeping unsupported files evaluable.

    Args:
        evaluator: Immutable evaluator profile.
        artifact: Source artifact whose language policy is requested.

    Returns:
        LanguageQualityPolicy | None: Matching policy, or ``None`` for an
        unsupported language. Unsupported artifacts still receive profile and
        baseline deterministic gates.
    """

    try:
        return evaluator.policy_for(artifact.language)

    except ValueError:
        return None


def _deterministic(
    request: FileEvaluationRequest, evaluator: EvaluatorSpec
) -> DeterministicResult:
    """Run all artifact, language, and explicit command checks in stable order.

    Args:
        request: Immutable files and commands supplied by the caller.
        evaluator: Immutable profile and per-language quality policies.

    Returns:
        DeterministicResult: Complete outcome for every file and command.
    """
    gates: list[GateResult] = []

    for file_index, artifact in enumerate(request.files, start=1):
        language_is_supported = artifact.language in evaluator.languages
        path_is_selected = any(
            _path_matches(artifact.path, pattern) for pattern in evaluator.path_patterns
        )
        profile_evidence = (
            Evidence(
                path=artifact.path,
                kind="profile",
                summary="evaluator profile selection",
            ),
        )
        gates.extend(
            (
                GateResult(
                    gate_id=f"file-{file_index}-PROFILE-LANGUAGE",
                    status=(
                        EvaluationStatus.PASS
                        if language_is_supported
                        else EvaluationStatus.FAIL
                    ),
                    message="language is supported by evaluator",
                    evidence=profile_evidence,
                ),
                GateResult(
                    gate_id=f"file-{file_index}-PROFILE-PATH",
                    status=(
                        EvaluationStatus.PASS
                        if path_is_selected
                        else EvaluationStatus.FAIL
                    ),
                    message="path is selected by evaluator",
                    evidence=profile_evidence,
                ),
            )
        )
        policy = _policy_for_artifact(evaluator, artifact)

        if policy is None:
            artifact_gates = evaluate_artifact(
                artifact.path,
                artifact.content,
                artifact.path,
            )

        else:
            dispatched = DEFAULT_DISPATCHER.dispatch(artifact, policy)
            artifact_gates = dispatched.gates

        for gate in artifact_gates:
            gates.append(
                gate.model_copy(update={"gate_id": f"file-{file_index}-{gate.gate_id}"})
            )
    ordered_gates = aggregate_gates(tuple(gates))
    runner = InMemoryCommandRunner()
    commands = tuple(
        runner.run(command, stdin="", evidence_path="command")
        for command in sorted(request.commands, key=lambda item: item.id)
    )
    statuses = tuple(gate.status for gate in ordered_gates) + tuple(
        command.status for command in commands
    )

    return DeterministicResult(
        status=_status(statuses), commands=commands, gates=ordered_gates
    )


def _namespaced_requirements(
    requirements: tuple[RequirementSpec, ...],
    file_index: int,
) -> tuple[RequirementSpec, ...]:
    """Namespace one artifact's requirements in configured order.

    Args:
        requirements: Semantic requirements from one language policy.
        file_index: One-based artifact index in the input request.

    Returns:
        tuple[RequirementSpec, ...]: Immutable namespaced requirements.
    """

    return tuple(
        requirement.model_copy(update={"id": f"file-{file_index}-{requirement.id}"})
        for requirement in requirements
    )


def _threshold_result(
    result: SemanticResult,
    threshold: float,
) -> SemanticResult:
    """Apply one policy's minimum mean score to a passing result.

    Args:
        result: Validated semantic result for one artifact.
        threshold: Minimum configured score for that artifact.

    Returns:
        SemanticResult: Result with ``FAIL`` status when scores are insufficient.
    """

    if result.status is not EvaluationStatus.PASS or not result.criteria:
        return result

    scores = tuple(criterion.score for criterion in result.criteria)

    if any(score is None for score in scores):
        return result.model_copy(update={"status": EvaluationStatus.FAIL})

    mean_score = sum(score for score in scores if score is not None) / len(scores)

    if mean_score < threshold:
        return result.model_copy(update={"status": EvaluationStatus.FAIL})

    return result


def _with_blocking_flag(
    result: SemanticResult,
    required: bool,
) -> SemanticResult:
    """Annotate semantic outcomes required by their language policy.

    Args:
        result: Semantic result produced for one artifact.
        required: Whether this artifact's semantic policy blocks aggregate pass.

    Returns:
        SemanticResult: Result annotated with the DTO's optional blocking flag.
        A compatibility guard keeps this facade usable while DTOs migrate.
    """

    if "blocks_aggregate" not in SemanticResult.model_fields:
        return result

    blocks_aggregate = required and result.status is not EvaluationStatus.PASS

    return result.model_copy(update={"blocks_aggregate": blocks_aggregate})


def _evaluate_artifact_semantic(
    request: FileEvaluationRequest,
    artifact: InMemoryFile,
    file_index: int,
    evaluator: EvaluatorSpec,
    policy: LanguageQualityPolicy,
    transport: SemanticTransport | None,
) -> SemanticResult:
    """Evaluate one artifact with policy retries and ordered model fallback.

    Args:
        request: Original request used for evaluator identity.
        artifact: Source artifact to evaluate.
        file_index: One-based artifact index used for criterion namespacing.
        evaluator: Evaluator profile supplying a stable result identity.
        policy: Exact language policy for this artifact.
        transport: Optional injected semantic model transport.

    Returns:
        SemanticResult: Explicit final semantic result, including errors.
    """
    evaluator_id = request.evaluator_id or evaluator.id
    requirements = _namespaced_requirements(policy.semantic_requirements, file_index)
    semantic_request = request.model_copy(
        update={
            "files": (artifact,),
            "requirements": requirements,
            "commands": (),
            "artifact_checks": (),
            "formatter_checks": (),
            "evaluator_id": evaluator_id,
        }
    )

    if not requirements:
        return _with_blocking_flag(
            SemanticResult(status=EvaluationStatus.PASS, evaluator_id=evaluator_id),
            policy.semantic_policy.required,
        )

    if transport is None:
        return _with_blocking_flag(
            SemanticResult(status=EvaluationStatus.BLOCKED, evaluator_id=evaluator_id),
            policy.semantic_policy.required,
        )

    semantic_policy = policy.semantic_policy
    enabled_models = tuple(model for model in semantic_policy.models if model.enabled)

    if not enabled_models:
        return _with_blocking_flag(
            SemanticResult(status=EvaluationStatus.BLOCKED, evaluator_id=evaluator_id),
            semantic_policy.required,
        )

    semantic_evaluator = SemanticEvaluator(transport)
    final_result: SemanticResult | None = None
    attempts = max(1, semantic_policy.retry.max_attempts)

    for model in enabled_models:
        for attempt in range(attempts):
            candidate = semantic_evaluator.evaluate(semantic_request, model)
            final_result = _threshold_result(candidate, policy.semantic_threshold)

            if final_result.status not in {
                EvaluationStatus.ERROR,
                EvaluationStatus.DISAGREE,
            }:
                return _with_blocking_flag(final_result, semantic_policy.required)

            if attempt < attempts - 1 and semantic_policy.retry.backoff_seconds > 0:
                time.sleep(semantic_policy.retry.backoff_seconds)

    if final_result is None:
        return _with_blocking_flag(
            SemanticResult(status=EvaluationStatus.ERROR, evaluator_id=evaluator_id),
            semantic_policy.required,
        )

    return _with_blocking_flag(final_result, semantic_policy.required)


def _combine_semantic_results(
    results: tuple[SemanticResult, ...],
    evaluator_id: str,
) -> SemanticResult | None:
    """Combine per-artifact semantic results in file and policy order.

    Args:
        results: Results produced for enabled artifact policies.
        evaluator_id: Stable evaluator profile identity.

    Returns:
        SemanticResult | None: Combined result, or ``None`` when none ran.
    """

    if not results:
        return None

    criteria: list[SemanticCriterionResult] = []

    for result in results:
        criteria.extend(result.criteria)

    combined = SemanticResult(
        status=_status(tuple(result.status for result in results)),
        evaluator_id=evaluator_id,
        criteria=tuple(criteria),
    )

    if "blocks_aggregate" not in SemanticResult.model_fields:
        return combined

    blocks_aggregate = any(
        bool(getattr(result, "blocks_aggregate", False)) for result in results
    )

    return combined.model_copy(update={"blocks_aggregate": blocks_aggregate})


def evaluate_code(
    request: FileEvaluationRequest,
    evaluator: EvaluatorSpec,
    semantic_transport: SemanticTransport | None = None,
) -> AggregateResult:
    """Evaluate immutable files while continuing every configured layer.

    Args:
        request: Immutable files, commands, and caller requirements.
        evaluator: Immutable profile with one policy per configured language.
        semantic_transport: Optional injected transport for enabled semantic policies.

    Returns:
        AggregateResult: Complete deterministic output and every enabled
        semantic result. Advisory semantic failures remain attached but do not
        affect aggregate status.
    """
    deterministic = _deterministic(request, evaluator)
    semantic_results: list[SemanticResult] = []
    required_semantic_statuses: list[EvaluationStatus] = []

    for file_index, artifact in enumerate(request.files, start=1):
        policy = _policy_for_artifact(evaluator, artifact)

        if policy is None or not policy.semantic_policy.enabled:
            continue

        semantic_result = _evaluate_artifact_semantic(
            request,
            artifact,
            file_index,
            evaluator,
            policy,
            semantic_transport,
        )
        semantic_results.append(semantic_result)

        if policy.semantic_policy.required:
            required_semantic_statuses.append(semantic_result.status)

    semantic = _combine_semantic_results(tuple(semantic_results), evaluator.id)
    aggregate_status = _status(
        (deterministic.status, *tuple(required_semantic_statuses))
    )

    return AggregateResult(
        status=aggregate_status,
        deterministic=deterministic,
        semantic=semantic,
        message="evaluation completed",
    )
