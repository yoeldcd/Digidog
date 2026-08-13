"""Evaluate in-memory artifacts against deterministic quality gates."""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath

from src.domain.models import (
    EvaluationStatus,
    Evidence,
    GateResult,
    LanguageQualityPolicy,
)


def _safe_evidence_path(path: str) -> str:
    """Return a DTO-safe relative path for evidence construction.

    Args:
        path: Candidate artifact path supplied by the caller.

    Returns:
        str: Candidate path when safe, otherwise a redacted fallback.
    """

    try:
        Evidence(path=path, kind="artifact")

    except (TypeError, ValueError):
        return "artifact"

    return path


def _line_number(content: str, offset: int) -> int:
    """Translate a character offset into a one-based source line number.

    Args:
        content: Complete in-memory artifact text.
        offset: Zero-based character offset within ``content``.

    Returns:
        int: One-based line number containing the offset.
    """

    line_count = content.count("\n", 0, offset)

    return line_count + 1


def _evidence(path: str, digest: str, line: int, summary: str) -> Evidence:
    """Construct one immutable, source-bounded evidence record.

    Args:
        path: Safe relative artifact path.
        digest: SHA-256 digest of the complete artifact.
        line: One-based source line associated with the evidence.
        summary: Human-readable evidence description.

    Returns:
        Evidence: Immutable evidence record with a single-line range.
    """

    return Evidence(
        path=path,
        line_start=max(1, line),
        line_end=max(1, line),
        kind="artifact",
        digest=digest,
        summary=summary,
    )


def _literal_matches(content: str, literal: str) -> tuple[int, ...]:
    """Return every non-overlapping occurrence offset for one literal.

    Args:
        content: Complete in-memory artifact text.
        literal: Literal value to locate.

    Returns:
        tuple[int, ...]: Character offsets in ascending source order.
    """

    if not literal:
        return ()

    offsets: list[int] = []
    cursor = 0

    while True:
        offset = content.find(literal, cursor)

        if offset < 0:
            break

        offsets.append(offset)
        cursor = offset + len(literal)

    return tuple(offsets)


def _pattern_matches(content: str, pattern: str) -> tuple[int, ...]:
    """Return every regular-expression match offset for one pattern.

    Args:
        content: Complete in-memory artifact text.
        pattern: Regular expression to locate.

    Returns:
        tuple[int, ...]: Match offsets in ascending source order.

    Raises:
        ValueError: If ``pattern`` is not a valid regular expression.
    """

    try:
        return tuple(match.start() for match in re.finditer(pattern, content))

    except re.error as error:
        raise ValueError("invalid forbidden pattern") from error


def _path_is_authorized(path: str, authorized_path: str) -> bool:
    """Compare two relative POSIX paths without touching the filesystem.

    Args:
        path: Candidate artifact path.
        authorized_path: Expected authorized relative path.

    Returns:
        bool: True only when both paths are safe and equal after normalization.
    """

    try:
        normalized_path = PurePosixPath(path).as_posix()
        normalized_authorized = PurePosixPath(authorized_path).as_posix()
        Evidence(path=normalized_path, kind="artifact")
        Evidence(path=normalized_authorized, kind="artifact")

    except (TypeError, ValueError):
        return False

    return normalized_path == normalized_authorized


def _bound_evidence(
    evidence: tuple[Evidence, ...],
    limit: int,
    collect_all: bool,
) -> tuple[Evidence, ...]:
    """Apply the configured evidence cardinality policy.

    Args:
        evidence: Evidence records ordered by source occurrence.
        limit: Maximum number of records retained for one gate.
        collect_all: Whether every occurrence up to ``limit`` is requested.

    Returns:
        tuple[Evidence, ...]: Bounded evidence preserving source order.
    """

    if collect_all:
        return evidence[:limit]

    return evidence[:1]


