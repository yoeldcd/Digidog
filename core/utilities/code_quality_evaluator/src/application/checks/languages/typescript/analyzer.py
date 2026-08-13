"""Fixed TypeScript quality gates over the dedicated ESTree summary."""

from __future__ import annotations

import hashlib
import re
from collections import Counter

from .....domain.models import (
    EvaluationStatus,
    Evidence,
    GateResult,
    InMemoryFile,
    Language,
    LanguageQualityPolicy,
)
from ...shared.gate_ids import TYPESCRIPT_GATE_IDS
from ...shared.protocol import BaseLanguageAnalyzer
from .parser import TypeScriptParser, TypeScriptParseResult


def _evidence(path: str, digest: str, line: int, summary: str) -> Evidence:
    """Build one source-bounded evidence record.

    Args:
        path: Safe relative artifact path.
        digest: SHA-256 digest for the complete source.
        line: One-based source line associated with the finding.
        summary: Redacted evidence description.

    Returns:
        Evidence: Immutable source-bounded record.
    """

    return Evidence(
        path=path,
        line_start=max(1, line),
        line_end=max(1, line),
        kind="artifact",
        digest=digest,
        summary=summary,
    )


def _bounded(
    items: list[Evidence], policy: LanguageQualityPolicy
) -> tuple[Evidence, ...]:
    """Apply the language occurrence policy while retaining source order.

    Args:
        items: Ordered candidate evidence records.
        policy: Language policy controlling evidence cardinality.

    Returns:
        tuple[Evidence, ...]: Bounded immutable evidence.
    """
    limit = policy.occurrences.max_evidence_per_gate

    return tuple(items[:limit] if policy.occurrences.collect_all else items[:1])


def _gate(
    gate_id: str, evidence: list[Evidence], message: str, policy: LanguageQualityPolicy
) -> GateResult:
    """Create a bounded pass/fail gate.

    Args:
        gate_id: Fixed gate identifier.
        evidence: Candidate source findings.
        message: Redacted gate explanation.
        policy: Language policy controlling evidence cardinality.

    Returns:
        GateResult: Immutable pass or fail result.
    """
    bounded = _bounded(evidence, policy)
    status = EvaluationStatus.FAIL if bounded else EvaluationStatus.PASS

    return GateResult(gate_id=gate_id, status=status, message=message, evidence=bounded)


_TS_DOC_BLOCK = re.compile(r"/\*\*([\s\S]*?)\*/")
_TS_DOC_TAG = re.compile(r"@([A-Za-z][A-Za-z0-9_-]*)(?:\s+([^@\n*]+))?")


def _line_number(source: str, offset: int) -> int:
    """Return a one-based source line for a character offset.

    Args:
        source: Complete source text held in memory.
        offset: Zero-based character offset.

    Returns:
        int: One-based line number containing the offset.
    """

    return source.count("\n", 0, offset) + 1


def _documentation_block(
    source: str, declaration_line: int
) -> tuple[bool, tuple[str, ...], tuple[str, ...], bool, bool]:
    """Extract the nearest JSDoc description, sections, parameters, and outcomes.

    Args:
        source: Complete TypeScript or TSX source text.
        declaration_line: One-based declaration line.

    Returns:
        tuple: Description flag, sections, parameter names, returns flag, throws flag.
    """

    blocks: list[tuple[int, int, str]] = []

    for match in _TS_DOC_BLOCK.finditer(source):
        start = _line_number(source, match.start())
        end = _line_number(source, match.end())
        blocks.append((start, end, match.group(1)))

    selected: tuple[int, int, str] | None = None

    for block in reversed(blocks):
        if block[1] < declaration_line and declaration_line - block[1] <= 2:
            selected = block
            break

        if block[1] < declaration_line:
            break

    if selected is None:
        return False, (), (), False, False

    body = selected[2]
    description_lines: list[str] = []
    sections: list[str] = []
    parameter_names: list[str] = []

    for raw_line in body.splitlines():
        cleaned = re.sub(r"^\s*\*\s?", "", raw_line).strip()

        if cleaned and not cleaned.startswith("@"):
            description_lines.append(cleaned)

    for match in _TS_DOC_TAG.finditer(body):
        tag = match.group(1).lower()
        value = (match.group(2) or "").strip()
        sections.append(tag)


        if tag in {"param", "arg", "argument"}:
            value = re.sub(r"^\{[^}]*\}\s*", "", value)
            value = value.lstrip("[")
            name = re.split(r"[\s=\]]", value, maxsplit=1)[0]


            if name:
                parameter_names.append(name)

    normalized_sections = tuple(dict.fromkeys(sections))
    returns = any(item in {"return", "returns"} for item in normalized_sections)
    throws = any(item in {"throw", "throws", "exception", "exceptions"} for item in normalized_sections)

    return (
        bool(description_lines),
        normalized_sections,
        tuple(dict.fromkeys(parameter_names)),
        returns,
        throws,
    )


