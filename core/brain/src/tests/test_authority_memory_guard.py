"""Regression tests for authority headers protecting Brain memory entries.

Verify that supported header spellings deny matching caller authorities while
leaving unrelated authorities and unmarked content readable.
"""

from __future__ import annotations

import pytest

from brain.application.authority.memory_guard import is_memory_access_allowed


@pytest.mark.parametrize(
    ("authority", "expected_allowed"),
    [
        ("workers.python.python_writer", True),
        ("workers.python_writer", True),
        ("python.python_writer", True),
        ("python.python_editor", False),
        ("worker.editor", True),
    ],
)
def test_authorized_tokens_match_segment_edges(
    authority: str,
    expected_allowed: bool,
) -> None:
    """Match Authorized tokens against exact, prefix, and suffix segments.

    Args:
        authority: Candidate dotted authority evaluated against the header.
        expected_allowed: Expected access result for the candidate authority.

    Returns:
        None.
    """

    content = "<!-- Authorized: writer, worker -->\n# Protected"

    allowed, _ = is_memory_access_allowed(content, authority)

    assert allowed is expected_allowed


@pytest.mark.parametrize(
    ("label", "token", "authority", "expected_allowed"),
    [
        ("Authorized", "worker", "workers.python.python_writer", True),
        ("Authorized", "writer", "python.python_writer", True),
        ("Authorized", "writer", "python.python_editor", False),
        ("Unauthorized", "worker", "workers.python.python_writer", False),
        ("Unauthorized", "writer", "python.python_writer", False),
        ("Unauthorized", "writer", "python.python_editor", True),
        ("Unauthorized", "ork", "worker", True),
        ("Authorized", "ork", "worker", False),
    ],
)
def test_both_header_types_reject_middle_substrings(
    label: str,
    token: str,
    authority: str,
    expected_allowed: bool,
) -> None:
    """Apply segment-edge matching without accepting middle substrings.

    Args:
        label: Header spelling that declares the authority rule.
        token: Token tested against the candidate authority segments.
        authority: Candidate authority evaluated against the header.
        expected_allowed: Expected access result for the candidate authority.

    Returns:
        None.
    """

    content = f"<!-- {label}: {token} -->\n# Protected"

    allowed, _ = is_memory_access_allowed(content, authority)

    assert allowed is expected_allowed


@pytest.mark.parametrize("label", ["Unauthorized", "Unautorized"])
def test_matching_authority_header_denies_memory_access(label: str) -> None:
    """Deny a caller named by either supported authority-header spelling.

    Args:
        label: Supported authorization marker spelling under test.

    Returns:
        None.
    """
    content = f"<!-- {label}: worker -->\n# Protected"

    allowed, reason = is_memory_access_allowed(content, "worker")

    assert allowed is False
    assert reason == (
        "This domain is restricted for authority 'worker', "
        "follow declared instructions without retry"
    )


def test_authority_header_matches_hierarchical_worker_identity() -> None:
    """Deny a nested worker identity when its authority segment is protected.

    Args:
        None.

    Returns:
        None.
    """

    content = "<!-- Unauthorized: worker -->\n# Protected"

    allowed, reason = is_memory_access_allowed(content, "worker.python.writer")

    assert allowed is False
    assert reason == (
        "This domain is restricted for authority 'worker.python.writer', "
        "follow declared instructions without retry"
    )


@pytest.mark.parametrize("authority", ["a", "B", "c", "root"])
def test_authorized_header_accepts_exact_list_entries_case_insensitively(authority: str) -> None:
    """Allow authorities named by a whitespace-tolerant, case-insensitive list.

    Args:
        authority: Candidate authority selected from the declared allowlist.

    Returns:
        None.
    """

    content = "<!--  aUtHoRiZeD :  A,  b , C, root  -->\n# Protected"

    assert is_memory_access_allowed(content, authority) == (True, "")


def test_authorized_header_denies_an_unrelated_authority() -> None:
    """Deny an authority absent from an Authorized header.

    Args:
        None.

    Returns:
        None.
    """

    content = "<!-- Authorized: worker -->\n# Protected"

    allowed, reason = is_memory_access_allowed(content, "orchestrator")

    assert allowed is False
    assert reason == (
        "This domain is restricted for authority 'orchestrator', "
        "follow declared instructions without retry"
    )


