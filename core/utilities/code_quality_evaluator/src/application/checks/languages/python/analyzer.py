"""Python language analyzer implementing the shared fixed-gate contract."""

from __future__ import annotations

from src.application.checks.shared.gate_ids import PYTHON_GATE_IDS
from src.application.checks.shared.protocol import BaseLanguageAnalyzer
from src.domain.models import (
    EvaluationStatus,
    Evidence,
    GateResult,
    InMemoryFile,
    Language,
    LanguageQualityPolicy,
)

from .parser import parse_python
from .rules import evaluate_rules


def _blocked_gates(
    syntax_evidence: tuple[Evidence, ...],
) -> tuple[GateResult, ...]:
    """Build the exact seven-gate sequence for a syntax failure.

    Args:
        syntax_evidence: Redacted syntax evidence shared by every dependent gate.

    Returns:
        tuple[GateResult, ...]: Syntax failure followed by six blocked gates.
    """

    gates: list[GateResult] = []

    for gate_id in PYTHON_GATE_IDS:
        if gate_id == "PY-SYNTAX":
            gates.append(
                GateResult(
                    gate_id=gate_id,
                    status=EvaluationStatus.FAIL,
                    message="syntax invalid",
                    evidence=syntax_evidence,
                )
            )

        else:
            gates.append(
                GateResult(
                    gate_id=gate_id,
                    status=EvaluationStatus.BLOCKED,
                    message="syntax-dependent gate blocked",
                    evidence=syntax_evidence,
                )
            )

    return tuple(gates)


class PythonAnalyzer(BaseLanguageAnalyzer):
    """Analyze in-memory Python artifacts against the fixed seven-gate contract.

    Attributes:
        language: Language served by this analyzer.
        gate_ids: Exact gate declaration and order required by the dispatcher.
    """

    language = Language.PYTHON
    gate_ids = PYTHON_GATE_IDS

    def _analyze(
        self,
        artifact: InMemoryFile,
        policy: LanguageQualityPolicy,
    ) -> tuple[GateResult, ...]:
        """Run Python-specific gates for one validated source artifact.

        Args:
            artifact: Immutable in-memory Python source artifact.
            policy: Immutable policy governing documentation, layout, compactness,
                and evidence cardinality.

        Returns:
            tuple[GateResult, ...]: Exact Python gate sequence in declaration order.
        """

        return evaluate_python(artifact.content, policy=policy, path=artifact.path)


def evaluate_python(
    content: str,
    policy: LanguageQualityPolicy | None = None,
    path: str = "artifact.py",
) -> tuple[GateResult, ...]:
    """Evaluate Python source and return the legacy seven-gate tuple.

    Args:
        content: Complete Python source text held in memory.
        policy: Optional immutable language quality policy.
        path: Relative source path used in redacted evidence.

    Returns:
        tuple[GateResult, ...]: Exactly seven gates in :data:`PYTHON_GATE_IDS` order.
    """

    parsed = parse_python(content, path=path)

    if parsed.module is None:
        return _blocked_gates(parsed.syntax_evidence)

    return evaluate_rules(content, parsed, policy=policy, path=path)


__all__ = ["PythonAnalyzer", "evaluate_python"]