def _parameter_names(source: str, line: int, name: str) -> tuple[str, ...]:
    """Extract TypeScript callable parameters from a bounded source signature.

    Args:
        source: Complete TypeScript or TSX source text.
        line: One-based declaration line.
        name: Callable identifier used to locate the signature.

    Returns:
        tuple[str, ...]: Ordered parameter names proven by the signature.
    """

    lines = source.splitlines()

    if line < 1 or line > len(lines):
        return ()

    segment = "\n".join(lines[line - 1 : line + 12])
    name_match = re.search(rf"\b{re.escape(name)}\b", segment)
    start = segment.find("(", name_match.end() if name_match else 0)

    if start < 0:
        return ()

    depth = 0
    end = -1

    for index in range(start, len(segment)):
        character = segment[index]

        if character == "(":
            depth += 1

        elif character == ")":
            depth -= 1


            if depth == 0:
                end = index
                break

    if end < 0:
        return ()

    parameters = segment[start + 1 : end]
    result: list[str] = []
    token: list[str] = []
    nested = 0

    for character in parameters + ",":

        if character in "<{[":
            nested += 1

        elif character in ">}]":
            nested = max(0, nested - 1)


        if character == "," and nested == 0:
            candidate = "".join(token).strip()
            token = []


            if candidate:
                candidate = candidate.split("=", 1)[0].strip()
                candidate = re.sub(r"^(?:public|private|protected|readonly|in|out)\s+", "", candidate)
                candidate = candidate.split(":", 1)[0].strip().rstrip("?")
                candidate = candidate.lstrip("...").strip()

                if re.fullmatch(r"[A-Za-z_$][\w$]*", candidate) and candidate != "this":
                    result.append(candidate)

            continue

        token.append(character)

    return tuple(dict.fromkeys(result))


def _is_nested(declaration: object, declarations: tuple[object, ...]) -> bool:
    """Return whether a declaration is inside another class or callable.

    Args:
        declaration: Declaration summary currently under inspection.
        declarations: All source-ordered declaration summaries.

    Returns:
        bool: Whether an enclosing class or callable contains the declaration.
    """

    line = getattr(declaration, "line", 0)

    for parent in declarations:
        if parent is declaration:
            continue

        parent_line = getattr(parent, "line", 0)
        parent_end = getattr(parent, "end_line", parent_line)
        parent_kind = getattr(parent, "kind", "")

        if parent_line < line <= parent_end and (
            "Class" in parent_kind
            or "Function" in parent_kind
            or parent_kind == "MethodDefinition"
        ):
            return True

    return False


def _section_present(sections: tuple[str, ...], required: str) -> bool:
    """Match TypeScript JSDoc section aliases without weakening policy tokens.

    Args:
        sections: Lower-case JSDoc tags observed in one comment.
        required: Policy section identifier.

    Returns:
        bool: Whether the required section or an accepted alias is present.
    """

    aliases = {
        "param": {"param", "params", "parameter", "parameters", "arg", "args"},
        "params": {"param", "params", "parameter", "parameters", "arg", "args"},
        "parameter": {"param", "params", "parameter", "parameters", "arg", "args"},
        "parameters": {"param", "params", "parameter", "parameters", "arg", "args"},
        "return": {"return", "returns"},
        "returns": {"return", "returns"},
        "throw": {"throw", "throws", "exception", "exceptions"},
        "throws": {"throw", "throws", "exception", "exceptions"},
    }
    wanted = required.lower()
    accepted = aliases.get(wanted, {wanted})

    return any(item.lower() in accepted for item in sections)


def _documentation_enabled(policy: LanguageQualityPolicy) -> bool:
    """Return whether any TypeScript documentation rule is active.

    Args:
        policy: Complete TypeScript quality policy.

    Returns:
        bool: Whether at least one documentation or visibility rule is enabled.
    """

    requirements = policy.documentation

    return any(
        (
            requirements.require_module,
            requirements.require_classes,
            requirements.require_callables,
            requirements.include_private,
            requirements.include_nested,
            requirements.require_constructor,
            requirements.require_exact_args,
            requirements.require_returns,
            requirements.require_raises_for_explicit_raise,
            requirements.required_sections,
        )
    )


