# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Runtime service that coordinates Brain CLI parsing, dispatch, and error rendering.

Parses command-line arguments, evaluates authority permissions, and delegates
execution to action handlers or error formatting components.
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr
from typing import Final

from brain.application.authority.passwords import (
    PasswordInputError,
    read_password,
    read_password_from_stdin,
    verify_password,
)
from brain.application.authority.service import AuthorityService
from brain.application.memory.paths import BrainStoreError
from brain.presentation.commands.registry import COMMAND_MODULES
from brain.presentation.json_renderer import render_json
from brain.presentation.parser.services.argument_parser_service import (
    ARGUMENT_ERROR_MESSAGE,
    build_argument_parser,
)
from brain.presentation.parser.services.global_flags_service import (
    extract_global_flags,
)
from brain.presentation.router.services.command_router_service import (
    AUTHORITY_VERIFIED_ATTRIBUTE,
    dispatch_command,
)
from brain.presentation.terminal import ANSI_RED, ANSI_RESET

REQUIRED_AUTHORITY_MESSAGE: Final[str] = (
    "Required Command Authority flag  --authority <AUTHORITY> to execute scoped command"
)
REQUIRED_HELP_AUTHORITY_MESSAGE: Final[str] = (
    "Required Command Authority flag  --authority <UTHORITY> to read scoped help."
)
GENERIC_AUTHORITY_ERROR_MESSAGE: Final[str] = "Unable to evaluate command authority."
PASSWORD_STDIN_TTY_MESSAGE: Final[str] = (
    "Password input from stdin requires a non-interactive stream."
)
_PASSWORD_INPUT_ERRORS: Final[tuple[type[BaseException], ...]] = (
    AttributeError,
    EOFError,
    OSError,
    PasswordInputError,
    TypeError,
    ValueError,
)


