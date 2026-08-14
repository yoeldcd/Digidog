# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Route parsed CLI commands through authorization and presentation policies.

Revalidates authority before handler lookup so security failures cannot disclose
command registration details or invoke an unauthorized action.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from typing import Final, TypeAlias, cast

from brain.application.authority.service import AuthorityService
from brain.application.memory.paths import BrainStoreError
from brain.infrastructure.avatar.configuration.avatar_config import load_avatar_config
from brain.infrastructure.voice.messaging.voice_signals import VoiceSignalService
from brain.presentation.actions.registry import get_action_handler
from brain.presentation.json_renderer import render_json
from brain.presentation.router.services.command_show_policy import (
    CommandShowPolicy,
    command_show_policy,
)
from brain.presentation.router.services.narration_policy import (
    CommandNarration,
    narration_for,
)

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list['JsonValue'] | dict[str, 'JsonValue']

REQUIRED_AUTHORITY_MESSAGE: Final[str] = (
    "Required Command Authority flag  --authority <AUTHORITY> to execute scoped command"
)
REQUIRED_HELP_AUTHORITY_MESSAGE: Final[str] = (
    "Required Command Authority flag  --authority <UTHORITY> to read scoped help."
)
GENERIC_AUTHORITY_ERROR_MESSAGE: Final[str] = "Unable to evaluate command authority."
AUTHORITY_VERIFIED_ATTRIBUTE: Final[str] = "authority_verified"


class _MirroredCapture(io.TextIOBase):
    """Mirror command output while retaining a narration-review copy.

    Keeps terminal behavior unchanged while allowing the router to analyze output
    for post-execution voice feedback without redirecting or duplicating writes.
    """

    def __init__(self, target: io.TextIOBase, capture: io.StringIO) -> None:
        """Initialize a mirror that preserves terminal writes for narration review.

        Retains the original stream as the write destination and a separate buffer
        for post-execution inspection, preserving output ordering and destination semantics.

        Args:
            target: Original CLI stream that continues to receive output.
            capture: Buffer that retains output for narration review.
        """
        self._target = target
        self._capture = capture

    def write(self, text: str) -> int:
        """Mirror one output fragment while retaining the same text for review.

        Writes to the capture first so narration sees the exact fragment before
        forwarding it to the original stream, preserving caller-visible character order.

        Args:
            text: Captured CLI output fragment.

        Returns:
            int: Characters written to the original stream.
        """
        self._capture.write(text)

        return self._target.write(text)

    def flush(self) -> None:
        """Flush the underlying CLI stream after mirrored output has been forwarded.

        Delegates flushing to the original target so buffered terminal output retains
        its existing lifecycle while the capture remains an in-memory review record.

        Args:
            None.

        Returns:
            None.
        """

        self._target.flush()