def _documentation_evidence(
    parsed: TypeScriptParseResult,
    policy: LanguageQualityPolicy,
    path: str,
    digest: str,
    source: str,
) -> list[Evidence]:
    """Find missing JSDoc descriptions and configured tags.

    Args:
        parsed: Immutable parser summary.
        policy: Documentation and visibility requirements.
        path: Safe relative artifact path.
        digest: SHA-256 digest for the complete source.
        source: Complete TypeScript or TSX source text held in memory.

    Returns:
        list[Evidence]: Source-ordered documentation findings.
    """
    requirements = policy.documentation

    if not _documentation_enabled(policy):
        return []

    findings: list[Evidence] = []

    module_documented = any(
        comment.is_jsdoc
        and comment.line <= 1
        and comment.has_description
        for comment in parsed.comments
    )

    if requirements.require_module and not module_documented:
        findings.append(_evidence(path, digest, 1, "module JSDoc is required"))

    for declaration in parsed.declarations:
        is_constructor = declaration.name.lower() == "constructor"
        constructor_allowed = requirements.require_constructor and is_constructor

        if declaration.private:
            private_excluded = not requirements.include_private and not constructor_allowed

            if private_excluded:
                continue

        nested = _is_nested(declaration, parsed.declarations)

        if nested and not requirements.include_nested and not constructor_allowed:
            continue

        is_class = "Class" in declaration.kind or declaration.kind in {
            "TSInterfaceDeclaration",
            "TSTypeAliasDeclaration",
            "TSEnumDeclaration",
        }
        is_callable = "Function" in declaration.kind or "Method" in declaration.kind
        class_documentation = is_class and requirements.require_classes
        callable_documentation = is_callable and requirements.require_callables
        constructor_documentation = is_callable and constructor_allowed
        requires_documentation = (
            class_documentation
            or callable_documentation
            or constructor_documentation
        )
        metadata_documentation = is_callable and any(
            (
                requirements.require_exact_args,
                requirements.require_returns,
                requirements.require_raises_for_explicit_raise,
            )
        )
        sections_documentation = (is_class or is_callable) and bool(
            requirements.required_sections
        )

        if not (requires_documentation or metadata_documentation or sections_documentation):
            continue

        has_description, sections, documented_parameters, has_returns, has_throws = _documentation_block(
            source, declaration.line
        )
        documented = declaration.documented and has_description

        if declaration.kind == "MethodDefinition" and has_description:
            documented = True

        if requires_documentation and not documented:
            findings.append(
                _evidence(
                    path,
                    digest,
                    declaration.line,
                    "type/class JSDoc is required" if is_class else "callable JSDoc is required",
                )
            )

        if is_callable and requirements.required_sections and not documented:
            findings.append(
                _evidence(
                    path,
                    digest,
                    declaration.line,
                    "JSDoc is required for configured sections",
                )
            )

        for section in requirements.required_sections:
            if is_callable and documented and not _section_present(sections, section):
                findings.append(
                    _evidence(
                        path,
                        digest,
                        declaration.line,
                        f"JSDoc section missing: {section}",
                    )
                )

        if is_callable and requirements.require_exact_args:
            expected = _parameter_names(source, declaration.line, declaration.name)
            mismatches = [
                *[name for name in expected if name not in documented_parameters],
                *[name for name in documented_parameters if name not in expected],
            ]

            for name in mismatches:
                findings.append(
                    _evidence(
                        path,
                        digest,
                        declaration.line,
                        f"@param name mismatch: {declaration.name}.{name}",
                    )
                )

        if is_callable and requirements.require_returns and not is_constructor and not has_returns:
            findings.append(
                _evidence(path, digest, declaration.line, "JSDoc @returns is required")
            )

        if is_callable and requirements.require_raises_for_explicit_raise:
            source_lines = source.splitlines()
            end_line = max(declaration.line, declaration.end_line)
            raises = any(
                re.search(r"\bthrow\b", line) is not None
                for line in source_lines[declaration.line - 1 : end_line]
            )

            if raises and not has_throws:
                findings.append(
                    _evidence(path, digest, declaration.line, "JSDoc @throws is required")
                )

    return findings


