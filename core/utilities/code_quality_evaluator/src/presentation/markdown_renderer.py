"""Render public code-quality reports as concise human-readable Markdown."""

from __future__ import annotations

from collections.abc import Iterable

from src.domain.models import EvaluationStatus

from .models import ErrorReport, EvaluationReport, FileEvaluationReport, FormatReport


def _status(status: EvaluationStatus) -> str:
    """Return a status in uppercase form for terminal output.

    Args:
        status: Public evaluation status.

    Returns:
        str: Uppercase status label.
    """

    return status.value.upper()


def _line_reference(path: str, line_start: int | None, line_end: int | None) -> str:
    """Format a bounded path and optional source line range.

    Args:
        path: Relative source path.
        line_start: First relevant line, when known.
        line_end: Last relevant line, when known.

    Returns:
        str: Human-readable path and line reference.
    """

    if line_start is None:
        return path

    if line_end is None or line_end == line_start:
        return f"{path}:{line_start}"

    return f"{path}:{line_start}-{line_end}"


def _render_findings(lines: list[str], findings: Iterable[object], indent: str) -> None:
    """Append source findings to a Markdown list.

    Args:
        lines: Mutable output line buffer.
        findings: Public finding objects with path and summary fields.
        indent: Markdown indentation for nested findings.

    Returns:
        None: The line buffer is updated in place.
    """

    for finding in findings:
        occurrence_text = (
            "" if finding.occurrences == 1 else f" ({finding.occurrences} occurrences)"
        )
        lines.append(
            f"{indent}- [{finding.kind}] "
            f"{_line_reference(finding.path, finding.line_start, finding.line_end)}: "
            f"{finding.summary}{occurrence_text}"
        )


def _render_file(lines: list[str], file_report: FileEvaluationReport) -> None:
    """Append one file status and its non-passing gates.

    Args:
        lines: Mutable output line buffer.
        file_report: Public per-file report.

    Returns:
        None: The line buffer is updated in place.
    """

    lines.append(f"- `{file_report.path}` ({file_report.language.value}): {_status(file_report.status)}")

    for gate in file_report.gates:
        lines.append(f"  - `{gate.gate_id}` [{_status(gate.status)}]: {gate.message}")
        _render_findings(lines, gate.findings, "    ")


def render_evaluation_markdown(report: EvaluationReport) -> str:
    """Render one check/evaluate report with actionable failures only.

    Args:
        report: Immutable public evaluation report.

    Returns:
        str: Markdown headline, summary, file findings, commands, and semantics.
    """

    operation = report.mode.title()
    lines = [
        f"# Code quality {operation}",
        "",
        f"**Status:** {_status(report.status)}",
        "",
        report.summary,
    ]

    if report.files:
        lines.extend(("", "## Files"))

        for file_report in report.files:
            _render_file(lines, file_report)

    if report.commands:
        lines.extend(("", "## Commands"))

        for command in report.commands:
            exit_text = "" if command.exit_code is None else f" (exit {command.exit_code})"
            lines.append(
                f"- `{command.command_id}` [{_status(command.status)}]{exit_text}: "
                f"{command.message}"
            )

    if report.semantic is not None:
        lines.extend(("", "## Semantic criteria"))
        aggregate_note = (
            " (blocks aggregate)" if report.semantic.blocks_aggregate else ""
        )
        semantic_label = (
            f"- `{report.semantic.evaluator_id}` [{_status(report.semantic.status)}]"
        )
        lines.append(
            semantic_label + aggregate_note
        )

        for criterion in report.semantic.criteria:
            score = "" if criterion.score is None else f"; score {criterion.score:.2f}"
            lines.append(
                f"  - `{criterion.criterion_id}` [{_status(criterion.status)}]{score}: "
                f"{criterion.rationale}"
            )
            _render_findings(lines, criterion.findings, "    ")

    return "\n".join(lines) + "\n"


def _render_candidate(lines: list[str], path: str, content: str) -> None:
    """Append a formatter candidate in a fenced code block.

    Args:
        lines: Mutable output line buffer.
        path: Relative source path.
        content: In-memory formatted candidate.

    Returns:
        None: The line buffer is updated in place.
    """

    heading = f"### Candidate for `{path}`"
    candidate_lines = content.rstrip("\n")
    lines.extend(("", heading, "", "```", candidate_lines, "```"))


def render_format_markdown(report: FormatReport) -> str:
    """Render formatter candidates and blockers in input order.

    Args:
        report: Immutable public formatter report.

    Returns:
        str: Markdown headline, status, summary, and per-file outcomes.
    """

    lines = [
        "# Code quality Format",
        "",
        f"**Status:** {_status(report.status)}",
        "",
        report.summary,
        "",
        "## Files",
    ]

    for file_report in report.files:
        lines.append(
            f"- `{file_report.path}` ({file_report.language.value}): "
            f"[{_status(file_report.status)}] {file_report.message}"
        )

        if file_report.content is not None:
            _render_candidate(lines, file_report.path, file_report.content)

    return "\n".join(lines) + "\n"


def render_error_markdown(report: ErrorReport) -> str:
    """Render one source-redacted launcher failure.

    Args:
        report: Immutable public error report.

    Returns:
        str: Markdown headline, status, and bounded recovery summary.
    """

    return "\n".join(
        (
            "# Code quality",
            "",
            f"**Status:** {_status(report.status)}",
            "",
            report.summary,
            "",
        )
    )


def render_markdown(report: ErrorReport | EvaluationReport | FormatReport) -> str:
    """Render any public code-quality report.

    Args:
        report: Error, evaluation, or format report produced by the presentation
            boundary.

    Returns:
        str: Human-readable Markdown equivalent of the report.
    """

    if isinstance(report, ErrorReport):
        return render_error_markdown(report)

    if isinstance(report, FormatReport):
        return render_format_markdown(report)

    return render_evaluation_markdown(report)


render_evaluation = render_evaluation_markdown
render_format = render_format_markdown