def dispatch_command(args: argparse.Namespace) -> int:
    """Authorize, resolve, and execute the action selected by parsed arguments.

    Rechecks authority before handler lookup and coordinates terminal or JSON
    presentation, narration, and task synchronization without changing handler output.

    Args:
        args: Parsed CLI arguments.

    Returns:
        int: Handler process exit code.

    Raises:
        BrainStoreError: If the requested command has no registered handler.
    """
    authority_failure = _revalidate_authority(args=args)

    # Authorization boundary: fail before handler lookup to avoid unauthorized execution or disclosure.

    if authority_failure is not None:
        return _render_authority_failure(args=args, message=authority_failure)

    command_name = _command_name(args)
    action_handler = get_action_handler(command_name=command_name)

    # Registry boundary: preserve the established unknown-command error after authorization succeeds.

    if action_handler is None:
        raise BrainStoreError(f"Unknown command: {command_name}")

    # Presentation boundary: route machine-readable calls through the single-document path.

    if getattr(args, "json", False):
        return _dispatch_json(
            command_name=command_name,
            action_handler=action_handler,
            args=args,
        )

    voice_service = VoiceSignalService()
    show_policy, narration = _resolve_presentation_policy(command_name, args)

    # Silent path: run the handler directly when no narration side effect is selected.

    if narration is None:
        exit_code = action_handler(args)
        _sync_successful_task(voice_service, command_name, args, exit_code)

        return exit_code

    _emit_start_review(
        voice_service=voice_service,
        command_name=command_name,
        narration=narration,
        args=args,
        show_policy=show_policy,
    )
    captured = io.StringIO()

    # Review transaction: capture failures and output so narration reflects the original command attempt.

    try:

        # Stream mirror: preserve terminal writes while collecting output for the review service.

        with (
            redirect_stdout(_MirroredCapture(sys.stdout, captured)),
            redirect_stderr(_MirroredCapture(sys.stderr, captured)),
        ):
            exit_code = action_handler(args)

    # Exception review: report captured failure context before re-raising the original exception.

    except Exception as exc:
        _emit_output_review(
            voice_service=voice_service,
            command_name=command_name,
            narration=narration,
            args=args,
            output=captured.getvalue(),
            succeeded=False,
            cause=str(exc),
            show_policy=show_policy,
        )

        raise

    _sync_successful_task(voice_service, command_name, args, exit_code)
    captured_output = captured.getvalue()
    narration_output = getattr(args, "narration_output", captured_output)
    failure_cause = _failure_cause(captured_output, exit_code)
    _emit_output_review(
        voice_service=voice_service,
        command_name=command_name,
        narration=narration,
        args=args,
        output=narration_output,
        succeeded=exit_code == 0,
        cause=failure_cause,
        show_policy=show_policy,
    )

    return exit_code


def _dispatch_json(
    command_name: str,
    action_handler: Callable[[argparse.Namespace], int],
    args: argparse.Namespace,
) -> int:
    """Run a handler while converting its stdout into one semantic JSON document.

    Captures action output before rendering to prevent incidental text from breaking
    the JSON boundary, while preserving raw-document and task-synchronization behavior.

    Args:
        command_name: Registered name of the action being executed.
        action_handler: Function that executes the parsed action arguments.
        args: Parsed CLI arguments.

    Returns:
        int: Handler process exit code, or one for synthesized JSON failures.
    """
    voice_service = VoiceSignalService()
    show_policy, narration = _resolve_presentation_policy(command_name, args)
    _emit_start_review(
        voice_service=voice_service,
        command_name=command_name,
        narration=narration,
        args=args,
        show_policy=show_policy,
    )
    captured = io.StringIO()

    # Review transaction: retain handler output so JSON and narration share one execution result.

    try:

        # JSON capture: isolate handler stdout before constructing the final machine document.

        with redirect_stdout(captured):
            exit_code = action_handler(args)

    # Exception review: preserve the original exception after recording any captured output.

    except Exception as exc:

        # Review safety: send a failure signal only when narration was selected.

        if narration:
            _emit_output_review(
                voice_service=voice_service,
                command_name=command_name,
                narration=narration,
                args=args,
                output=captured.getvalue(),
                succeeded=False,
                cause=str(exc),
                show_policy=show_policy,
            )

        raise

    output = captured.getvalue()

    # Raw-output contract: bypass JSON synthesis for handlers returning document text.

    if getattr(args, "raw_document_output", False):
        print(output, end="")
        _sync_successful_task(voice_service, command_name, args, exit_code)

        return exit_code

    payload, has_semantic_payload = _resolve_json_payload(
        args,
        command_name,
        output,
        exit_code,
    )
    print(render_json(payload=payload, color_enabled=getattr(args, "color", False)))

    # JSON contract: convert successful nonsemantic output into a stable failure envelope.

    if not has_semantic_payload:
        return 1 if exit_code == 0 else exit_code

    _sync_successful_task(voice_service, command_name, args, exit_code)

    # Output review: narrate only the semantic payload path that completed dispatch.

    if narration:
        narration_output = getattr(args, "narration_output", output)
        failure_cause = _failure_cause(_plain_text(output), exit_code)
        _emit_output_review(
            voice_service=voice_service,
            command_name=command_name,
            narration=narration,
            args=args,
            output=narration_output,
            succeeded=exit_code == 0,
            cause=failure_cause,
            show_policy=show_policy,
        )

    return exit_code