def run_cli(argv: list[str] | None = None) -> int:
    """Parse arguments, execute selected action, and return process status.

    Extracts global presentation and authority flags, then checks permission
    before parsing so restricted help and password requests cannot bypass policy.
    Dispatches only an approved action and keeps failures on the safe CLI contract.

    Args:
        argv: Argument override, or None for process arguments.

    Returns:
        int: Process exit code.
    """
    raw_argv: list[str] = sys.argv[1:] if argv is None else argv
    (
        parsed_argv,
        color_enabled,
        verbose_log,
        authority,
        authority_provided,
        password_stdin,
    ) = extract_global_flags(argv=raw_argv)

    # Resolve the command before parsing so authority policy controls parser access.
    command_name = _resolve_preflight_command(argv=parsed_argv)
    json_mode = _json_requested(argv=parsed_argv)

    # Reject omitted or blank authority before parser or permission side effects.

    if not authority_provided or not authority.strip():
        # Preserve the dedicated read-scoped help wording for the help command.
        required_authority_message = (
            REQUIRED_HELP_AUTHORITY_MESSAGE
            if command_name == "help"
            else REQUIRED_AUTHORITY_MESSAGE
        )

        return _render_failure(
            command_name=command_name,
            message=required_authority_message,
            json_mode=json_mode,
            color_enabled=color_enabled,
        )

    decision = AuthorityService().evaluate_command_permission(
        command_name=command_name,
        authority=authority,
    )
    decision_status, decision_message, password_digest = _normalize_permission_decision(
        decision
    )

    # Stop denied commands before parser construction or handler dispatch.

    if decision_status == "deny":
        return _render_failure(
            command_name=command_name,
            message=decision_message or GENERIC_AUTHORITY_ERROR_MESSAGE,
            json_mode=json_mode,
            color_enabled=color_enabled,
    )

    # A password request without a configured digest cannot be approved safely.

    if decision_status == "request_password" and not password_digest:
        return _render_failure(
            command_name=command_name,
            message=decision_message or GENERIC_AUTHORITY_ERROR_MESSAGE,
            json_mode=json_mode,
            color_enabled=color_enabled,
    )

    # Treat unknown decision states as a fail-closed authority failure.

    if decision_status not in {"execute", "request_password"}:
        return _render_failure(
            command_name=command_name,
            message=GENERIC_AUTHORITY_ERROR_MESSAGE,
            json_mode=json_mode,
            color_enabled=color_enabled,
        )

    # Parse only after authority preflight so argparse help cannot bypass policy.
    parser = build_argument_parser(command_modules=COMMAND_MODULES)
    parser_diagnostics = io.StringIO()

    # Capture parser diagnostics because raw usage text can echo untrusted input.

    try:
        # Keep argparse diagnostics private until they become the stable error text.

        with redirect_stderr(parser_diagnostics):
            args = parser.parse_args(parsed_argv)

    # Convert argparse exits into the stable output contract without leaking details.

    except SystemExit as exc:
        # Help/version exits are successful; all other parser exits are redacted.

        if exc.code == 0:
            return 0

        return _render_failure(
            command_name=command_name,
            message=ARGUMENT_ERROR_MESSAGE,
            json_mode=json_mode,
            color_enabled=color_enabled,
        )

    args.color = color_enabled
    args.verbose_log = verbose_log
    args.authority = authority
    args.authority_provided = authority_provided

    setattr(args, AUTHORITY_VERIFIED_ATTRIBUTE, False)

    parsed_command_name = getattr(args, "command", None)

    # Prefer argparse's resolved command when it supplies a concrete subcommand.

    if isinstance(parsed_command_name, str) and parsed_command_name:
        command_name = parsed_command_name

    parsed_json_mode = getattr(args, "json", False)

    # Retain the post-parse denial guard as defense in depth for mutable decisions.

    if decision_status == "deny":
        return _render_failure(
            command_name=command_name,
            message=decision_message,
            json_mode=parsed_json_mode,
            color_enabled=color_enabled,
    )

    # Complete the password-request policy only after parser output mode is known.

    if decision_status == "request_password":
        # Recheck the digest after parsing so inconsistent decision data still fails closed.

        if not password_digest:
            return _render_failure(
                command_name=command_name,
                message=decision_message,
                json_mode=parsed_json_mode,
                color_enabled=color_enabled,
            )

        # Explicit stdin input is valid only from a noninteractive stream.

        if password_stdin and _stdin_is_tty():
            return _render_failure(
                command_name=command_name,
                message=PASSWORD_STDIN_TTY_MESSAGE,
                json_mode=parsed_json_mode,
                color_enabled=color_enabled,
            )

        candidate_password = _read_password_candidate(
            password_stdin=password_stdin,
            json_mode=parsed_json_mode,
            prompt=decision_message,
        )

        # Missing or unavailable input must never cross the protected dispatch boundary.

        if candidate_password is None:
            return _render_failure(
                command_name=command_name,
                message=decision_message,
                json_mode=parsed_json_mode,
                color_enabled=color_enabled,
        )

        # Verify the in-memory candidate without attaching it to the dispatch namespace.

        try:
            password_valid = verify_password(
                candidate_password,
                password_digest,
            )

        # Malformed verifier inputs are invalid credentials, never an access grant.

        except (TypeError, ValueError):
            password_valid = False

        # Release the local candidate reference immediately after verification.

        finally:
            del candidate_password

        # Only a successful password verification may authorize dispatch.

        if not password_valid:
            return _render_failure(
                command_name=command_name,
                message=_invalid_password_message(decision_message),
                json_mode=parsed_json_mode,
                color_enabled=color_enabled,
            )

    # Any status other than execute is rejected rather than interpreted permissively.

    elif decision_status != "execute":
        return _render_failure(
            command_name=command_name,
            message=GENERIC_AUTHORITY_ERROR_MESSAGE,
            json_mode=parsed_json_mode,
            color_enabled=color_enabled,
        )

    # Mark the namespace only after this boundary has completed local verification.
    setattr(args, AUTHORITY_VERIFIED_ATTRIBUTE, True)

    # Dispatch receives only a parsed namespace carrying the nonsecret verification marker.

    try:
        return dispatch_command(args=args)

    # Keep known storage failures on the same terminal or JSON error contract.

    except BrainStoreError as exc:
        return _render_failure(
            command_name=getattr(args, "command", None) or "help",
            message=str(exc),
            json_mode=parsed_json_mode,
            color_enabled=color_enabled,
        )


