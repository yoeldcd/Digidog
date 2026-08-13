"""Markdown analyzer implementing syntax, structure, and compactness gates."""

from __future__ import annotations

from src.application.checks.shared.gate_ids import MARKDOWN_GATE_IDS
from src.application.checks.shared.protocol import BaseLanguageAnalyzer
from src.domain.models import (
    EvaluationStatus,
    Evidence,
    GateResult,
    InMemoryFile,
    Language,
    LanguageQualityPolicy,
)

from .parser import MarkdownParser, MarkdownParseResult


def _evidence(path: str, line: int, summary: str) -> Evidence:
    """Build source-bounded Markdown evidence without retaining prose.

    Args:
        path: Relative artifact path used by the evidence DTO.
        line: One-based source line associated with the finding.
        summary: Redacted finding description.

    Returns:
        Evidence: Immutable source-bounded finding.
    """

    try:
        safe_path = Evidence(path=path, kind="markdown").path

    except (TypeError, ValueError):
        safe_path = "artifact.md"

    return Evidence(
        path=safe_path,
        line_start=max(1, line),
        line_end=max(1, line),
        kind="markdown",
        summary=summary,
    )


def _bounded(
    evidence: tuple[Evidence, ...], policy: LanguageQualityPolicy
) -> tuple[Evidence, ...]:
    """Apply occurrence policy while retaining source order.

    Args:
        evidence: Ordered evidence records for one gate.
        policy: Immutable occurrence policy controlling the bound.

    Returns:
        tuple[Evidence, ...]: Bounded evidence preserving source order.
    """
    limit = policy.occurrences.max_evidence_per_gate

    return evidence[:limit] if policy.occurrences.collect_all else evidence[:1]


class MarkdownAnalyzer(BaseLanguageAnalyzer):
    """Analyze Markdown syntax, configured block spacing, and compactness.

    Markdown compactness is intentionally structural: prose, inline markup, and
    code content are not treated as programming-language statements.
    """

    language = Language.MARKDOWN
    gate_ids = MARKDOWN_GATE_IDS

    def __init__(self, parser: MarkdownParser | None = None) -> None:
        """Initialize the analyzer with an injectable markdown-it parser.

        Args:
            parser: Optional parser instance used for deterministic tests.
        """
        self._parser = parser or MarkdownParser()

    def _analyze(
        self,
        artifact: InMemoryFile,
        policy: LanguageQualityPolicy,
    ) -> tuple[GateResult, ...]:
        """Analyze one Markdown artifact and emit exactly three ordered gates.

        Args:
            artifact: Immutable in-memory Markdown source artifact.
            policy: Immutable policy governing evidence cardinality.

        Returns:
            tuple[GateResult, ...]: Exact ``MARKDOWN_GATE_IDS`` sequence.
        """
        parsed = self._parser.parse(artifact.content)
        syntax_evidence = _syntax_evidence(artifact.path, parsed)
        syntax_gate = GateResult(
            gate_id=MARKDOWN_GATE_IDS[0],
            status=EvaluationStatus.PASS
            if parsed.syntax_valid
            else EvaluationStatus.FAIL,
            message="syntax valid" if parsed.syntax_valid else "syntax invalid",
            evidence=_bounded(syntax_evidence, policy),
        )

        if not parsed.syntax_valid:
            structure_gate = GateResult(
                gate_id=MARKDOWN_GATE_IDS[1],
                status=EvaluationStatus.BLOCKED,
                message="syntax-dependent gate blocked",
                evidence=_bounded(syntax_evidence, policy),
            )
            compactness_gate = GateResult(
                gate_id=MARKDOWN_GATE_IDS[2],
                status=EvaluationStatus.BLOCKED,
                message="syntax-dependent gate blocked",
                evidence=_bounded(syntax_evidence, policy),
            )

        else:
            structure_evidence = _layout_evidence(artifact.path, parsed, policy)
            structure_gate = GateResult(
                gate_id=MARKDOWN_GATE_IDS[1],
                status=(
                    EvaluationStatus.FAIL
                    if structure_evidence
                    else EvaluationStatus.PASS
                ),
                message=(
                    "Markdown block spacing valid"
                    if not structure_evidence
                    else "Markdown block spacing violates policy"
                ),
                evidence=_bounded(structure_evidence, policy),
            )
            compactness_evidence = _compactness_evidence(
                artifact.path, parsed, policy
            )
            compactness_gate = GateResult(
                gate_id=MARKDOWN_GATE_IDS[2],
                status=(
                    EvaluationStatus.FAIL
                    if compactness_evidence
                    else EvaluationStatus.PASS
                ),
                message=(
                    "Markdown compactness valid"
                    if not compactness_evidence
                    else "Markdown blocks are too compact"
                ),
                evidence=_bounded(compactness_evidence, policy),
            )

        return (syntax_gate, structure_gate, compactness_gate)


