"""Standalone launcher for in-memory code-quality evaluation reports."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Final, Protocol

UTILITY_ROOT: Final[Path] = Path(__file__).resolve().parent
CORE_ROOT: Final[Path] = UTILITY_ROOT.parents[1]
DEFAULT_CONFIG_PATH: Final[Path] = CORE_ROOT / "configs" / "code_evaluator_configs.json"


class _Status(Protocol):
    """Describe an enum-like status rendered by the launcher."""

    value: str


class _EvaluationResult(Protocol):
    """Describe an immutable aggregate result rendered by the launcher."""

    status: _Status

    def model_dump(self, *, mode: str, exclude_defaults: bool) -> dict[str, object]:
        """Serialize the result at the presentation boundary.

        Args:
            mode: Serialization mode selected by the caller.
            exclude_defaults: Whether default-valued fields are omitted.

        Returns:
            dict[str, object]: JSON-compatible result fields.
        """


@dataclass(frozen=True, slots=True)
class _Bindings:
    """Hold lazily imported utility services.

    Attributes:
        parse_request: Strict request parser.
        load_config: Isolated configuration loader.
        resolve_evaluator: Evaluator profile resolver.
        resolve_language_policy: Exact per-language policy resolver.
        evaluate_code: Core in-memory facade.
        openai_transport: Authorized semantic transport type.
        formatter_runner: In-memory formatter runner type.
        generate_schemas: DTO schema snapshot generator.
        recognized_errors: Safe errors rendered as CLI failures.
    """

    parse_request: object
    load_config: object
    resolve_evaluator: object
    resolve_language_policy: object
    evaluate_code: object
    openai_transport: object
    formatter_runner: object
    generate_schemas: object
    recognized_errors: tuple[type[Exception], ...]


class CliError(ValueError):
    """Represent a source-redacted launcher failure."""


class _JsonArgumentParser(argparse.ArgumentParser):
    """Raise typed usage failures instead of writing argparse diagnostics."""

    def error(self, message: str) -> None:
        """Raise a bounded usage failure.

        Args:
            message: Argparse diagnostic, intentionally not exposed verbatim.

        Raises:
            CliError: Always, with a stable source-redacted message.

        Returns:
            None: This method always raises ``CliError``.
        """

        raise CliError("invalid command arguments")


def _load_bindings() -> _Bindings:
    """Load the relocatable utility package after bootstrapping its root.

    Args:

    Returns:
        _Bindings: Immutable runtime service bindings.
    """

    utility_root_text = str(UTILITY_ROOT)

    if utility_root_text not in sys.path:
        sys.path.insert(0, utility_root_text)

    from pydantic import ValidationError
    from src.application.configuration import (
        ConfigError,
        generate_schema_snapshots,
        load_config,
        resolve_evaluator,
        resolve_language_policy,
    )
    from src.application.specification import SpecificationError, parse_request
    from src.facade import evaluate_code
    from src.infrastructure.formatter_runner import InMemoryFormatterRunner
    from src.infrastructure.openai_transport import OpenAITransport

    return _Bindings(
        parse_request=parse_request,
        load_config=load_config,
        resolve_evaluator=resolve_evaluator,
        resolve_language_policy=resolve_language_policy,
        evaluate_code=evaluate_code,
        openai_transport=OpenAITransport,
        formatter_runner=InMemoryFormatterRunner,
        generate_schemas=generate_schema_snapshots,
        recognized_errors=(
            CliError,
            ConfigError,
            SpecificationError,
            ValidationError,
            ValueError,
        ),
    )


def _load_projection_module() -> ModuleType:
    """Load the presentation projection after utility import bootstrapping.

    Args:
        No arguments are accepted.

    Returns:
        ModuleType: Public projection module used by the launcher modes.
    """

    utility_root_text = str(UTILITY_ROOT)

    if utility_root_text not in sys.path:
        sys.path.insert(0, utility_root_text)

    from src.presentation import projection

    return projection


def _build_parser() -> argparse.ArgumentParser:
    """Build the compact launcher argument contract.

    Args:

    Returns:
        argparse.ArgumentParser: Configured parser without automatic diagnostics.
    """

    parser = _JsonArgumentParser(prog="code-quality")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Workspace-relative files evaluated directly.",
    )
    parser.add_argument(
        "--mode",
        choices=("check", "evaluate", "format", "schema"),
        default="check",
    )
    parser.add_argument(
        "--language",
        choices=(
            "python",
            "javascript",
            "typescript",
            "markdown",
            "json",
            "powershell",
        ),
        help="Optional language override for direct file input.",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--evaluator")
    parser.add_argument(
        "--schema",
        choices=("request", "result", "format", "error", "config", "model"),
        default="request",
    )

    return parser


def _compact(payload: object) -> None:
    """Write exactly one compact JSON document.

    Args:
        payload: JSON-serializable presentation payload.

    Returns:
        None: Output is written to standard output.
    """

    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _exit_code(status: _Status) -> int:
    """Map evaluation status to the stable CLI exit contract.

    Args:
        status: Aggregate or formatter status.

    Returns:
        int: Zero for pass, one for fail/disagree, two otherwise.
    """

    if status.value == "pass":
        return 0

    if status.value in {"fail", "disagree"}:
        return 1

    return 2


def _disable_semantic_policies_for_request(
    evaluator: object,
    request: object,
    resolve_language_policy: object,
) -> object:
    """Disable semantic checks only for policies used by a check request.

    Args:
        evaluator: Immutable evaluator profile selected for the request.
        request: Parsed request containing the requested source files.
        resolve_language_policy: Resolver used to require an exact policy for every
            requested language.

    Returns:
        object: Evaluator profile with requested language semantics disabled.

    Raises:
        ValueError: If any requested language has no configured policy.
    """

    requested_languages = _resolve_request_languages(
        evaluator,
        request,
        resolve_language_policy,
    )

    requested_language_set = frozenset(requested_languages)
    policies = []

    for policy in evaluator.language_policies:
        if policy.language not in requested_language_set:
            policies.append(policy)
            continue

        semantic_policy = policy.semantic_policy.model_copy(
            update={"enabled": False, "required": False}
        )
        policies.append(policy.model_copy(update={"semantic_policy": semantic_policy}))

    return evaluator.model_copy(update={"language_policies": tuple(policies)})


def _resolve_request_languages(
    evaluator: object,
    request: object,
    resolve_language_policy: object,
) -> tuple[object, ...]:
    """Require one configured quality policy for every requested language.

    Args:
        evaluator: Immutable evaluator profile selected for the request.
        request: Parsed request containing the requested source files.
        resolve_language_policy: Resolver used to validate exact policy coverage.

    Returns:
        tuple[object, ...]: Requested language enum values in file order.

    Raises:
        ValueError: If any requested language has no configured policy.
    """

    requested_languages = tuple(source_file.language for source_file in request.files)

    for language in requested_languages:
        resolve_language_policy(evaluator, language)

    return requested_languages


_LANGUAGE_BY_SUFFIX: Final[dict[str, str]] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".md": "markdown",
    ".json": "json",
    ".ps1": "powershell",
    ".psm1": "powershell",
}


def _request_from_paths(args: argparse.Namespace) -> str:
    """Build compact request JSON from confined direct file arguments.

    Args:
        args: Parsed arguments containing paths and optional language override.

    Returns:
        str: Compact request JSON for the strict DTO parser.

    Raises:
        CliError: No path is supplied or a path is unsafe, unreadable, or unsupported.
    """

    if not args.paths:
        raise CliError("at least one file path is required")

    workspace_root = Path.cwd().resolve()
    files: list[dict[str, str]] = []

    for raw_path in args.paths:
        relative_path = Path(raw_path)

        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise CliError("unsafe direct file path")

        source_path = (workspace_root / relative_path).resolve()

        if workspace_root not in source_path.parents and source_path != workspace_root:
            raise CliError("unsafe direct file path")

        language = args.language or _LANGUAGE_BY_SUFFIX.get(source_path.suffix.lower())

        if language is None:
            raise CliError("unsupported direct file language")

        try:
            source = source_path.read_text(encoding="utf-8")

        except (OSError, UnicodeError) as error:
            raise CliError("direct file is unavailable") from error

        files.append(
            {
                "path": relative_path.as_posix(),
                "language": language,
                "content": source,
            }
        )

    return json.dumps({"files": files}, ensure_ascii=False, separators=(",", ":"))


def _evaluation_mode(
    *,
    args: argparse.Namespace,
    serialized_request: str,
    bindings: _Bindings,
) -> int:
    """Run deterministic-only or semantic evaluation.

    Args:
        args: Parsed launcher arguments.
        serialized_request: Complete request JSON from stdin.
        bindings: Runtime utility services.

    Returns:
        int: Stable status-derived process exit code.
    """

    request = bindings.parse_request(serialized_request)
    config = bindings.load_config(args.config)
    evaluator = bindings.resolve_evaluator(config, args.evaluator)
    transport = None

    if args.mode == "check":
        evaluator = _disable_semantic_policies_for_request(
            evaluator,
            request,
            bindings.resolve_language_policy,
        )

    else:
        _resolve_request_languages(
            evaluator,
            request,
            bindings.resolve_language_policy,
        )
        transport = bindings.openai_transport()

    result: _EvaluationResult = bindings.evaluate_code(
        request,
        evaluator,
        transport,
    )
    projection = _load_projection_module()
    report = projection.project_evaluation(request, result, mode=args.mode)
    _compact(projection.public_payload(report))

    return _exit_code(result.status)


def _format_mode(
    *,
    args: argparse.Namespace,
    serialized_request: str,
    bindings: _Bindings,
) -> int:
    """Format every requested file through its configured in-memory formatter.

    Args:
        args: Parsed launcher arguments.
        serialized_request: Complete request JSON from stdin.
        bindings: Runtime utility services.

    Returns:
        int: Highest formatter status exit code.
    """

    request = bindings.parse_request(serialized_request)
    config = bindings.load_config(args.config)
    evaluator = bindings.resolve_evaluator(config, args.evaluator)
    runner = bindings.formatter_runner()
    outcomes = []

    for source_file in request.files:
        try:
            policy = bindings.resolve_language_policy(evaluator, source_file.language)

        except ValueError:
            policy = None

        formatter = (
            policy.formatters[0] if policy is not None and policy.formatters else None
        )

        if formatter is None:
            outcomes.append(None)

            continue

        outcomes.append(
            runner.run(
                formatter,
                source=source_file.content,
                path=source_file.path,
            )
        )

    projection = _load_projection_module()
    report = projection.project_format(request, tuple(outcomes))
    _compact(projection.public_payload(report))

    return _exit_code(report.status)


def _schema_mode(args: argparse.Namespace, bindings: _Bindings) -> int:
    """Render one DTO-generated schema document.

    Args:
        args: Parsed launcher arguments selecting the schema.
        bindings: Runtime utility services.

    Returns:
        int: Zero after successful schema serialization.

    Raises:
        CliError: The selected generated schema is unavailable.
    """

    filenames = {
        "request": "request.schema.json",
        "result": "result.schema.json",
        "format": "format_result.schema.json",
        "error": "error_result.schema.json",
        "config": "config.schema.json",
        "model": "model_spec.schema.json",
    }
    selected_filename = filenames[args.schema]

    for snapshot in bindings.generate_schemas():
        if snapshot.filename == selected_filename:
            _compact(json.loads(snapshot.content))

            return 0

    raise CliError("requested schema is unavailable")


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one standalone evaluator operation.

    Args:
        argv: Optional command arguments; defaults to process arguments.

    Returns:
        int: Stable status-derived process exit code.
    """

    mode = "check"

    try:
        parser = _build_parser()
        args = parser.parse_args(argv)
        mode = args.mode
        bindings = _load_bindings()

        if args.mode == "schema":
            return _schema_mode(args, bindings)

        serialized_request = _request_from_paths(args)

        if args.mode == "format":
            return _format_mode(
                args=args,
                serialized_request=serialized_request,
                bindings=bindings,
            )

        return _evaluation_mode(
            args=args,
            serialized_request=serialized_request,
            bindings=bindings,
        )

    except Exception as error:
        recognized_errors = (
            _load_bindings().recognized_errors
            if not isinstance(error, CliError)
            else (CliError,)
        )

        if not isinstance(error, recognized_errors):
            raise

        projection = _load_projection_module()
        from src.domain.models import EvaluationStatus

        error_report = projection.ErrorReport(
            mode=mode,
            status=EvaluationStatus.BLOCKED,
            summary="Code quality evaluation failed before a result could be produced.",
        )
        _compact(projection.public_payload(error_report))

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