def _normalize_permission_decision(
    decision: object,
) -> tuple[str, str, str]:
    """Normalize typed authority decisions and their legacy two-value view.

    Keeps the runtime compatible with established tuple responses while
    preserving password metadata from the typed security decision contract.
    Malformed decision shapes become a fail-closed status before any dispatch.

    Args:
        decision: AuthorityDecision instance or historical execute/message pair.

    Returns:
        tuple[str, str, str]: Status, safe message, and password digest.
        Malformed decisions become a fail-closed denial without exposing data.
    """
    decision_status = getattr(decision, "status", None)

    # Prefer the typed decision because it carries explicit password metadata.

    if isinstance(decision_status, str):
        decision_message = getattr(decision, "message", "")
        password_digest = getattr(decision, "password_digest", "")

        # Normalize malformed messages so renderers receive only safe text.

        if not isinstance(decision_message, str):
            decision_message = ""

        # Discard malformed digests so password requests fail closed.

        if not isinstance(password_digest, str):
            password_digest = ""

        return decision_status, decision_message, password_digest

    # Accept legacy tuples only at this compatibility boundary.

    try:
        allowed, decision_message = decision  # type: ignore[misc]

    # Malformed authority responses cannot safely authorize a command.

    except (TypeError, ValueError):
        return "invalid", GENERIC_AUTHORITY_ERROR_MESSAGE, ""

    # Normalize legacy messages before they reach terminal or JSON rendering.

    if not isinstance(decision_message, str):
        decision_message = ""

    decision_status = "execute" if bool(allowed) else "deny"

    return decision_status, decision_message, ""


def _read_password_candidate(
    password_stdin: bool,
    json_mode: bool,
    prompt: str,
) -> str | None:
    """Read one password through the explicitly permitted secure channel.

    Selects either the noninteractive stdin channel or a hidden TTY prompt
    according to the caller's mode, and never returns input in JSON/non-TTY mode.
    Input errors are converted to no candidate so protected commands fail closed.

    Args:
        password_stdin: Whether --password-stdin was supplied globally.
        json_mode: Whether the command requested machine-readable output.
        prompt: Configured request text used only for hidden terminal input.

    Returns:
        str | None: The candidate password, or None when input is unavailable or
        violates the bounded input contract.
    """

    # The explicit stdin protocol is the only allowed noninteractive input path.

    if password_stdin:
        # Reject TTY stdin so a pipe-only channel cannot be confused with a prompt.

        if _stdin_is_tty():
            return None

        # Read exactly through the dedicated stdin helper and retain no parser field.

        try:
            return read_password_from_stdin()

        # Any input failure denies the request without exposing implementation details.

        except _PASSWORD_INPUT_ERRORS:
            return None

    # JSON output and noninteractive stdin must never trigger a hidden prompt.

    if json_mode or not _stdin_is_tty():
        return None

    # Use hidden terminal input only for an interactive, non-JSON request.

    try:
        return read_password(prompt=prompt)

    # Treat unavailable terminal input as an unapproved request.

    except _PASSWORD_INPUT_ERRORS:
        return None