def _syntax_evidence(path: str, parsed: MarkdownParseResult) -> tuple[Evidence, ...]:
    """Return one evidence record per bounded unclosed fence finding.

    Args:
        path: Relative artifact path used by evidence.
        parsed: Immutable Markdown parse result.

    Returns:
        tuple[Evidence, ...]: Empty for valid syntax or fence findings otherwise.
    """

    if parsed.syntax_valid:
        return ()

    return tuple(
        _evidence(path, line, "unclosed Markdown fenced block")
        for line in parsed.unclosed_fence_lines
    ) or (_evidence(path, 1, "Markdown syntax invalid"),)


_LAYOUT_FACTS: tuple[tuple[str, str, str], ...] = (
    ("heading", "missing_blank_before_headings", "missing_blank_after_headings"),
    ("list", "missing_blank_before_lists", "missing_blank_after_lists"),
    ("table", "missing_blank_before_tables", "missing_blank_after_tables"),
    ("fence", "missing_blank_before_fences", "missing_blank_after_fences"),
    (
        "thematic_break",
        "missing_blank_before_thematic_breaks",
        "missing_blank_after_thematic_breaks",
    ),
)


def _layout_evidence(
    path: str,
    parsed: MarkdownParseResult,
    policy: LanguageQualityPolicy,
) -> tuple[Evidence, ...]:
    """Return evidence for configured blank lines around Markdown blocks.

    Args:
        path: Relative artifact path used by evidence.
        parsed: Immutable parser facts with source-bounded line numbers.
        policy: Immutable vertical-layout policy.

    Returns:
        tuple[Evidence, ...]: Ordered findings, or an empty tuple when disabled.
    """
    layout = policy.vertical_layout

    if not layout.enabled:
        return ()

    configured_before = {_normalize_kind(item) for item in layout.blank_before}
    configured_after = {_normalize_kind(item) for item in layout.blank_after}
    findings: list[Evidence] = []

    for kind, before_field, after_field in _LAYOUT_FACTS:
        normalized_kind = _normalize_kind(kind)
        before_lines = getattr(parsed, before_field)
        after_lines = getattr(parsed, after_field)

        if normalized_kind in configured_before:
            findings.extend(
                _evidence(path, line, f"blank line missing before {kind}")
                for line in before_lines
            )

        if normalized_kind in configured_after:
            findings.extend(
                _evidence(path, line, f"blank line missing after {kind}")
                for line in after_lines
            )

    return _sort_evidence(findings)


def _compactness_evidence(
    path: str,
    parsed: MarkdownParseResult,
    policy: LanguageQualityPolicy,
) -> tuple[Evidence, ...]:
    """Return structural anti-compactness findings without code-language rules.

    Args:
        path: Relative artifact path used by evidence.
        parsed: Immutable parser facts with source-bounded line numbers.
        policy: Immutable compactness policy.

    Returns:
        tuple[Evidence, ...]: Ordered block-separation findings.
    """

    if not policy.compactness.forbid_one_line_suites:
        return ()

    findings: list[Evidence] = []
    facts = (
        ("heading", parsed.missing_blank_before_headings, "before"),
        ("heading", parsed.missing_blank_after_headings, "after"),
        ("list", parsed.missing_blank_before_lists, "before"),
        ("table", parsed.missing_blank_before_tables, "before"),
        ("table", parsed.missing_blank_after_tables, "after"),
        ("fence", parsed.missing_blank_before_fences, "before"),
        ("fence", parsed.missing_blank_after_fences, "after"),
        (
            "thematic break",
            parsed.missing_blank_before_thematic_breaks,
            "before",
        ),
        (
            "thematic break",
            parsed.missing_blank_after_thematic_breaks,
            "after",
        ),
    )

    for kind, lines, direction in facts:
        findings.extend(
            _evidence(path, line, f"blank line missing {direction} {kind}")
            for line in lines
        )

    findings.extend(
        _evidence(path, current, "adjacent Markdown blocks require blank separation")
        for _, current in parsed.adjacent_block_lines
    )

    return _sort_evidence(findings)


def _normalize_kind(value: str) -> str:
    """Normalize configured layout token spelling to parser block kinds.

    Args:
        value: Configured layout token identifier.

    Returns:
        str: Canonical parser block-kind identifier.
    """

    normalized = value.strip().lower().replace("-", "_")

    if normalized in {"bullet_list", "ordered_list", "list_item"}:
        return "list"

    if normalized in {"hr", "thematic", "thematicbreak"}:
        return "thematic_break"

    return normalized


def _sort_evidence(findings: list[Evidence]) -> tuple[Evidence, ...]:
    """Return source-ordered immutable evidence with stable summary tie-breaks.

    Args:
        findings: Mutable local evidence collection to order.

    Returns:
        tuple[Evidence, ...]: Immutable source-ordered evidence records.
    """

    return tuple(
        sorted(findings, key=lambda item: (item.line_start or 0, item.summary))
    )


__all__ = ["MarkdownAnalyzer"]
