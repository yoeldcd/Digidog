"""Shared redacted evidence and gate construction helpers for Python rules."""

from __future__ import annotations

from src.domain.models import (
    EvaluationStatus,
    Evidence,
    GateResult,
    LanguageQualityPolicy,
)


def safe_path(path: str) -> str:
    """Return a DTO-safe path without reading from disk.

    Args:
        path: Candidate source path.

    Returns:
        str: Candidate path or fixed redacted fallback.
    """

    try:
        Evidence(path=path, kind="python")

    except (TypeError, ValueError):
        return "artifact.py"

    return path


def evidence(path: str, line: int, summary: str) -> Evidence:
    """Build one immutable, redacted source evidence record.

    Args:
        path: Relative source path.
        line: One-based source line.
        summary: Redacted finding description.

    Returns:
        Evidence: Immutable source evidence.
    """

    return Evidence(
        path=safe_path(path),
        line_start=max(1, line),
        line_end=max(1, line),
        kind="python",
        summary=summary,
    )


def bounded(
    findings: tuple[Evidence, ...],
    policy: LanguageQualityPolicy | None,
) -> tuple[Evidence, ...]:
    """Apply configured occurrence limits while preserving source order.

    Args:
        findings: Ordered evidence records for one gate.
        policy: Optional policy containing occurrence settings.

    Returns:
        tuple[Evidence, ...]: Bounded immutable evidence.
    """

    if policy is None:
        return findings

    limit = policy.occurrences.max_evidence_per_gate

    if policy.occurrences.collect_all:
        return findings[:limit]

    return findings[:1]


def gate(
    gate_id: str,
    findings: tuple[Evidence, ...],
    message: str,
    policy: LanguageQualityPolicy | None,
) -> GateResult:
    """Build one immutable pass/fail gate with bounded evidence.

    Args:
        gate_id: Stable gate identifier.
        findings: Ordered evidence records for the gate.
        message: Human-readable gate description.
        policy: Optional occurrence policy.

    Returns:
        GateResult: Immutable pass/fail gate result.
    """

    bounded_findings = bounded(findings, policy)
    status = EvaluationStatus.FAIL if bounded_findings else EvaluationStatus.PASS

    return GateResult(
        gate_id=gate_id,
        status=status,
        message=message,
        evidence=bounded_findings,
    )


__all__ = ["bounded", "evidence", "gate", "safe_path"]