def _stdin_is_tty() -> bool:
    """Return whether standard input is an available interactive terminal.

    Centralizes the capability check used by password transport guards so
    unusual or closed stdin implementations resolve to the safe non-TTY state.

    Args:
        None.

    Returns:
        bool: True only when sys.stdin exposes a callable isatty method that
        reports an interactive terminal.
    """

    # Probe stdin defensively because test doubles and closed streams may be partial.

    try:
        isatty = sys.stdin.isatty

        return bool(isatty())

    # Any capability or stream error must not enable interactive password input.

    except (AttributeError, OSError, TypeError, ValueError):
        return False


def _invalid_password_message(request_message: str) -> str:
    """Build a safe wrong-password response retaining request context.

    Keeps the configured request context useful to the caller while excluding
    the candidate password and preserving the existing terminal/JSON wording.

    Args:
        request_message: Configured request text and optional postfix.

    Returns:
        str: Safe invalid-password text with the original request context.
    """

    # Use a stable standalone message when the authority service supplied no context.

    if not request_message:
        return "Invalid password."

    return f"Invalid password. {request_message}"


def _render_failure(
    command_name: str,
    message: str,
    json_mode: bool,
    color_enabled: bool,
) -> int:
    """Render one failure without exposing authority or password internals.

    Centralizes terminal and JSON failure output so early authority checks,
    parser failures, password failures, and storage errors share one safe contract.

    Args:
        command_name: Canonical command name associated with the failure.
        message: Safe user-facing decision or runtime message.
        json_mode: Whether to emit the JSON error contract.
        color_enabled: Whether terminal presentation should use ANSI colors.

    Returns:
        int: Failure exit status, always one.
    """

    # JSON callers receive a machine-readable payload without parser diagnostics.

    if json_mode:
        payload = {
            "ok": False,
            "command": command_name,
            "error": message,
        }

        print(render_json(payload=payload, color_enabled=color_enabled))

        return 1

    # Terminal callers receive the established error wording and optional color.

    if color_enabled:
        print(f"{ANSI_RED}Error: {message}{ANSI_RESET}", file=sys.stderr)

    else:
        print(f"Error: {message}", file=sys.stderr)

    return 1


def _json_requested(argv: list[str]) -> bool:
    """Return whether the raw command vector requests JSON error output safely.

    Detects the output mode before argparse so authority failures can preserve
    the JSON contract even when parsing is intentionally skipped.

    Args:
        argv: Global-flag-cleaned command-line tokens.

    Returns:
        bool: True when a canonical JSON switch is present.
    """

    return any(argument in ("-j", "--json") for argument in argv)


def _resolve_preflight_command(argv: list[str]) -> str:
    """Resolve the command identity without invoking argparse.

    Scans the cleaned argument vector before parser construction so permission
    checks can identify a command while keeping help and malformed input guarded.

    Args:
        argv: Global-flag-cleaned command-line tokens.

    Returns:
        str: Canonical command name, or help when no command was supplied.
    """

    # Preserve left-to-right CLI precedence for the first command-like token.

    for argument in argv:
        # Help is a command-level request whose authority wording is specialized.

        if argument in ("-h", "--help"):
            return "help"

        # Global options are not command identities and must not affect preflight.

        if argument.startswith("-"):
            continue

        return _canonical_command_name(command_candidate=argument)

    return "help"


def _canonical_command_name(command_candidate: str) -> str:
    """Map one command name or alias to the registered canonical name.

    Resolves aliases against the same command registry used by argparse so
    permission evaluation and dispatch address one stable command identity.

    Args:
        command_candidate: First non-option token from the raw command vector.

    Returns:
        str: Registered canonical name, or the original candidate for unknown input.
    """

    # Use the registered schema as the single source of command identity truth.

    for command_module in COMMAND_MODULES:
        command_schema = command_module.SCHEMA

        # Exact schema names already have canonical identity.

        if command_candidate == command_schema.name:
            return command_schema.name

        # Aliases must resolve before permission evaluation to avoid policy drift.

        if command_candidate in command_schema.aliases:
            return command_schema.name

    return command_candidate
