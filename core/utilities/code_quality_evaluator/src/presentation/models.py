"""Immutable public result schemas shared by JSON and Markdown renderers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain.models import EvaluationStatus, Language


class PresentationDTO(BaseModel):
    """Provide strict immutable behavior for public presentation objects."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FindingReport(PresentationDTO):
    """Describe one actionable source finding without internal evidence data.

    Attributes:
        path: Workspace-relative artifact path.
        line_start: Optional first relevant source line.
        line_end: Optional final relevant source line.
        kind: Stable finding classification.
        summary: Bounded human-readable explanation.
        occurrences: Number of equivalent findings represented by this row.
    """

    path: str
    line_start: int | None = Field(None, ge=1)
    line_end: int | None = Field(None, ge=1)
    kind: str
    summary: str
    occurrences: int = Field(1, ge=1)


class GateReport(PresentationDTO):
    """Describe one non-passing deterministic gate.

    Attributes:
        gate_id: Stable public gate identifier.
        status: Non-passing gate status.
        message: Human-readable gate outcome.
        findings: Actionable source findings in stable order.
    """

    gate_id: str
    status: EvaluationStatus
    message: str
    findings: tuple[FindingReport, ...] = ()


class FileEvaluationReport(PresentationDTO):
    """Group deterministic findings for one requested source file.

    Attributes:
        path: Workspace-relative requested path.
        language: Language selected for the artifact.
        status: Worst deterministic status for this file.
        gates: Non-passing gates owned by this file.
    """

    path: str
    language: Language
    status: EvaluationStatus
    gates: tuple[GateReport, ...] = ()


class CommandReport(PresentationDTO):
    """Describe one non-passing configured command without captured output.

    Attributes:
        command_id: Stable configured command identifier.
        status: Command result status.
        exit_code: Process exit code when execution started.
        message: Bounded explanation suitable for a user.
    """

    command_id: str
    status: EvaluationStatus
    exit_code: int | None = None
    message: str


class SemanticCriterionReport(PresentationDTO):
    """Describe one semantic criterion result.

    Attributes:
        criterion_id: Stable configured criterion identifier.
        status: Criterion outcome.
        score: Optional normalized score.
        rationale: Bounded provider rationale.
        findings: Source-bounded findings supporting the result.
    """

    criterion_id: str
    status: EvaluationStatus
    score: float | None = Field(None, ge=0, le=1)
    rationale: str
    findings: tuple[FindingReport, ...] = ()


class SemanticReport(PresentationDTO):
    """Describe the semantic layer without provider transport internals.

    Attributes:
        status: Semantic layer outcome.
        evaluator_id: Stable evaluator profile identifier.
        blocks_aggregate: Whether this layer prevents aggregate PASS.
        criteria: Criterion results in configured order.
    """

    status: EvaluationStatus
    evaluator_id: str
    blocks_aggregate: bool
    criteria: tuple[SemanticCriterionReport, ...] = ()


class EvaluationReport(PresentationDTO):
    """Represent the public result of check or semantic evaluation.

    Attributes:
        mode: Evaluation operation that produced the report.
        status: Aggregate result status.
        summary: Concise descriptive aggregate explanation.
        files: Requested files in input order.
        commands: Non-passing configured command results.
        semantic: Semantic result for evaluate mode, when enabled.
    """

    mode: Literal["check", "evaluate"]
    status: EvaluationStatus
    summary: str
    files: tuple[FileEvaluationReport, ...]
    commands: tuple[CommandReport, ...] = ()
    semantic: SemanticReport | None = None


class FileFormatReport(PresentationDTO):
    """Describe one in-memory formatting result.

    Attributes:
        path: Workspace-relative requested path.
        language: Language selected for the artifact.
        status: Formatter result status.
        message: Descriptive outcome or blocker.
        content: Formatted candidate when formatting succeeded.
    """

    path: str
    language: Language
    status: EvaluationStatus
    message: str
    content: str | None = None


class FormatReport(PresentationDTO):
    """Represent the public result of in-memory formatting.

    Attributes:
        mode: Constant format operation name.
        status: Worst formatter status across requested files.
        summary: Concise descriptive aggregate explanation.
        files: Per-file formatter results in input order.
    """

    mode: Literal["format"] = "format"
    status: EvaluationStatus
    summary: str
    files: tuple[FileFormatReport, ...]


class ErrorReport(PresentationDTO):
    """Represent a descriptive public failure before a normal result exists.

    Attributes:
        mode: Requested operation when it could be identified.
        status: Stable blocked or error classification.
        summary: Source-redacted explanation and next-action context.
    """

    mode: Literal["check", "evaluate", "format", "schema"]
    status: Literal[EvaluationStatus.BLOCKED, EvaluationStatus.ERROR]
    summary: str