def _token_matches(kind: str, token: str) -> bool:
    """Match policy token aliases to ESTree and TypeScript node kinds.

    Args:
        kind: ESTree node kind.
        token: Configured layout token.

    Returns:
        bool: True when the token identifies the node kind.
    """
    normalized = token.lower().replace("_", "").replace("-", "")
    candidate = kind.lower().replace("_", "").replace("-", "")
    aliases = {
        "function": "functiondeclaration",
        "class": "classdeclaration",
        "if": "ifstatement",
        "for": "forstatement",
        "while": "whilestatement",
        "switch": "switchstatement",
        "try": "trystatement",
        "catch": "catchclause",
        "import": "importdeclaration",
        "export": "exportnameddeclaration",
        "interface": "tsinterfacedeclaration",
        "type": "tstypealiasdeclaration",
        "enum": "tsenumdeclaration",
        "namespace": "tsmoduledeclaration",
    }

    return candidate == aliases.get(normalized, normalized) or candidate.startswith(
        normalized
    )


def _vertical_evidence(
    parsed: TypeScriptParseResult, policy: LanguageQualityPolicy, path: str, digest: str
) -> list[Evidence]:
    """Check configured blank lines around TypeScript declarations and clauses.

    Args:
        parsed: Immutable parser summary.
        policy: Vertical-layout requirements.
        path: Safe relative artifact path.
        digest: SHA-256 digest for the complete source.

    Returns:
        list[Evidence]: Source-ordered layout findings.
    """
    layout = policy.vertical_layout

    if not layout.enabled:
        return []

    lines = {line.line: line for line in parsed.lines}
    findings: list[Evidence] = []

    for node in parsed.nodes:
        before = any(_token_matches(node.kind, token) for token in layout.blank_before)
        after = any(_token_matches(node.kind, token) for token in layout.blank_after)

        if before and node.line > 1:
            blank_count = 0
            cursor = node.line - 1

            while cursor > 0 and lines.get(cursor) is not None and lines[cursor].blank:
                blank_count += 1
                cursor -= 1

            if blank_count < layout.minimum_blank_lines:
                findings.append(
                    _evidence(
                        path,
                        digest,
                        node.line,
                        f"blank line missing before {node.kind}",
                    )
                )

        if after and node.end_line < len(parsed.lines):
            blank_count = 0
            cursor = node.end_line + 1

            while cursor <= len(parsed.lines):
                current_line = lines.get(cursor)

                if current_line is None or not current_line.blank:
                    break

                blank_count += 1
                cursor += 1

            if blank_count < layout.minimum_blank_lines:
                findings.append(
                    _evidence(
                        path,
                        digest,
                        node.end_line,
                        f"blank line missing after {node.kind}",
                    )
                )

    return findings


def _compactness_evidence(
    parsed: TypeScriptParseResult,
    policy: LanguageQualityPolicy,
    path: str,
    digest: str,
    source: str = "",
) -> list[Evidence]:
    """Collect semicolon, one-line-suite, statement, and operation findings.

    Args:
        parsed: Immutable parser summary.
        policy: Compactness requirements.
        path: Safe relative artifact path.
        digest: SHA-256 digest for the complete source.
        source: Complete TypeScript or TSX source text held in memory.

    Returns:
        list[Evidence]: Source-ordered compactness findings.
    """
    compactness = policy.compactness
    findings: list[Evidence] = []

    if compactness.forbid_semicolons:
        for line in parsed.semicolon_lines:
            semicolon_evidence = _evidence(
                path, digest, line, "semicolon statement separator"
            )
            findings.append(semicolon_evidence)

    if compactness.forbid_one_line_suites:
        for node in parsed.nodes:
            if node.one_line_suite:
                suite_evidence = _evidence(path, digest, node.line, "one-line suite")
                findings.append(suite_evidence)

    line_counts = Counter(statement.line for statement in parsed.statements)

    for line, count in sorted(line_counts.items()):
        if count > compactness.max_statements_per_line:
            findings.append(
                _evidence(path, digest, line, "too many statements on one line")
            )

    if compactness.max_operations_per_statement is not None:
        for statement in parsed.statements:
            source_lines = source.splitlines()
            statement_text = "\n".join(
                source_lines[statement.line - 1 : statement.end_line]
            )
            fluent_chain = (
                compactness.exempt_fluent_chains
                and statement_text.count(".") >= 2
            )
            comprehension = (
                compactness.exempt_comprehensions
                and re.search(r"\bfor\b[\s\S]*\bin\b", statement_text)
                is not None
            )

            if fluent_chain or comprehension:
                continue

            if statement.operation_count > compactness.max_operations_per_statement:
                for line in statement.operation_lines:
                    operation_evidence = _evidence(
                        path, digest, line, "too many operations in one statement"
                    )
                    findings.append(operation_evidence)

    return sorted(findings, key=lambda item: (item.line_start or 0, item.summary))