def _command_name(args: argparse.Namespace) -> str:
    """Normalize the command identity used by authorization and dispatch.

    Returns the explicit nonempty command when present; otherwise selects help so
    missing command input follows the router's existing read-path behavior.

    Args:
        args: Parsed CLI arguments that may omit a command name.

    Returns:
        str: Requested command name or ``"help"`` when omitted.
    """
    command_name = getattr(args, "command", None)

    # Command identity: preserve explicit parser output while rejecting empty values.

    if isinstance(command_name, str) and command_name:
        return command_name

    return "help"


def _revalidate_authority(args: argparse.Namespace) -> str | None:
    """Recheck command authority at the final dispatch boundary before execution.

    Rejects missing or unverified authority and normalizes service decisions to safe
    statuses, failing closed so handler lookup cannot become an authorization bypass.

    Args:
        args: Parsed CLI namespace carrying the explicit authority context and
            the nonsecret password-verification marker.

    Returns:
        str | None: Safe failure text, or None when dispatch is authorized.
    """

    command_name = _command_name(args)

    # Authority invariant: explicit presence is required before any policy evaluation.

    if getattr(args, "authority_provided", None) is not True:
        return _required_authority_message(command_name=command_name)

    authority = getattr(args, "authority", None)

    # Input boundary: reject blank or non-text authorities to keep matching fail-closed.

    if not isinstance(authority, str) or not authority.strip():
        return _required_authority_message(command_name=command_name)

    # Verification invariant: only the runtime's nonsecret success marker may authorize recheck.

    if getattr(args, AUTHORITY_VERIFIED_ATTRIBUTE, False) is not True:
        return GENERIC_AUTHORITY_ERROR_MESSAGE

    # Policy boundary: delegate command-specific permission evaluation to the authority service.

    try:
        decision = AuthorityService().evaluate_command_permission(
            command_name=command_name,
            authority=authority,
        )

    # Fail-closed guard: infrastructure or malformed-decision errors never grant dispatch.

    except (OSError, RuntimeError, TypeError, ValueError):
        return GENERIC_AUTHORITY_ERROR_MESSAGE

    decision_status, _ = _normalize_authority_decision(decision=decision)

    # Decision gate: permit only statuses already approved by the runtime password protocol.

    if decision_status in {"execute", "request_password"}:

        # Reverification guard: require the marker again before crossing into handler lookup.

        if getattr(args, AUTHORITY_VERIFIED_ATTRIBUTE, False) is True:
            return None

        return GENERIC_AUTHORITY_ERROR_MESSAGE

    return GENERIC_AUTHORITY_ERROR_MESSAGE


def _required_authority_message(command_name: str) -> str:
    """Select the safe missing-authority message for the command policy category.

    Keeps help/read failures distinct from execution failures without exposing
    authority-evaluation details or invoking command-specific code.

    Args:
        command_name: Canonical command name selected by the router.

    Returns:
        str: Help-specific read message, or the generic execute message.
    """

    # Message policy: preserve dedicated help guidance for read-path authority failures.

    if command_name == "help":
        return REQUIRED_HELP_AUTHORITY_MESSAGE

    return REQUIRED_AUTHORITY_MESSAGE


def _normalize_authority_decision(decision: object) -> tuple[str, str]:
    """Convert current or legacy authority results into a safe status/message pair.

    Accepts typed decisions and historical iterable results so the router can fail
    closed on malformed data without propagating unstable decision representations.

    Args:
        decision: Authority decision object or legacy boolean/message pair.

    Returns:
        tuple[str, str]: Normalized status and safe decision message.
    """

    decision_status = getattr(decision, "status", None)

    # Typed decision path: preserve the service status and only a string message.

    if isinstance(decision_status, str):
        decision_message = getattr(decision, "message", "")

        # Output safety: discard malformed decision messages instead of exposing arbitrary values.

        if not isinstance(decision_message, str):
            decision_message = ""

        return decision_status, decision_message

    # Compatibility path: accept the historical pair while retaining a fail-closed fallback.

    try:
        allowed, decision_message = decision

    # Malformed-decision guard: classify unpacking failures as invalid, never executable.

    except (TypeError, ValueError):
        return "invalid", ""

    # Output safety: coerce non-text legacy details to an empty safe message.

    if not isinstance(decision_message, str):
        decision_message = ""

    decision_status = "execute" if allowed is True else "deny"

    return decision_status, decision_message


