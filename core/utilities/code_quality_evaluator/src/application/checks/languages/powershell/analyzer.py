"""PowerShell analyzer implementing the shared fixed four-gate contract."""

from __future__ import annotations

from collections import Counter
import re

from src.application.checks.shared.gate_ids import POWERSHELL_GATE_IDS
from src.application.checks.shared.protocol import BaseLanguageAnalyzer
from src.domain.models import (
    EvaluationStatus,
    Evidence,
    GateResult,
    InMemoryFile,
    Language,
    LanguageQualityPolicy,
)

from .parser import PowerShellParser, PowerShellParseResult


def _evidence(path: str, line: int, summary: str) -> Evidence:
    """Build source-bounded PowerShell evidence without retaining source text.

    Args:
        path: Relative artifact path used by the evidence DTO.
        line: One-based source line associated with the finding.
        summary: Redacted finding description.

    Returns:
        Evidence: Immutable source-bounded finding.
    """

    try:
        safe_path = Evidence(path=path, kind="powershell").path

    except (TypeError, ValueError):
        safe_path = "artifact.ps1"

    return Evidence(
        path=safe_path,
        line_start=max(1, line),
        line_end=max(1, line),
        kind="powershell",
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


def _help_sections(source: str, line: int) -> tuple[str, ...]:
    """Return comment-based help section names immediately preceding a declaration.

    Args:
        source: Complete PowerShell source text held in memory.
        line: One-based declaration line.

    Returns:
        tuple[str, ...]: Ordered lower-case help section names.
    """

    lines = source.splitlines()
    start = max(0, line - 13)
    prefix = "\n".join(lines[start : max(0, line - 1)])
    names = re.findall(
        r"\.\s*(SYNOPSIS|DESCRIPTION|PARAMETER|INPUTS|OUTPUTS|EXAMPLE|EXCEPTION|ERRORS|NOTES|LINK)\b",
        prefix,
        flags=re.IGNORECASE,
    )

    return tuple(dict.fromkeys(item.lower() for item in names))


def _help_present(source: str, line: int) -> bool:
    """Return whether a declaration has a nearby comment-help marker.

    Args:
        source: Complete PowerShell source text held in memory.
        line: One-based declaration line.

    Returns:
        bool: Whether a comment-based help block precedes the declaration.
    """

    lines = source.splitlines()
    prefix = "\n".join(lines[max(0, line - 13) : max(0, line - 1)])

    return bool(
        re.search(r"(?:^|\n)\s*#\.", prefix, flags=re.IGNORECASE)
        or re.search(r"(?:^|\n)\s*<#", prefix, flags=re.IGNORECASE)
    )


def _declaration_name(source: str, line: int, kind: str) -> str:
    """Extract a declaration name from a PowerShell source line.

    Args:
        source: Complete PowerShell source text held in memory.
        line: One-based declaration line.
        kind: Parser declaration family identifier.

    Returns:
        str: Declaration name, or an empty value when unavailable.
    """

    lines = source.splitlines()
    text = lines[line - 1] if 1 <= line <= len(lines) else ""

    if "function" in kind.lower():
        match = re.search(r"\bfunction\s+(?:global:|script:|private:)?(?P<name>[\w-]+)", text, re.IGNORECASE)

        return match.group("name") if match else ""

    if "type" in kind.lower() or "class" in kind.lower():
        match = re.search(r"\bclass\s+(?P<name>[\w-]+)", text, re.IGNORECASE)

        return match.group("name") if match else ""

    return ""


def _brace_depth(source: str, line: int) -> int:
    """Return a conservative brace depth before a PowerShell declaration.

    Args:
        source: Complete PowerShell source text held in memory.
        line: One-based declaration line.

    Returns:
        int: Non-negative brace depth before the declaration.
    """

    lines = source.splitlines()
    depth = 0

    for value in lines[: max(0, line - 1)]:
        depth += value.count("{") - value.count("}")

    return max(0, depth)


def _constructor_lines(source: str, class_lines: tuple[int, ...]) -> tuple[int, ...]:
    """Find class constructor signatures represented only in source text.

    Args:
        source: Complete PowerShell source text held in memory.
        class_lines: One-based class declaration lines from the parser summary.

    Returns:
        tuple[int, ...]: One-based constructor signature lines.
    """

    lines = source.splitlines()
    result: list[int] = []

    for class_line in class_lines:
        class_text = lines[class_line - 1] if 1 <= class_line <= len(lines) else ""
        match = re.search(r"\bclass\s+(?P<name>[\w-]+)", class_text, re.IGNORECASE)

        if match is None:
            continue

        class_name = re.escape(match.group("name"))
        depth = _brace_depth(source, class_line) + 1

        for offset, value in enumerate(lines[class_line:], start=class_line + 1):
            depth += value.count("{") - value.count("}")

            if depth <= 0:
                break

            if re.search(rf"^\s*{class_name}\s*\(", value):
                result.append(offset)

    return tuple(result)


class PowerShellAnalyzer(BaseLanguageAnalyzer):
    """Analyze PowerShell syntax, comment help, native layout, and compactness."""

    language = Language.POWERSHELL
    gate_ids = POWERSHELL_GATE_IDS

    def __init__(self, parser: PowerShellParser | None = None) -> None:
        """Initialize the analyzer with an injectable Parser.ParseInput adapter.

        Args:
            parser: Optional parser instance used for deterministic tests.
        """
        self._parser = parser or PowerShellParser()

    def _analyze(
        self,
        artifact: InMemoryFile,
        policy: LanguageQualityPolicy,
    ) -> tuple[GateResult, ...]:
        """Analyze one PowerShell artifact and emit exactly four ordered gates.

        Args:
            artifact: Immutable in-memory PowerShell source artifact.
            policy: Immutable policy governing documentation, layout, compactness,
                and evidence cardinality.

        Returns:
            tuple[GateResult, ...]: Exact ``POWERSHELL_GATE_IDS`` sequence.
        """
        parsed = self._parser.parse(artifact.content)
        syntax_evidence = _syntax_evidence(artifact.path, parsed)

        if not parsed.available:
            gates = _blocked_gates(
                syntax_evidence, "PowerShell parser unavailable", policy
            )

        elif not parsed.syntax_valid:
            gates = _blocked_gates(
                syntax_evidence, "syntax-dependent gate blocked", policy
            )
            gates = (
                GateResult(
                    gate_id="PS-SYNTAX",
                    status=EvaluationStatus.FAIL,
                    message="syntax invalid",
                    evidence=_bounded(syntax_evidence, policy),
                ),
                *gates[1:],
            )

        else:
            gates = self._valid_gates(artifact.path, parsed, policy, artifact.content)

        return gates

    def _valid_gates(
        self,
        path: str,
        parsed: PowerShellParseResult,
        policy: LanguageQualityPolicy,
        source: str,
    ) -> tuple[GateResult, ...]:
        """Evaluate non-syntax PowerShell gates after ParseInput succeeds.

        Args:
            path: Relative artifact path used by evidence.
            parsed: Immutable PowerShell parse result.
            policy: Immutable documentation, layout, and compactness policy.
            source: Complete PowerShell source text held in memory.

        Returns:
            tuple[GateResult, ...]: Syntax and dependent gates in fixed order.
        """
        summary = parsed.summary

        if summary is None:
            return _blocked_gates((), "PowerShell parser unavailable", policy)

        documentation_findings = _documentation_findings(path, summary, policy, source)
        layout_findings = _layout_findings(path, summary, policy, parsed.lines)
        compactness_findings = _compactness_findings(path, summary, policy)

        return (
            GateResult(
                gate_id="PS-SYNTAX",
                status=EvaluationStatus.PASS,
                message="syntax valid",
                evidence=(),
            ),
            _gate(
                "PS-DOCUMENTATION",
                documentation_findings,
                "comment-based help complete",
                policy,
            ),
            _gate(
                "PS-VERTICAL-LAYOUT",
                layout_findings,
                "native clause layout valid",
                policy,
            ),
            _gate(
                "PS-COMPACTNESS",
                compactness_findings,
                "statement compactness valid",
                policy,
            ),
        )


def _blocked_gates(
    evidence: tuple[Evidence, ...],
    message: str,
    policy: LanguageQualityPolicy,
) -> tuple[GateResult, ...]:
    """Build exact syntax-failure or unavailable dependent gates.

    Args:
        evidence: Redacted parser evidence shared by dependent gates.
        message: Bounded gate explanation.
        policy: Immutable occurrence policy controlling evidence limits.

    Returns:
        tuple[GateResult, ...]: Four blocked gates in fixed declaration order.
    """
    bounded = _bounded(evidence, policy)

    return tuple(
        GateResult(
            gate_id=gate_id,
            status=EvaluationStatus.BLOCKED,
            message=message,
            evidence=bounded,
        )
        for gate_id in POWERSHELL_GATE_IDS
    )


def _gate(
    gate_id: str,
    evidence: tuple[Evidence, ...],
    message: str,
    policy: LanguageQualityPolicy,
) -> GateResult:
    """Build one pass/fail gate with bounded evidence.

    Args:
        gate_id: Stable PowerShell gate identifier.
        evidence: Ordered findings for the gate.
        message: Redacted gate explanation.
        policy: Immutable occurrence policy controlling evidence limits.

    Returns:
        GateResult: Immutable pass/fail gate.
    """
    bounded = _bounded(evidence, policy)

    return GateResult(
        gate_id=gate_id,
        status=EvaluationStatus.FAIL if bounded else EvaluationStatus.PASS,
        message=message if not bounded else f"{message}; findings detected",
        evidence=bounded,
    )


def _syntax_evidence(path: str, parsed: PowerShellParseResult) -> tuple[Evidence, ...]:
    """Return one evidence record for each parser syntax coordinate.

    Args:
        path: Relative artifact path used by evidence.
        parsed: Immutable PowerShell parse result.

    Returns:
        tuple[Evidence, ...]: Redacted syntax or runner-unavailable findings.
    """

    if parsed.summary is None:
        return (_evidence(path, 1, parsed.message),)

    return tuple(
        _evidence(path, error.line, "PowerShell syntax invalid")
        for error in parsed.summary.syntax_errors
    )


def _documentation_findings(
    path: str,
    summary: object,
    policy: LanguageQualityPolicy,
    source: str,
) -> tuple[Evidence, ...]:
    """Find declarations lacking nearby comment-based help when enabled.

    Args:
        path: Relative artifact path used by evidence.
        summary: Bounded parser summary containing declaration lines.
        policy: Immutable documentation policy.
        source: Complete PowerShell source text held in memory.

    Returns:
        tuple[Evidence, ...]: Redacted missing-help findings.
    """
    documentation = policy.documentation
    documentation_enabled = any(
        (
            documentation.require_module,
            documentation.require_classes,
            documentation.require_callables,
            documentation.include_private,
            documentation.include_nested,
            documentation.require_constructor,
            documentation.require_exact_args,
            documentation.require_returns,
            documentation.require_raises_for_explicit_raise,
            documentation.required_sections,
        )
    )

    if not documentation_enabled:
        return ()
    findings: list[Evidence] = []

    function_lines = tuple(getattr(summary, "function_lines", ()))
    class_lines = tuple(getattr(summary, "class_lines", ()))
    constructor_lines = _constructor_lines(source, class_lines)
    declaration_entries = [
        *((line, "function") for line in function_lines),
        *((line, "class") for line in class_lines),
        *((line, "constructor") for line in constructor_lines),
    ]
    declaration_entries.sort(key=lambda item: item[0])

    if documentation.require_module:
        first_declaration = declaration_entries[0][0] if declaration_entries else len(source.splitlines()) + 1
        module_prefix = "\n".join(source.splitlines()[: max(0, first_declaration - 1)])
        module_help = re.search(
            r"\.\s*(?:SYNOPSIS|DESCRIPTION)\b|#\.",
            module_prefix,
            flags=re.IGNORECASE,
        )

        if module_help is None:
            findings.append(_evidence(path, 1, "module comment-based help missing"))

    for line, kind in declaration_entries:
        name = _declaration_name(source, line, kind)
        private = name.startswith("_")

        private_excluded = (
            private
            and not documentation.include_private
            and kind != "constructor"
        )

        if private_excluded:
            continue

        nested = _brace_depth(source, line) > 0

        if nested and not documentation.include_nested and kind != "constructor":
            continue

        class_required = kind == "class" and documentation.require_classes
        function_required = kind == "function" and documentation.require_callables
        constructor_required = kind == "constructor" and documentation.require_constructor
        required = any((class_required, function_required, constructor_required))
        sections = _help_sections(source, line)
        has_help = _help_present(source, line)

        if required and not has_help:
            findings.append(_evidence(path, line, "comment-based help missing"))

        if documentation.required_sections and (required or kind == "constructor"):
            if not has_help:
                findings.append(_evidence(path, line, "comment-based help required for configured sections"))

            else:
                for section in documentation.required_sections:
                    wanted = section.lower()
                    aliases = {
                        "parameters": {"parameter", "parameters"},
                        "param": {"parameter", "parameters"},
                        "outputs": {"outputs"},
                        "return": {"outputs"},
                        "returns": {"outputs"},
                        "errors": {"exception", "errors"},
                        "throws": {"exception", "errors"},
                    }
                    accepted = aliases.get(wanted, {wanted})

                    if not accepted.intersection(sections):
                        findings.append(_evidence(path, line, f"comment-help section missing: {section}"))

        if kind in {"function", "constructor"}:
            signature = "\n".join(source.splitlines()[line - 1 : line + 16])
            param_match = re.search(r"\bparam\s*\((.*?)\)", signature, flags=re.IGNORECASE | re.DOTALL)
            expected: tuple[str, ...] = ()

            if param_match:
                expected = tuple(
                    dict.fromkeys(
                        item
                        for item in re.findall(r"\$([A-Za-z_]\w*)", param_match.group(1))
                        if item.lower() not in {"true", "false"}
                    )
                )

            help_prefix = "\n".join(
                source.splitlines()[max(0, line - 13) : line - 1]
            )
            documented_matches = re.findall(
                r"\.\s*PARAMETER\s+([A-Za-z_]\w*)",
                help_prefix,
                flags=re.IGNORECASE,
            )
            documented = tuple(dict.fromkeys(documented_matches))

            if documentation.require_exact_args:
                for parameter in (
                    *[name for name in expected if name not in documented],
                    *[name for name in documented if name not in expected],
                ):
                    findings.append(_evidence(path, line, f"parameter name mismatch: {name}.{parameter}"))

            if documentation.require_returns and kind != "constructor" and "outputs" not in sections:
                findings.append(_evidence(path, line, "comment-help OUTPUTS section missing"))

            if documentation.require_raises_for_explicit_raise:
                source_lines = source.splitlines()
                next_lines = [
                    candidate
                    for candidate in (*function_lines, *class_lines)
                    if candidate > line
                ]
                end_line = min(next_lines) - 1 if next_lines else len(source_lines)
                raises = any(
                    re.search(r"\bthrow\b", value, flags=re.IGNORECASE) is not None
                    for value in source_lines[line - 1 : end_line]
                )

                if raises and not {"exception", "errors"}.intersection(sections):
                    findings.append(_evidence(path, line, "comment-help EXCEPTION section missing"))

    return tuple(findings)


def _layout_findings(
    path: str,
    summary: object,
    policy: LanguageQualityPolicy,
    lines: tuple[object, ...] = (),
) -> tuple[Evidence, ...]:
    """Check configured blank boundaries around native PowerShell clauses.

    Args:
        path: Relative artifact path used by evidence.
        summary: Bounded parser summary containing clause ranges.
        policy: Immutable vertical-layout policy.
        lines: Immutable blank-line facts derived from source.

    Returns:
        tuple[Evidence, ...]: Redacted clause-boundary findings.
    """
    layout = policy.vertical_layout

    if not layout.enabled:
        return ()
    clause_kinds = getattr(summary, "clause_kinds", ())
    starts = getattr(summary, "clause_lines", ())
    ends = getattr(summary, "clause_end_lines", ())
    findings: list[Evidence] = []
    before = {item.lower() for item in layout.blank_before}
    after = {item.lower() for item in layout.blank_after}
    blank_lines = {
        getattr(item, "line", 0): bool(getattr(item, "blank", False))
        for item in lines
    }

    for kind, start, end in zip(clause_kinds, starts, ends):
        normalized = _clause_name(kind)

        if normalized in before and start > 1:
            count = 0
            cursor = start - 1

            while cursor > 0 and blank_lines.get(cursor, False):
                count += 1
                cursor -= 1

            if count < layout.minimum_blank_lines:
                findings.append(
                    _evidence(path, start, f"blank line missing before {normalized}")
                )

        if normalized in after:
            count = 0
            cursor = end + 1

            while cursor <= len(lines) and blank_lines.get(cursor, False):
                count += 1
                cursor += 1

            if count < layout.minimum_blank_lines:
                findings.append(
                    _evidence(path, end, f"blank line missing after {normalized}")
                )

    return tuple(findings)


def _compactness_findings(
    path: str, summary: object, policy: LanguageQualityPolicy
) -> tuple[Evidence, ...]:
    """Check semicolon and same-line native statement compactness.

    Args:
        path: Relative artifact path used by evidence.
        summary: Bounded parser summary containing token and pipeline lines.
        policy: Immutable compactness policy.

    Returns:
        tuple[Evidence, ...]: Redacted compactness findings.
    """
    compactness = policy.compactness
    findings: list[Evidence] = []

    if compactness.forbid_semicolons:
        findings.extend(
            _evidence(path, line, "semicolon statement separator")
            for line in getattr(summary, "semicolon_lines", ())
        )
    pipeline_lines = tuple(getattr(summary, "pipeline_lines", ()))
    line_counts = Counter(pipeline_lines)

    for line, count in sorted(line_counts.items()):
        if count > compactness.max_statements_per_line:
            findings.append(_evidence(path, line, "too many statements on one line"))

        if (
            compactness.max_operations_per_statement is not None
            and count > compactness.max_operations_per_statement
        ):
            findings.append(_evidence(path, line, "too many operations in one statement"))

    if compactness.forbid_one_line_suites:
        starts = getattr(summary, "clause_lines", ())
        ends = getattr(summary, "clause_end_lines", ())
        findings.extend(
            _evidence(path, start, "one-line PowerShell clause")
            for start, end in zip(starts, ends)
            if start == end
        )

    return tuple(findings)


def _clause_name(kind: str) -> str:
    """Normalize PowerShell AST type names to policy token names.

    Args:
        kind: Native PowerShell AST type name.

    Returns:
        str: Lowercase policy token name.
    """
    normalized = kind.removesuffix("Ast").lower()

    for suffix in ("statement", "clause"):
        normalized = normalized.removesuffix(suffix)

    return normalized


__all__ = ["PowerShellAnalyzer"]