@pytest.mark.parametrize(
    ("label", "token", "expected_allowed"),
    [
        ("Authorized", "worker.python.writer", True),
        ("Authorized", "python", True),
        ("Authorized", "worker.python", True),
        ("Authorized", "python.writer", True),
        ("Unauthorized", "worker.python.writer", False),
        ("Unauthorized", "python", False),
        ("Unauthorized", "worker.python", False),
        ("Unauthorized", "python.writer", False),
    ],
)
def test_authority_headers_share_hierarchical_matching(
    label: str,
    token: str,
    expected_allowed: bool,
) -> None:
    """Apply exact, segment, prefix, and suffix matching to both header types.

    Args:
        label: Header spelling that declares the authority rule.
        token: Exact or hierarchical token used by the header.
        expected_allowed: Expected access result for the matching rule.

    Returns:
        None.
    """

    content = f"<!-- {label}: {token} -->\n# Protected"

    allowed, _ = is_memory_access_allowed(content, "worker.python.writer")

    assert allowed is expected_allowed


@pytest.mark.parametrize(
    ("authorized_token", "unauthorized_token", "authority", "expected_allowed"),
    [
        ("A", "A", "a", True),
        ("B", "B", "b", True),
        ("C", "C", "c", True),
        ("root", "root", "root", True),
        ("worker", "worker", "worker", True),
        ("worker", "worker", "worker.python.writer", True),
        ("python", "python", "worker.python.writer", True),
        ("worker.python", "worker.python", "worker.python.writer", True),
        ("python.writer", "python.writer", "worker.python.writer", True),
        ("worker", "orchestrator", "worker", True),
        ("worker", "orchestrator", "orchestrator", False),
    ],
)
def test_combined_headers_apply_allowlist_and_denylist_precedence(
    authorized_token: str,
    unauthorized_token: str,
    authority: str,
    expected_allowed: bool,
) -> None:
    """Prioritize a matching Authorized rule over a matching Unauthorized rule.

    Args:
        authorized_token: Token declared by the Authorized header.
        unauthorized_token: Token declared by the Unauthorized header.
        authority: Caller authority evaluated against both headers.
        expected_allowed: Expected result after applying both header rules.

    Returns:
        None.
    """

    content = (
        f"<!-- Authorized: {authorized_token} -->\n"
        f"<!-- Unauthorized: {unauthorized_token} -->\n# Protected"
    )

    allowed, reason = is_memory_access_allowed(content, authority)

    assert allowed is expected_allowed

    if expected_allowed:
        assert reason == ""

        return

    assert reason == (
        f"This domain is restricted for authority '{authority}', "
        "follow declared instructions without retry"
    )


def test_user_authority_bypasses_declared_headers() -> None:
    """Keep the existing user bypass ahead of header authorization checks.

    Args:
        None.

    Returns:
        None.
    """

    content = "<!-- Authorized: worker -->\n<!-- Unauthorized: user -->\n# Protected"

    assert is_memory_access_allowed(content, "user") == (True, "")


@pytest.mark.parametrize("authority", [None, "", "   "])
def test_missing_or_empty_authority_denies_with_safe_message(
    authority: str | None,
) -> None:
    """Deny memory access when no usable caller authority is supplied.

    Args:
        authority: Missing, empty, or whitespace-only authority under test.

    Returns:
        None.
    """

    content = "<!-- Authorized: user -->\n# Protected"

    allowed, reason = is_memory_access_allowed(content, authority)

    assert allowed is False
    assert reason == "Command authority is required."


def test_unmarked_content_remains_readable() -> None:
    """Allow content that declares neither an allowlist nor a denylist.

    Args:
        None.

    Returns:
        None.
    """

    content = "# Unmarked memory"

    assert is_memory_access_allowed(content, "worker") == (True, "")


def test_unrelated_authority_remains_allowed() -> None:
    """Keep protected entries readable for authorities absent from the marker.

    Args:
        None.

    Returns:
        None.
    """
    content = "<!-- Unauthorized: worker -->\n# Protected"

    assert is_memory_access_allowed(content, "orchestrator") == (True, "")
