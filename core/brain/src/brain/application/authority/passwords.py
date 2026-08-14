# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Provide password hashing and strictly bounded password-input helpers.

Keep plaintext handling at local input boundaries, enforce digest formatting before
comparison, and preserve exact input framing so callers can authorize without exposing secrets.
"""

from __future__ import annotations

import getpass
import hashlib
import hmac
import re
import sys
from typing import Callable, Final, Pattern, TextIO, TypeAlias


PasswordReader: TypeAlias = Callable[[str], str]

DEFAULT_PASSWORD_PROMPT: Final[str] = "Password: "
_HEX_DIGEST_PATTERN: Final[Pattern[str]] = re.compile(r"[0-9a-f]{64}")

__all__ = [
    "DEFAULT_PASSWORD_PROMPT",
    "PasswordInputError",
    "PasswordReader",
    "hash_password",
    "read_password",
    "read_password_from_stdin",
    "verify_password",
]


class PasswordInputError(ValueError):
    """Represent rejected password payloads at an input boundary.

    Distinguish empty or structurally invalid secret input from unrelated value errors,
    so callers can fail closed without trimming, logging, or exposing the rejected value.
    """


def hash_password(password: str) -> str:
    """Return the lowercase UTF-8 SHA-256 digest for one password string.

    Provide the deterministic digest representation required by the authority configuration
    contract while keeping the source password confined to the caller's local boundary.

    Args:
        password: Password text to encode as UTF-8 and hash.

    Returns:
        str: The 64-character lowercase hexadecimal SHA-256 digest.

    Raises:
        TypeError: If password is not a string.
    """

    # Input boundary: reject non-string values before any secret encoding or digest computation.

    if not isinstance(password, str):
        raise TypeError("password must be a string")

    encoded_password = password.encode("utf-8")
    password_digest = hashlib.sha256(encoded_password)

    return password_digest.hexdigest()


def verify_password(password: str, expected_digest: str) -> bool:
    """Constant-time compare a password with a strictly formatted digest.

    Validate the digest shape before hashing and compare only accepted lowercase hexadecimal
    values so malformed configuration fails closed without exposing comparison details.

    Args:
        password: Candidate password text to hash as UTF-8.
        expected_digest: Expected lowercase 64-character hexadecimal digest.

    Returns:
        bool: True only when the digest is well-formed and matches the password.
        False for malformed digests, non-string candidates, or mismatches.
    """

    # Candidate boundary: malformed types must fail closed without invoking hashing.

    if not isinstance(password, str):
        return False

    # Configuration boundary: only canonical lowercase SHA-256 digests may reach comparison.

    if not _is_valid_digest(expected_digest):
        return False

    actual_digest = hash_password(password)

    return hmac.compare_digest(actual_digest, expected_digest)


def read_password(
    getpass_reader: PasswordReader | None = None,
    prompt: str = DEFAULT_PASSWORD_PROMPT,
) -> str:
    """Read one non-empty password through an injectable hidden reader.

    Resolve the default reader at call time and return the exact text supplied by the input
    boundary, preserving whitespace and keeping prompt handling outside this helper's policy.

    Args:
        getpass_reader: Callable receiving the prompt and returning hidden input.
            When omitted, getpass.getpass is selected at call time.
        prompt: Prompt passed to the hidden reader.

    Returns:
        str: The unmodified non-empty password returned by the reader.

    Raises:
        PasswordInputError: If the reader returns an empty string.
        TypeError: If prompt or the reader result is not a string.
    """

    # Prompt contract: reject invalid prompt types before invoking an external reader.

    if not isinstance(prompt, str):
        raise TypeError("prompt must be a string")

    reader = getpass_reader

    # Reader selection: resolve the hidden default lazily so injected readers remain testable.

    if reader is None:
        reader = getpass.getpass

    password = reader(prompt)

    return _require_non_empty(password, "hidden")


def read_password_from_stdin(stdin: TextIO | None = None) -> str:
    """Read exactly one non-empty password line from standard input.

    Strip only one terminal line ending and reject embedded or extra line material so a
    noninteractive authorization channel cannot silently accept ambiguous framing.

    Args:
        stdin: Text stream to read, or None to use sys.stdin at call time.

    Returns:
        str: The password without one terminal LF, CRLF, or CR line ending.

    Raises:
        PasswordInputError: If input is empty or contains additional line material.
        TypeError: If the stream does not return text.
    """

    input_stream = stdin

    # Stream selection: resolve sys.stdin at call time so callers can inject a controlled source.

    if input_stream is None:
        input_stream = sys.stdin

    raw_input = input_stream.read()

    # Transport contract: reject non-text stream output before line framing is inspected.

    if not isinstance(raw_input, str):
        raise TypeError("stdin must provide text")

    password = _remove_terminal_line_ending(raw_input)

    # Framing boundary: reject embedded or additional line endings instead of choosing one secret.

    if "\n" in password or "\r" in password:
        raise PasswordInputError("stdin password must contain exactly one line")

    return _require_non_empty(password, "stdin")


def _is_valid_digest(digest: object) -> bool:
    """Return whether a value is exactly one lowercase SHA-256 hex digest.

    Use a strict shape check before constant-time comparison so malformed or mixed-case
    configuration values fail closed rather than reaching the authorization comparison.

    Args:
        digest: Candidate digest value supplied to the verification boundary.

    Returns:
        bool: True only for exactly 64 lowercase hexadecimal characters.
    """

    # Type boundary: non-string values cannot satisfy the exact digest representation.

    if not isinstance(digest, str):
        return False

    return _HEX_DIGEST_PATTERN.fullmatch(digest) is not None


def _remove_terminal_line_ending(value: str) -> str:
    """Remove at most one conventional terminal line ending from text.

    Preserve all other characters, including whitespace and embedded line breaks, so input
    framing is validated by the caller instead of normalized into an accepted secret.

    Args:
        value: Complete text payload read from the input stream.

    Returns:
        str: Text with one terminal LF, CRLF, or CR removed when present.
    """

    # CRLF precedence: consume the two-character form before single-character endings.

    if value.endswith("\r\n"):
        return value[:-2]

    # Single-ending rule: remove at most one LF or CR and preserve all other payload text.

    if value.endswith("\n") or value.endswith("\r"):
        return value[:-1]

    return value


def _require_non_empty(value: object, source: str) -> str:
    """Validate one text input without trimming or persisting its secret value.

    Reject non-text results and empty strings at the reader boundary while returning the
    original non-empty value unchanged for hashing or authorization.

    Args:
        value: Runtime result produced by an input reader.
        source: Human-readable input source used only in the error message.

    Returns:
        str: The original non-empty string value.

    Raises:
        PasswordInputError: If value is an empty string.
        TypeError: If value is not a string.
    """

    # Reader contract: reject non-text results before emptiness checks or return to callers.

    if not isinstance(value, str):
        raise TypeError(f"{source} password reader must return a string")

    # Empty secret rule: fail closed without trimming or replacing a missing password.

    if value == "":
        raise PasswordInputError(f"{source} password must not be empty")

    return value
