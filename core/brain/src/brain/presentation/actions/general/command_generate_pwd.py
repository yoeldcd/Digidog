"""Execute the user-only generate-pwd command without exposing its input.

The action accepts secret material only through shared hidden or stdin readers,
then publishes a SHA-256 digest while keeping plaintext out of output and narration.
"""

from __future__ import annotations

import argparse
import sys
from typing import Final

from brain.application.authority.passwords import (
    PasswordInputError,
    hash_password,
    read_password,
    read_password_from_stdin,
)


COMMAND_NAME: Final[str] = "generate-pwd"
AUTHORITY_ERROR: Final[str] = "generate-pwd requires exact --authority user."
JSON_INPUT_ERROR: Final[str] = "JSON mode requires --stdin."
INPUT_ERROR: Final[str] = "Password input was rejected."
NON_INTERACTIVE_INPUT_ERROR: Final[str] = (
    "Hidden password input requires an interactive standard input stream."
)


def _read_source(args: argparse.Namespace) -> str:
    """Select a safe password source for the command's execution mode.

    The explicit stdin path supports automation, while JSON mode and non-interactive
    terminals fail closed so a secret is never requested through an unsafe channel.

    Args:
        args: Parsed command flags controlling the input source and output mode.

    Returns:
        str: Unmodified, non-empty source text.

    Raises:
        PasswordInputError: If stdin input is unavailable, empty, multiline, or
            JSON mode would otherwise need to prompt.
    """

    # Input-source precedence: explicit stdin is the only automation-safe channel.

    if getattr(args, "stdin", False):
        return read_password_from_stdin()

    # JSON safety boundary: machine-readable mode must not trigger a hidden prompt.

    if getattr(args, "json", False):
        raise PasswordInputError(JSON_INPUT_ERROR)

    # Interactive-input boundary: hidden reads require a terminal that can protect input.

    if not _stdin_is_tty():
        raise PasswordInputError(NON_INTERACTIVE_INPUT_ERROR)

    return read_password()


def _stdin_is_tty() -> bool:
    """Probe whether hidden input can be requested from the current standard input.

    The probe treats missing, invalid, or unusable stream APIs as non-interactive,
    providing a fail-closed signal before any secret reader is invoked.

    Args:
        None.

    Returns:
        bool: True only when ``sys.stdin`` exposes a callable ``isatty`` method
        that reports an interactive terminal.
    """

    # Terminal capability probe: determine whether hidden input can be requested safely.

    try:
        isatty = sys.stdin.isatty

        return bool(isatty())

    # Fail-closed fallback: treat any unusable terminal API as non-interactive.

    except (AttributeError, OSError, TypeError, ValueError):
        return False


def _fail(args: argparse.Namespace, message: str) -> int:
    """Build a redacted failure result for a rejected command or secret input.

    The helper keeps machine-readable and terminal channels aligned while clearing
    narration, so fixed diagnostics cannot accidentally echo sensitive source text.

    Args:
        args: Parsed command namespace receiving the machine-readable payload.
        message: Fixed, source-redacted failure explanation.

    Returns:
        int: Nonzero command status.
    """

    args.json_payload = {
        "ok": False,
        "command": COMMAND_NAME,
        "error": message,
    }
    args.narration_output = ""

    # Output-mode boundary: terminal diagnostics are emitted only outside JSON payload mode.

    if not getattr(args, "json", False):
        print(f"Error: {message}", file=sys.stderr)

    return 1


def handle(args: argparse.Namespace) -> int:
    """Coordinate authorization, safe input collection, hashing, and digest output.

    The exact user-only guard and broad input-failure boundary fail closed; successful
    paths publish only the digest and deliberately suppress narration of source text.

    Args:
        args: Parsed command flags including the exact caller authority.

    Returns:
        int: Zero when the digest is generated; one for a safe denial or input
            failure.
    """

    # Authority boundary: only the exact user authority may create password digests.

    if getattr(args, "authority", None) != "user":
        return _fail(args, AUTHORITY_ERROR)

    # Secret-processing boundary: source acquisition and hashing share a redacted failure path.

    try:
        source_text = _read_source(args)
        digest = hash_password(source_text)

    # Failure containment: convert every input or hashing error into a generic diagnostic.

    except Exception:
        return _fail(args, INPUT_ERROR)

    args.json_payload = {
        "ok": True,
        "command": COMMAND_NAME,
        "hash": digest,
    }
    args.narration_output = ""

    # Output-mode boundary: terminal mode prints only the digest; JSON mode keeps payload-only output.

    if not getattr(args, "json", False):
        print(digest)

    return 0
