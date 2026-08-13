"""Project internal evaluator results into stable public presentation DTOs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, TypeAlias, runtime_checkable

from src.domain.models import (
    AggregateResult,
    EvaluationStatus,
    FileEvaluationRequest,
)

from .models import (
    CommandReport,
    ErrorReport,
    EvaluationReport,
    FileEvaluationReport,
    FileFormatReport,
    FindingReport,
    FormatReport,
    GateReport,
    SemanticCriterionReport,
    SemanticReport,
)

_MAX_TEXT_LENGTH = 500
_MAX_FINDINGS_PER_GATE = 50
_PASS = EvaluationStatus.PASS


class FormatterOutcome(Protocol):
    """Describe the formatter result consumed by the presentation boundary."""

    status: EvaluationStatus
    candidate: str | None
    command_result: object


class CommandOutcome(Protocol):
    """Describe command metadata required for public projection."""

    command_id: str
    status: EvaluationStatus
    exit_code: int | None
    evidence: tuple[object, ...]


class GateOutcome(Protocol):
    """Describe deterministic gate metadata required for public projection."""

    gate_id: str
    status: EvaluationStatus
    message: str
    evidence: tuple[object, ...]


class CriterionOutcome(Protocol):
    """Describe semantic criterion metadata required for public projection."""

    criterion_id: str
    status: EvaluationStatus
    score: float | None
    rationale: str
    evidence: tuple[object, ...]


@runtime_checkable
class EvidenceOutcome(Protocol):
    """Describe source evidence without exposing digest fields."""

    path: str
    line_start: int | None
    line_end: int | None
    kind: str
    summary: str


class DeterministicOutcome(Protocol):
    """Describe aggregate deterministic output."""

    status: EvaluationStatus
    gates: tuple[GateOutcome, ...]
    commands: tuple[CommandOutcome, ...]


class SemanticOutcome(Protocol):
    """Describe aggregate semantic output."""

    status: EvaluationStatus
    evaluator_id: str
    blocks_aggregate: bool
    criteria: tuple[CriterionOutcome, ...]


def _bounded_text(value: str, fallback: str) -> str:
    """Normalize one user-facing message and cap its size.

    Args:
        value: Candidate text from a trusted evaluator DTO.
        fallback: Text used when the candidate is empty.

    Returns:
        str: Single-line bounded text suitable for JSON and Markdown.
    """

    normalized = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    selected = normalized or fallback

    if len(selected) <= _MAX_TEXT_LENGTH:
        return selected

    return f"{selected[: _MAX_TEXT_LENGTH - 1].rstrip()}…"


def _evidence_report(
    evidence: object,
    *,
    fallback_path: str,
    fallback_kind: str,
    fallback_summary: str,
) -> FindingReport:
    """Convert evidence into a source-bounded public finding.

    Args:
        evidence: Internal evidence object with the documented evidence protocol.
        fallback_path: File path used when evidence does not expose one.
        fallback_kind: Stable kind used when evidence does not expose one.
        fallback_summary: Gate or criterion message used when evidence is empty.

    Returns:
        FindingReport: Immutable finding without digest or raw output fields.
    """

    candidate = evidence if isinstance(evidence, EvidenceOutcome) else None

    if candidate is None:
        return FindingReport(
            path=fallback_path,
            kind=fallback_kind,
            summary=_bounded_text(fallback_summary, "quality requirement failed"),
        )

    return FindingReport(
        path=candidate.path,
        line_start=candidate.line_start,
        line_end=candidate.line_end,
        kind=_bounded_text(candidate.kind, fallback_kind),
        summary=_bounded_text(candidate.summary, fallback_summary),
    )


def _findings(
    evidence: Sequence[object],
    *,
    fallback_path: str,
    fallback_kind: str,
    fallback_summary: str,
) -> tuple[FindingReport, ...]:
    """Project bounded evidence in source order.

    Args:
        evidence: Internal evidence records in deterministic order.
        fallback_path: File path used when no evidence was recorded.
        fallback_kind: Stable category used for a fallback finding.
        fallback_summary: Gate or criterion message used for a fallback finding.

    Returns:
        tuple[FindingReport, ...]: At most the configured bounded finding count.
    """

    if not evidence:
        return ()

    projected = tuple(
        _evidence_report(
            item,
            fallback_path=fallback_path,
            fallback_kind=fallback_kind,
            fallback_summary=fallback_summary,
        )
        for item in evidence[:_MAX_FINDINGS_PER_GATE]
    )
    grouped: dict[tuple[object, ...], FindingReport] = {}

    for finding in projected:
        key = (
            finding.path,
            finding.line_start,
            finding.line_end,
            finding.kind,
            finding.summary,
        )
        current = grouped.get(key)

        if current is None:
            grouped[key] = finding

            continue

        grouped[key] = current.model_copy(
            update={"occurrences": current.occurrences + 1}
        )

    return tuple(grouped.values())


def _gate_file_index(gate_id: str, file_count: int) -> int | None:
    """Return a one-based file index encoded in a gate identifier.

    Args:
        gate_id: Deterministic gate identifier.
        file_count: Number of requested files.

    Returns:
        int | None: Valid one-based file index, or ``None`` for an unowned gate.
    """

    parts = gate_id.split("-", 2)

    if len(parts) < 3 or parts[0] != "file":
        return None

    try:
        file_index = int(parts[1])

    except ValueError:
        return None

    return file_index if 1 <= file_index <= file_count else None


def _gate_report(gate: GateOutcome, fallback_path: str) -> GateReport:
    """Project one non-passing deterministic gate.

    Args:
        gate: Internal deterministic gate result.
        fallback_path: Requested file path used when evidence is absent.

    Returns:
        GateReport: Public gate message and source-bounded findings.
    """

    findings = _findings(
        gate.evidence,
        fallback_path=fallback_path,
        fallback_kind="gate",
        fallback_summary=gate.message,
    )

    return GateReport(
        gate_id=gate.gate_id,
        status=gate.status,
        message=_bounded_text(gate.message, "quality requirement failed"),
        findings=findings,
    )


def _file_status(gates: Sequence[GateOutcome]) -> EvaluationStatus:
    """Return the worst status among all gates owned by one file.

    Args:
        gates: Internal gates associated with one requested file.

    Returns:
        EvaluationStatus: Highest-severity status, or ``PASS`` for no gates.
    """

    precedence = {
        EvaluationStatus.PASS: 0,
        EvaluationStatus.FAIL: 1,
        EvaluationStatus.DISAGREE: 1,
        EvaluationStatus.BLOCKED: 2,
        EvaluationStatus.ERROR: 3,
    }

    if not gates:
        return _PASS

    return max(gates, key=lambda gate: precedence[gate.status]).status


def _project_semantic(result: SemanticOutcome | None) -> SemanticReport | None:
    """Project semantic criteria while retaining only actionable outcomes.

    Args:
        result: Internal semantic result, or ``None`` when semantic evaluation did
            not run.

    Returns:
        SemanticReport | None: Source-redacted semantic projection when available.
    """

    if result is None:
        return None

    criteria: list[SemanticCriterionReport] = []

    for criterion in result.criteria:
        findings = _findings(
            criterion.evidence,
            fallback_path="<semantic>",
            fallback_kind="semantic",
            fallback_summary=criterion.rationale,
        )
        criteria.append(
            SemanticCriterionReport(
                criterion_id=criterion.criterion_id,
                status=criterion.status,
                score=criterion.score,
                rationale=_bounded_text(criterion.rationale, "semantic criterion failed"),
                findings=findings,
            )
        )

    return SemanticReport(
        status=result.status,
        evaluator_id=result.evaluator_id,
        blocks_aggregate=result.blocks_aggregate,
        criteria=tuple(criteria),
    )


def project_evaluation(
    request: FileEvaluationRequest,
    aggregate: AggregateResult,
    mode: Literal["check", "evaluate"],
) -> EvaluationReport:
    """Project a request and aggregate result into one public report.

    Args:
        request: Immutable source request in caller order.
        aggregate: Complete internal deterministic and semantic result.
        mode: Public operation name, either ``check`` or ``evaluate``.

    Returns:
        EvaluationReport: Immutable JSON/Markdown source-redacted report.
    """

    deterministic = aggregate.deterministic
    gates_by_file: dict[int, list[GateOutcome]] = {
        index: [] for index in range(1, len(request.files) + 1)
    }
    unowned_gates: list[GateOutcome] = []

    for gate in deterministic.gates:
        file_index = _gate_file_index(gate.gate_id, len(request.files))

        if file_index is None:
            unowned_gates.append(gate)
            continue

        gates_by_file[file_index].append(gate)

    files: list[FileEvaluationReport] = []

    for file_index, source_file in enumerate(request.files, start=1):
        owned_gates = gates_by_file[file_index]
        reports = tuple(
            _gate_report(gate, source_file.path)
            for gate in owned_gates
            if gate.status is not _PASS
        )
        files.append(
            FileEvaluationReport(
                path=source_file.path,
                language=source_file.language,
                status=_file_status(owned_gates),
                gates=reports,
            )
        )

    if unowned_gates:
        # Commands are represented separately; an unowned gate is retained in the
        # first file to avoid dropping an actionable deterministic result.
        first_file = files[0]
        extra_reports = tuple(
            _gate_report(gate, first_file.path)
            for gate in unowned_gates
            if gate.status is not _PASS
        )
        files[0] = first_file.model_copy(
            update={"gates": (*first_file.gates, *extra_reports)}
        )

    commands = tuple(
        CommandReport(
            command_id=command.command_id,
            status=command.status,
            exit_code=command.exit_code,
            message=_bounded_text(
                next(
                    (
                        evidence.summary
                        for evidence in command.evidence
                        if isinstance(evidence, EvidenceOutcome)
                        and evidence.summary
                    ),
                    command.status.value,
                ),
                command.status.value,
            ),
        )
        for command in deterministic.commands
        if command.status is not _PASS
    )
    semantic = _project_semantic(aggregate.semantic)
    summary = _evaluation_summary(aggregate, files, commands, semantic)

    return EvaluationReport(
        mode=mode,
        status=aggregate.status,
        summary=summary,
        files=tuple(files),
        commands=commands,
        semantic=semantic,
    )


def _evaluation_summary(
    aggregate: AggregateResult,
    files: Sequence[FileEvaluationReport],
    commands: Sequence[CommandReport],
    semantic: SemanticReport | None,
) -> str:
    """Build a bounded status summary from projected actionable counts.

    Args:
        aggregate: Internal aggregate result supplying overall status.
        files: Projected per-file reports.
        commands: Projected non-passing command reports.
        semantic: Projected semantic report, when present.

    Returns:
        str: Concise bounded status summary.
    """

    if aggregate.status is _PASS:
        return "All requested files passed quality checks."

    gate_count = sum(len(item.gates) for item in files)
    criterion_count = len(semantic.criteria) if semantic is not None else 0
    details: list[str] = []

    if gate_count:
        details.append(
            f"{gate_count} gate" + ("s" if gate_count != 1 else "")
        )

    if commands:
        details.append(
            f"{len(commands)} command" + ("s" if len(commands) != 1 else "")
        )

    if criterion_count:
        details.append(
            f"{criterion_count} semantic result"
            + ("s" if criterion_count != 1 else "")
        )

    detail_text = ", ".join(details) or "no actionable details"
    status_phrase = {
        EvaluationStatus.FAIL: "failed",
        EvaluationStatus.DISAGREE: "disagreed",
        EvaluationStatus.BLOCKED: "was blocked",
        EvaluationStatus.ERROR: "encountered an error",
    }.get(aggregate.status, aggregate.status.value)

    return _bounded_text(
        f"Quality evaluation {status_phrase}: {detail_text}.",
        "quality evaluation did not pass",
    )


def project_format(
    request: FileEvaluationRequest,
    outcomes: Sequence[FormatterOutcome | None],
) -> FormatReport:
    """Project formatter candidates and blockers without command metadata.

    Args:
        request: Immutable source request in caller order.
        outcomes: Formatter results aligned with ``request.files``; ``None`` means
            no formatter policy was configured for that file.

    Returns:
        FormatReport: Immutable formatter result without digests or raw command output.
    """

    files: list[FileFormatReport] = []
    statuses: list[EvaluationStatus] = []

    for index, source_file in enumerate(request.files):
        outcome = outcomes[index] if index < len(outcomes) else None

        if outcome is None:
            status = EvaluationStatus.BLOCKED
            message = "formatter is unavailable for this language"
            candidate = None

        else:
            status = outcome.status
            candidate = outcome.candidate
            message = (
                "formatted candidate available"
                if status is _PASS
                else "formatter did not produce a candidate"
            )

        statuses.append(status)
        files.append(
            FileFormatReport(
                path=source_file.path,
                language=source_file.language,
                status=status,
                message=message,
                content=candidate,
            )
        )

    aggregate_status = max(
        statuses,
        key=lambda status: {
            EvaluationStatus.PASS: 0,
            EvaluationStatus.FAIL: 1,
            EvaluationStatus.DISAGREE: 1,
            EvaluationStatus.BLOCKED: 2,
            EvaluationStatus.ERROR: 3,
        }[status],
        default=_PASS,
    )

    summary = (
        "Formatted candidates are available."
        if aggregate_status is _PASS
        else "One or more files could not be formatted."
    )

    return FormatReport(
        status=aggregate_status,
        summary=summary,
        files=tuple(files),
    )


Report: TypeAlias = EvaluationReport | FormatReport | ErrorReport


def public_payload(report: Report) -> dict[str, object]:
    """Serialize one public report using its authoritative DTO schema.

    Args:
        report: Immutable report produced by a projection function.

    Returns:
        dict[str, object]: JSON-compatible mapping with default noise omitted.
    """

    payload = dict(report.model_dump(mode="json", exclude_defaults=True))

    if isinstance(report, FormatReport):
        payload["mode"] = report.mode

    return payload


project_evaluation_report = project_evaluation
project_format_report = project_format