def evaluate_artifact(
    path: str,
    content: str,
    authorized_path: str,
    required_literals: tuple[str, ...] = (),
    forbidden_literals: tuple[str, ...] = (),
    forbidden_patterns: tuple[str, ...] = (),
    max_line_length: int | None = 120,
    policy: LanguageQualityPolicy | None = None,
) -> tuple[GateResult, ...]:
    """Evaluate an artifact entirely in memory and return six stable gates.

    Args:
        path: Relative artifact path supplied by the caller.
        content: Complete artifact content held in memory.
        authorized_path: Expected relative path for the artifact.
        required_literals: Text values that must occur in the content.
        forbidden_literals: Text values that must not occur in the content.
        forbidden_patterns: Regular expressions that must not match content.
        max_line_length: Maximum permitted line length, or ``None`` to disable it.
        policy: Optional immutable policy overriding explicit gate settings.

    Returns:
        tuple[GateResult, ...]: Six gates in stable identifier order.

    Raises:
        ValueError: If a configured forbidden pattern is invalid.
    """

    if policy is not None:
        required_literals = policy.required_literals
        forbidden_literals = policy.forbidden_literals
        forbidden_patterns = policy.forbidden_patterns
        max_line_length = policy.line_length

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    lines = content.splitlines() or [""]
    evidence_path = _safe_evidence_path(path)
    collect_all = policy.occurrences.collect_all if policy is not None else True
    evidence_limit = (
        policy.occurrences.max_evidence_per_gate if policy is not None else 1000
    )

    def make_gate(
        gate_id: str,
        passed: bool,
        message: str,
        evidence: tuple[Evidence, ...] = (),
    ) -> GateResult:
        """Build one immutable artifact gate result.

        Args:
            gate_id: Stable gate identifier.
            passed: Whether the gate condition passed.
            message: Human-readable gate outcome.
            evidence: Bounded source evidence supporting the outcome.

        Returns:
            GateResult: Immutable gate result.
        """
        status = EvaluationStatus.PASS if passed else EvaluationStatus.FAIL
        bounded = _bound_evidence(evidence, evidence_limit, collect_all)

        return GateResult(
            gate_id=gate_id,
            status=status,
            message=message,
            evidence=bounded,
        )

    content_is_nonblank = bool(content.strip())
    content_evidence = (
        ()
        if content_is_nonblank
        else (_evidence(evidence_path, digest, 1, "content is blank"),)
    )
    path_is_valid = _path_is_authorized(path, authorized_path)
    path_evidence = (
        ()
        if path_is_valid
        else (
            _evidence(evidence_path, digest, 1, "path does not match authorized path"),
        )
    )
    line_evidence = tuple(
        _evidence(evidence_path, digest, line_number, "line exceeds maximum length")
        for line_number, line in enumerate(lines, start=1)
        if max_line_length is not None and len(line) > max_line_length
    )

    required_evidence: list[Evidence] = []
    required_pass = True

    for literal in required_literals:
        offsets = _literal_matches(content, literal)
        required_pass = required_pass and bool(offsets)

        if offsets:
            required_evidence.extend(
                _evidence(
                    evidence_path,
                    digest,
                    _line_number(content, offset),
                    f"required literal occurrence: {literal}",
                )
                for offset in offsets
            )

        else:
            required_evidence.append(
                _evidence(
                    evidence_path, digest, 1, f"required literal missing: {literal}"
                )
            )

    forbidden_evidence: list[Evidence] = []

    for literal in forbidden_literals:
        forbidden_evidence.extend(
            _evidence(
                evidence_path,
                digest,
                _line_number(content, offset),
                f"forbidden literal occurrence: {literal}",
            )
            for offset in _literal_matches(content, literal)
        )

    for pattern in forbidden_patterns:
        forbidden_evidence.extend(
            _evidence(
                evidence_path,
                digest,
                _line_number(content, offset),
                f"forbidden pattern occurrence: {pattern}",
            )
            for offset in _pattern_matches(content, pattern)
        )

    digest_evidence = (_evidence(evidence_path, digest, 1, "sha256 digest recorded"),)
    digest_gate = make_gate(
        "REQ-01-DIGEST",
        True,
        "sha256 digest recorded",
        digest_evidence,
    )

    content_message = (
        "content is non-blank" if content_is_nonblank else "content is blank"
    )
    content_gate = make_gate(
        "REQ-01-CONTENT",
        content_is_nonblank,
        content_message,
        content_evidence,
    )

    path_message = (
        "path matches authorized relative path"
        if path_is_valid
        else "path does not match authorized relative path"
    )
    path_gate = make_gate("REQ-01-PATH", path_is_valid, path_message, path_evidence)

    line_pass = not line_evidence
    line_message = (
        "line lengths are within limit"
        if max_line_length is not None
        else "line-length policy disabled"
    )
    line_gate = make_gate(
        "REQ-01-LINE-LENGTH",
        line_pass,
        line_message,
        line_evidence,
    )

    ordered_required_evidence = tuple(
        sorted(required_evidence, key=lambda item: item.line_start or 0)
    )
    required_message = (
        "required literals are present"
        if required_pass
        else "required literals are missing"
    )
    required_gate = make_gate(
        "REQ-01-REQUIRED",
        required_pass,
        required_message,
        ordered_required_evidence,
    )

    ordered_forbidden_evidence = tuple(
        sorted(forbidden_evidence, key=lambda item: item.line_start or 0)
    )
    forbidden_pass = not forbidden_evidence
    forbidden_message = (
        "forbidden content is absent"
        if forbidden_pass
        else "forbidden content detected"
    )
    forbidden_gate = make_gate(
        "REQ-01-FORBIDDEN",
        forbidden_pass,
        forbidden_message,
        ordered_forbidden_evidence,
    )

    return (
        digest_gate,
        content_gate,
        path_gate,
        line_gate,
        required_gate,
        forbidden_gate,
    )