def _render_authority_failure(args: argparse.Namespace, message: str) -> int:
    """Render an authorization failure without resolving or invoking a handler.

    Uses the established terminal or JSON response shape and a constant failure
    status, keeping denial output observable while preventing command dispatch.

    Args:
        args: Parsed CLI namespace carrying output and command settings.
        message: Safe failure text selected by the router authorization gate.

    Returns:
        int: Failure exit status, always one.
    """

    command_name = _command_name(args)

    # Machine-output contract: return one structured failure document without invoking a handler.

    if getattr(args, "json", False):
        payload = {
            "ok": False,
            "command": command_name,
            "error": message,
        }
        print(render_json(payload=payload, color_enabled=getattr(args, "color", False)))

        return 1

    # Terminal presentation: add ANSI color only when explicitly requested by the caller.

    if getattr(args, "color", False):
        print(f"\033[31mError: {message}\033[0m", file=sys.stderr)

    # Plain terminal presentation: keep the failure text unchanged for non-color callers.

    else:
        print(f"Error: {message}", file=sys.stderr)

    return 1


def _resolve_presentation_policy(
    command_name: str,
    args: argparse.Namespace,
) -> tuple[CommandShowPolicy | None, CommandNarration | None]:
    """Select command presentation policy and narration before handler execution.

    Honors no-speak and unavailable-policy gates so voice side effects remain isolated
    from command behavior and protected output is reviewed only when permitted.

    Args:
        command_name: Registered name of the action being executed.
        args: Parsed CLI arguments that control speech suppression.

    Returns:
        tuple[CommandShowPolicy | None, CommandNarration | None]: Command
        show policy and narration, or two ``None`` values when speech is
        suppressed or unavailable.
    """

    # Side-effect policy: honor explicit silence before loading avatar configuration.

    if getattr(args, "no_speak", False):
        return None, None

    show_policy = command_show_policy(command_name, load_avatar_config())

    # Availability policy: stop before narration lookup when the command has no show rule.

    if show_policy is None:
        return None, None

    narration = narration_for(command=command_name, args=args)

    return show_policy, narration


def _emit_start_review(
    voice_service: VoiceSignalService,
    command_name: str,
    narration: CommandNarration | None,
    args: argparse.Namespace,
    show_policy: CommandShowPolicy | None,
) -> None:
    """Emit the optional call-phase review after presentation policy resolution.

    Skips voice emission when narration or its announcement flag is absent, keeping
    silent commands free of unintended external signaling.

    Args:
        voice_service: Service that sends reviewed voice signals.
        command_name: Registered name of the action being executed.
        narration: Optional narration selected for the command.
        args: Parsed CLI arguments forwarded to the voice service.
        show_policy: Optional presentation policy that permits the narration.

    Returns:
        None.
    """

    # Announcement gate: avoid call-phase signaling unless policy explicitly requests it.

    if narration is None or not narration.announce_start:
        return

    voice_service.emit_reviewed(
        command=command_name,
        phase="call",
        narration=narration,
        args=args,
        show_policy=show_policy,
    )


def _emit_output_review(
    voice_service: VoiceSignalService,
    command_name: str,
    narration: CommandNarration,
    args: argparse.Namespace,
    output: str,
    succeeded: bool,
    cause: str,
    show_policy: CommandShowPolicy | None,
) -> None:
    """Emit the post-execution review from captured command outcome details.

    Passes selected output, success state, and failure cause to the voice service
    so narration reflects actual execution without re-running the handler.

    Args:
        voice_service: Service that sends reviewed voice signals.
        command_name: Registered name of the action being executed.
        narration: Narration selected for the command.
        args: Parsed CLI arguments forwarded to the voice service.
        output: Captured or overridden command output for the review.
        succeeded: Whether command execution completed successfully.
        cause: Failure explanation, or an empty string after success.
        show_policy: Optional presentation policy that permits the narration.

    Returns:
        None.
    """

    voice_service.emit_reviewed(
        command=command_name,
        phase="output",
        narration=narration,
        args=args,
        output=output,
        succeeded=succeeded,
        cause=cause,
        show_policy=show_policy,
    )


