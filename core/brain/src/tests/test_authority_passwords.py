"""Contract tests for authority password hashing and secure input helpers."""

from __future__ import annotations

from io import StringIO

import pytest

from brain.application.authority import passwords


@pytest.mark.parametrize(
    ("password", "expected_digest"),
    [
        (
            "abc",
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        ),
        (
            "é",
            "4a99557e4033c3539de2eb65472017cad5f9557f7a0625a09f1c3f6e2ba69c4c",
        ),
    ],
)
def test_hash_password_uses_utf8_sha256_and_lowercase_hex(
    password: str,
    expected_digest: str,
) -> None:
    """Hash ASCII and non-ASCII inputs into known lowercase SHA-256 vectors.

    Args:
        password: Obvious test password used as the hash input.
        expected_digest: Known SHA-256 digest for the UTF-8 input.

    Returns:
        None.
    """

    digest = passwords.hash_password(password)

    assert digest == expected_digest
    assert len(digest) == 64
    assert digest == digest.lower()


def test_verify_password_uses_constant_time_compare(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use hmac.compare_digest exactly after validating the expected digest.

    Args:
        monkeypatch: Pytest fixture used to observe the comparison call.

    Returns:
        None.
    """

    expected_digest = passwords.hash_password("abc")
    comparison_calls: list[tuple[str, str]] = []

    def compare_digest(left: str, right: str) -> bool:
        """Record a comparison and return its ordinary equality result.

        Args:
            left: Actual digest supplied by the password verifier.
            right: Expected digest supplied by the caller.

        Returns:
            bool: Equality result for this test double.
        """

        comparison_calls.append((left, right))

        return left == right

    monkeypatch.setattr(passwords.hmac, "compare_digest", compare_digest)

    assert passwords.verify_password("abc", expected_digest) is True
    assert comparison_calls == [(expected_digest, expected_digest)]


@pytest.mark.parametrize(
    "malformed_digest",
    [
        "",
        "000000000000000000000000000000000000000000000000000000000000000",
        "00000000000000000000000000000000000000000000000000000000000000000",
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg",
        "000000000000000000000000000000000000000000000000000000000000000\n",
    ],
)
def test_verify_password_returns_false_for_malformed_digests(malformed_digest: str) -> None:
    """Reject digest length, alphabet, case, and newline violations.

    Args:
        malformed_digest: Invalid digest fixture presented to verification.

    Returns:
        None.
    """

    assert passwords.verify_password("abc", malformed_digest) is False


def test_verify_password_returns_false_for_a_mismatch() -> None:
    """Return false when a valid digest belongs to another password.

    Args:
        None.

    Returns:
        None.
    """

    expected_digest = passwords.hash_password("abc")

    assert passwords.verify_password("wrong", expected_digest) is False


def test_read_password_uses_an_injected_hidden_reader_without_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pass the prompt to an injected reader and return its unmodified value.

    Args:
        capsys: Pytest fixture used to prove the helper emits no output.

    Returns:
        None.
    """

    prompts: list[str] = []

    def hidden_reader(prompt: str) -> str:
        """Record the prompt and return an obvious test password.

        Args:
            prompt: Prompt supplied by the password helper.

        Returns:
            str: Obvious test password.
        """

        prompts.append(prompt)

        return "abc"

    assert passwords.read_password(hidden_reader) == "abc"
    assert prompts == [passwords.DEFAULT_PASSWORD_PROMPT]
    assert capsys.readouterr().out == ""


def test_read_password_rejects_empty_hidden_input() -> None:
    """Raise the typed input error when a hidden reader returns no content.

    Args:
        None.

    Returns:
        None.
    """

    with pytest.raises(passwords.PasswordInputError, match="must not be empty"):
        passwords.read_password(lambda _prompt: "")


@pytest.mark.parametrize(
    ("payload", "expected_password"),
    [
        ("abc", "abc"),
        ("abc\n", "abc"),
        ("abc\r\n", "abc"),
        ("abc\r", "abc"),
        (" abc \n", " abc "),
    ],
)
def test_read_password_from_stdin_accepts_one_line_and_removes_one_ending(
    payload: str,
    expected_password: str,
) -> None:
    """Accept one line with optional conventional newline termination.

    Args:
        payload: Complete stdin payload used by the test.
        expected_password: Payload after removing one terminal line ending.

    Returns:
        None.
    """

    assert passwords.read_password_from_stdin(StringIO(payload)) == expected_password


@pytest.mark.parametrize("payload", ["", "\n", "\r\n", "abc\nextra", "abc\n\n"])
def test_read_password_from_stdin_rejects_empty_and_extra_material(payload: str) -> None:
    """Reject empty input and every payload containing a second line.

    Args:
        payload: Invalid stdin payload under test.

    Returns:
        None.
    """

    with pytest.raises(passwords.PasswordInputError):
        passwords.read_password_from_stdin(StringIO(payload))