def _syntax_gates(
    parsed: TypeScriptParseResult, path: str, digest: str
) -> tuple[GateResult, ...] | None:
    """Return fixed syntax/dependent gates when parsing fails.

    Args:
        parsed: Immutable parser summary.
        path: Safe relative artifact path.
        digest: SHA-256 digest for the complete source.

    Returns:
        tuple[GateResult, ...] | None: Blocking gates, or none when valid.
    """

    if parsed.syntax_valid:
        return None

    evidence = (_evidence(path, digest, parsed.error_line or 1, "syntax invalid"),)

    return tuple(
        GateResult(
            gate_id=gate_id,
            status=EvaluationStatus.FAIL
            if gate_id == "TS-SYNTAX"
            else EvaluationStatus.BLOCKED,
            message="syntax invalid"
            if gate_id == "TS-SYNTAX"
            else "syntax-dependent gate blocked",
            evidence=evidence,
        )
        for gate_id in TYPESCRIPT_GATE_IDS
    )


class TypeScriptAnalyzer(BaseLanguageAnalyzer):
    """Analyze TypeScript and TSX with exactly four fixed gates."""

    language = Language.TYPESCRIPT
    gate_ids = TYPESCRIPT_GATE_IDS

    def __init__(self, parser: TypeScriptParser | None = None) -> None:
        """Initialize the analyzer with an optional injectable parser.

        Args:
            parser: Optional parser implementation used for deterministic tests.
        """
        self._parser = parser or TypeScriptParser()

    def _analyze(
        self, artifact: InMemoryFile, policy: LanguageQualityPolicy
    ) -> tuple[GateResult, ...]:
        """Return syntax, documentation, vertical-layout, and compactness gates.

        Args:
            artifact: In-memory TypeScript artifact.
            policy: Complete TypeScript quality policy.

        Returns:
            tuple[GateResult, ...]: Exact four fixed gate results.
        """
        parsed = self._parser.parse(artifact.content)
        digest = hashlib.sha256(artifact.content.encode("utf-8")).hexdigest()
        syntax_gates = _syntax_gates(parsed, artifact.path, digest)

        if syntax_gates is not None:
            return syntax_gates

        documentation = _documentation_evidence(
            parsed, policy, artifact.path, digest, artifact.content
        )
        vertical = _vertical_evidence(parsed, policy, artifact.path, digest)
        compactness = _compactness_evidence(
            parsed, policy, artifact.path, digest, artifact.content
        )
        docs_enabled = _documentation_enabled(policy)

        return (
            _gate("TS-SYNTAX", [], "syntax valid", policy),
            _gate(
                "TS-DOCUMENTATION",
                documentation,
                "documentation complete"
                if docs_enabled
                else "documentation policy disabled",
                policy,
            ),
            _gate(
                "TS-VERTICAL-LAYOUT",
                vertical,
                "vertical layout valid"
                if policy.vertical_layout.enabled
                else "vertical layout policy disabled",
                policy,
            ),
            _gate("TS-COMPACTNESS", compactness, "compactness valid", policy),
        )


def evaluate_typescript(
    content: str, policy: LanguageQualityPolicy, path: str = "artifact.ts"
) -> tuple[GateResult, ...]:
    """Evaluate TypeScript source and return the exact four language gates.

    Args:
        content: Complete TypeScript source held in memory.
        policy: Complete TypeScript quality policy.
        path: Safe relative artifact path, or a redacted fallback.

    Returns:
        tuple[GateResult, ...]: Exact four fixed gate results.
    """
    safe_path = path

    try:
        Evidence(path=path, kind="artifact")

    except (TypeError, ValueError):
        safe_path = "artifact.ts"
    artifact = InMemoryFile(
        path=safe_path, language=Language.TYPESCRIPT, content=content
    )

    return TypeScriptAnalyzer().analyze(artifact, policy).gates


__all__ = ["TypeScriptAnalyzer", "evaluate_typescript"]