def _sync_successful_task(
    voice_service: VoiceSignalService,
    command_name: str,
    args: argparse.Namespace,
    exit_code: int,
) -> None:
    """Synchronize task state only for handlers reporting successful completion.

    The exit-code guard prevents failed or denied actions from mutating task state,
    while leaving synchronization ownership with the voice service.

    Args:
        voice_service: Service that synchronizes task state.
        command_name: Registered name of the action being executed.
        args: Parsed CLI arguments forwarded to the voice service.
        exit_code: Process exit code returned by the action handler.

    Returns:
        None.
    """

    # Task-state invariant: failed handlers must not trigger successful-task synchronization.

    if exit_code != 0:
        return

    voice_service.sync_task_state(command_name, args)


def _resolve_json_payload(
    args: argparse.Namespace,
    command_name: str,
    output: str,
    exit_code: int,
) -> tuple[JsonValue, bool]:
    """Choose a semantic JSON payload or construct the router's failure envelope.

    Prefers valid handler JSON and explicit payload arguments, then normalizes text
    and exit status into a stable error object without altering handler execution.

    Args:
        args: Parsed CLI arguments that may hold a semantic JSON payload.
        command_name: Registered name of the action being executed.
        output: Captured standard output from the action handler.
        exit_code: Process exit code returned by the action handler.

    Returns:
        tuple[JsonValue, bool]: Renderable payload and whether it was
        supplied by the handler or action arguments rather than synthesized
        after failure.
    """

    # Handler payload preference: preserve valid semantic JSON emitted by the command.

    if _is_json_document(output):
        return cast(JsonValue, json.loads(output)), True

    # Argument payload preference: retain an explicit semantic payload when stdout is non-JSON.

    if hasattr(args, "json_payload"):
        return cast(JsonValue, args.json_payload), True

    error_message = _plain_text(output).strip()

    # Error-envelope policy: replace diagnostic text on nominal success with a deterministic message.

    if exit_code == 0:
        error_message = "Command did not provide a semantic JSON payload."

    return (
        {
            "ok": False,
            "command": command_name,
            "error": error_message or "Command failed without an error description.",
        },
        False,
    )


def _failure_cause(output: str, exit_code: int) -> str:
    """Derive a concise failure cause from captured output and exit status.

    Suppresses cause text for successful actions and supplies a deterministic
    fallback when a failing handler produced no diagnostic output.

    Args:
        output: Captured command output that may explain a failure.
        exit_code: Process exit code returned by the action handler.

    Returns:
        str: Empty text after success, otherwise output text or an exit-code note.
    """

    # Success invariant: successful commands do not narrate a failure cause.

    if exit_code == 0:
        return ""

    return output.strip() or f"exit code {exit_code}"


def _is_json_document(output: str) -> bool:
    """Check whether captured output is nonempty and decodes as one JSON document.

    Uses the standard decoder as the router's semantic-boundary check so non-JSON
    diagnostics can be wrapped instead of emitted as invalid JSON.

    Args:
        output: Captured standard output to validate.

    Returns:
        bool: Whether the output can be decoded as a JSON document.
    """

    # Empty-output guard: blank stdout cannot satisfy the semantic JSON contract.

    if not output.strip():
        return False

    # Decode gate: validate the entire captured stream before treating it as semantic output.

    try:
        json.loads(output)

    # Diagnostic path: invalid JSON remains a nonsemantic result for envelope synthesis.

    except json.JSONDecodeError:
        return False

    return True


def _plain_text(output: str) -> str:
    """Remove terminal ANSI sequences from a captured error message.

    Args:
        output: Text that may contain ANSI terminal control sequences.

    Returns:
        str: Output text with ANSI terminal control sequences removed.
    """

    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
