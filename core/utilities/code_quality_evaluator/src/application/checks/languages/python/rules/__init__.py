"""Composable Python static-quality rules and fixed gate orchestration."""

from __future__ import annotations

from src.domain.models import GateResult, LanguageQualityPolicy

from ..parser import ParseResult
from .annotations import annotation_evidence
from .compactness import compactness_evidence
from .documentation import documentation_evidence
from .evidence import gate
from .imports import any_evidence, import_evidence
from .layout import layout_evidence


def evaluate_rules(
    content: str,
    parsed: ParseResult,
    policy: LanguageQualityPolicy | None = None,
    path: str = "artifact.py",
) -> tuple[GateResult, ...]:
    """Evaluate seven Python gates using an already-parsed source result.

    Args:
        content: Complete Python source text held in memory.
        parsed: Parse result produced by :func:`parse_python`.
        policy: Optional immutable language quality policy.
        path: Relative source path used for redacted evidence.

    Returns:
        tuple[GateResult, ...]: Python gates in stable declaration order. The parser
            owns all parsing; this function never calls ``ast.parse``.

    Raises:
        ValueError: If the supplied parse result does not contain a module.
    """

    if parsed.module is None:
        raise ValueError("rules require a successful parse")

    annotation_findings = annotation_evidence(parsed.module, path)
    documentation_findings = documentation_evidence(parsed.module, policy, path)
    import_findings = import_evidence(parsed.module, path)
    any_findings = any_evidence(parsed.module, path)
    layout_findings = layout_evidence(parsed, policy, path)
    compactness_findings = compactness_evidence(parsed, policy, path)

    return (
        gate("PY-SYNTAX", (), "syntax valid", policy),
        gate("PY-ANNOTATIONS", annotation_findings, "annotations complete", policy),
        gate(
            "PY-DOCSTRINGS",
            documentation_findings,
            "documentation complete",
            policy,
        ),
        gate("PY-IMPORTS", import_findings, "imports valid", policy),
        gate("PY-NO-ANY", any_findings, "Any absent", policy),
        gate("PY-VERTICAL-LAYOUT", layout_findings, "vertical layout valid", policy),
        gate("PY-COMPACTNESS", compactness_findings, "compactness valid", policy),
    )


__all__ = ["evaluate_rules"]
