"""JSON analyzer implementing the shared fixed two-gate contract."""

from __future__ import annotations

from src.application.checks.shared.gate_ids import JSON_GATE_IDS
from src.application.checks.shared.protocol import BaseLanguageAnalyzer
from src.domain.models import (
    EvaluationStatus,
    Evidence,
    GateResult,
    InMemoryFile,
    Language,
    LanguageQualityPolicy,
)

from .parser import JsonParser, JsonParseResult


def _evidence(path: str, line: int, summary: str) -> Evidence:
    """Build source-bounded JSON evidence without retaining source values.

    Args:
        path: Relative artifact path used by the evidence DTO.
        line: One-based source line associated with the finding.
        summary: Redacted finding description.

    Returns:
        Evidence: Immutable source-bounded finding.
    """

    try:
        safe_path = Evidence(path=path, kind="json").path

    except (TypeError, ValueError):
        safe_path = "artifact.json"

    return Evidence(
        path=safe_path,
        line_start=max(1, line),
        line_end=max(1, line),
        kind="json",
        summary=summary,
    )


def _bounded(
    evidence: tuple[Evidence, ...], policy: LanguageQualityPolicy
) -> tuple[Evidence, ...]:
    """Apply the configured evidence cardinality policy.

    Args:
        evidence: Ordered evidence records for one gate.
        policy: Immutable occurrence policy controlling the bound.

    Returns:
        tuple[Evidence, ...]: Bounded evidence preserving source order.
    """
    limit = policy.occurrences.max_evidence_per_gate

    return evidence[:limit] if policy.occurrences.collect_all else evidence[:1]


class JsonAnalyzer(BaseLanguageAnalyzer):
    """Analyze JSON syntax and bounded object/array structure in memory."""

    language = Language.JSON
    gate_ids = JSON_GATE_IDS

    def __init__(self, parser: JsonParser | None = None) -> None:
        """Initialize the analyzer with an injectable bounded parser.

        Args:
            parser: Optional parser instance used for deterministic tests and limits.
        """
        self._parser = parser or JsonParser()

    def _analyze(
        self,
        artifact: InMemoryFile,
        policy: LanguageQualityPolicy,
    ) -> tuple[GateResult, ...]:
        """Analyze one JSON artifact and emit exactly two ordered gates.

        Args:
            artifact: Immutable in-memory JSON source artifact.
            policy: Immutable policy governing evidence cardinality.

        Returns:
            tuple[GateResult, ...]: Exact ``JSON_GATE_IDS`` sequence.
        """
        parsed = self._parser.parse(artifact.content)
        syntax_evidence = _syntax_evidence(artifact.path, parsed)
        syntax_status = (
            EvaluationStatus.PASS if parsed.syntax_valid else EvaluationStatus.FAIL
        )
        syntax_gate = GateResult(
            gate_id="JSON-SYNTAX",
            status=syntax_status,
            message="syntax valid" if parsed.syntax_valid else "syntax invalid",
            evidence=_bounded(syntax_evidence, policy),
        )

        if not parsed.syntax_valid:
            structure_gate = GateResult(
                gate_id="JSON-STRUCTURE",
                status=EvaluationStatus.BLOCKED,
                message="syntax-dependent gate blocked",
                evidence=_bounded(syntax_evidence, policy),
            )

        else:
            structure_evidence = _structure_evidence(artifact.path, parsed)
            structure_gate = GateResult(
                gate_id="JSON-STRUCTURE",
                status=(
                    EvaluationStatus.PASS
                    if parsed.structure_valid
                    else EvaluationStatus.FAIL
                ),
                message=(
                    "structure within bounds"
                    if parsed.structure_valid
                    else "structure violates JSON policy"
                ),
                evidence=_bounded(structure_evidence, policy),
            )

        return (syntax_gate, structure_gate)


def _syntax_evidence(path: str, parsed: JsonParseResult) -> tuple[Evidence, ...]:
    """Return a single syntax evidence record only for invalid JSON.

    Args:
        path: Relative artifact path used by evidence.
        parsed: Immutable JSON parse result.

    Returns:
        tuple[Evidence, ...]: Empty for valid JSON, otherwise one finding.
    """

    if parsed.syntax_valid:
        return ()

    return (_evidence(path, parsed.error_line or 1, "JSON syntax invalid"),)


def _structure_evidence(path: str, parsed: JsonParseResult) -> tuple[Evidence, ...]:
    """Return bounded structure findings without exposing duplicate key values.

    Args:
        path: Relative artifact path used by evidence.
        parsed: Immutable JSON parse result.

    Returns:
        tuple[Evidence, ...]: Redacted duplicate or bound findings.
    """
    findings: list[Evidence] = []

    if parsed.duplicate_keys:
        findings.append(_evidence(path, 1, "duplicate object keys detected"))

    if parsed.error_kind == "max_depth_exceeded":
        findings.append(_evidence(path, 1, "maximum JSON nesting depth exceeded"))

    if parsed.error_kind == "max_nodes_exceeded":
        findings.append(_evidence(path, 1, "maximum JSON structure size exceeded"))

    return tuple(findings)


__all__ = ["JsonAnalyzer"]
