"""Adapt Brain command arguments to the canonical Core evaluator launcher."""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout

from utilities.code_quality_evaluator import code_quality_evaluator

COMMAND_NAME = "code-quality"
ERROR_MESSAGE = "code quality evaluation failed"


def _launcher_arguments(args: argparse.Namespace) -> list[str]:
    """Build the exact canonical launcher arguments.

    Args:
        args: Parsed Brain command arguments.

    Returns:
        list[str]: Arguments forwarded to the Core launcher.
    """

    mode = getattr(args, "mode", "check")
    launcher_arguments = [*getattr(args, "paths", ()), "--mode", mode]
    evaluator = getattr(args, "evaluator", "")
    language = getattr(args, "language", "")

    if evaluator:
        launcher_arguments.extend(("--evaluator", evaluator))

    if language:
        launcher_arguments.extend(("--language", language))

    if mode == "schema":
        launcher_arguments.extend(("--schema", getattr(args, "schema", "request")))

    return launcher_arguments


def _failure(args: argparse.Namespace) -> int:
    """Attach one stable source-redacted failure payload.

    Args:
        args: Brain namespace receiving semantic JSON output.

    Returns:
        int: Stable blocked/error exit code.
    """

    args.json_payload = {
        "command": COMMAND_NAME,
        "mode": getattr(args, "mode", "check"),
        "status": "blocked",
        "summary": ERROR_MESSAGE,
    }

    return 2


def _render_markdown(payload: dict[str, object]) -> str:
    """Render a Core public report through the shared Markdown renderer.

    Args:
        payload: One parsed Core result without the Brain command marker.

    Returns:
        str: Human-readable Markdown equivalent of the public report.

    Raises:
        ValueError: If the payload does not match a known public result schema.
    """

    projection = code_quality_evaluator._load_projection_module()
    from src.presentation.markdown_renderer import render_markdown

    mode = payload.get("mode")

    if mode in {"check", "evaluate"}:
        model = projection.EvaluationReport

    elif mode == "format":
        model = projection.FormatReport

    elif mode == "schema":
        title = payload.get("title", "schema")

        return f"# Code quality schema\n\n{title}\n"

    else:
        model = projection.ErrorReport

    try:
        report = model.model_validate_json(json.dumps(payload))

    except (TypeError, ValueError):
        status = str(payload.get("status", "error")).upper()
        summary = str(payload.get("summary", ERROR_MESSAGE))

        return f"# Code quality\n\n**Status:** {status}\n\n{summary}\n"

    return render_markdown(report)


def handle(args: argparse.Namespace) -> int:
    """Delegate execution to Core and preserve its compact JSON payload.

    Args:
        args: Parsed Brain command arguments.

    Returns:
        int: Exact Core launcher exit code, or two for adapter failure.
    """

    output = io.StringIO()

    try:
        with redirect_stdout(output):
            exit_code = code_quality_evaluator.main(_launcher_arguments(args))

    except (RuntimeError, TypeError, ValueError):
        return _failure(args)

    documents = tuple(line for line in output.getvalue().splitlines() if line.strip())

    if len(documents) != 1:
        return _failure(args)

    try:
        payload = json.loads(documents[0])

    except json.JSONDecodeError:
        return _failure(args)

    if not isinstance(payload, dict):
        return _failure(args)

    public_payload = dict(payload)
    args.json_payload = {"command": COMMAND_NAME, **public_payload}

    if not getattr(args, "json", False):
        try:
            print(_render_markdown(public_payload), end="")

        except (RuntimeError, TypeError, ValueError):
            return _failure(args)

    return exit_code
