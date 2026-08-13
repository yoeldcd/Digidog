"""Public presentation contracts for code-quality command results."""

from .models import (
    CommandReport,
    ErrorReport,
    EvaluationReport,
    FileEvaluationReport,
    FileFormatReport,
    FindingReport,
    FormatReport,
    GateReport,
    SemanticCriterionReport,
    SemanticReport,
)
from .markdown_renderer import (
    render_error_markdown,
    render_evaluation_markdown,
    render_format_markdown,
    render_markdown,
)
from .projection import (
    project_evaluation,
    project_evaluation_report,
    project_format,
    project_format_report,
    public_payload,
)

__all__ = [
    "CommandReport",
    "ErrorReport",
    "EvaluationReport",
    "FileEvaluationReport",
    "FileFormatReport",
    "FindingReport",
    "FormatReport",
    "GateReport",
    "SemanticCriterionReport",
    "SemanticReport",
    "project_evaluation",
    "project_evaluation_report",
    "project_format",
    "project_format_report",
    "public_payload",
    "render_evaluation_markdown",
    "render_error_markdown",
    "render_format_markdown",
    "render_markdown",
]
