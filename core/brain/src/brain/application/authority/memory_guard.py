# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Guard memory-content exposure using the authority headers declared in Markdown.

Centralizes canonical identity matching and fail-closed allowlist/denylist decisions
so protected memory is not exposed to missing, malformed, or unrelated authorities.
"""

from __future__ import annotations

import re
from typing import Final


_AUTHORITY_HEADER_PATTERN = re.compile(
    r"<!--\s*(?P<header>Authorized|Unaut?h?orized)\s*:\s*(?P<tokens>.*?)\s*-->",
    re.IGNORECASE,
)

AUTHORITY_REQUIRED_MESSAGE: Final[str] = "Command authority is required."


def _parse_authority_tokens(raw_tokens: str) -> tuple[str, ...]:
    """Normalize comma-separated authority tokens before hierarchy matching.

    Canonicalizing case and whitespace prevents equivalent declarations from diverging,
    while discarding empty fields keeps malformed delimiters from granting access.

    Args:
        raw_tokens: Raw comma-separated token text captured from a header.

    Returns:
        tuple[str, ...]: Lowercase, trimmed, non-empty authority tokens.
    """

    normalized_tokens: list[str] = []

    # Parse each declared field independently so empty tokens cannot affect authorization.

    for item in raw_tokens.split(","):
        cleaned_item = item.strip().lower()

        # Ignore empty declarations because no concrete token can safely authorize a caller.

        if cleaned_item:
            normalized_tokens.append(cleaned_item)

    return tuple(normalized_tokens)


def _authority_matches_token(
    authority_clean: str,
    authority_segments: frozenset[str],
    token: str,
) -> bool:
    """Match one declared token against the caller's normalized authority hierarchy.

    Uses exact, dotted-segment, prefix, and suffix comparisons instead of arbitrary substring
    matching, preventing a partial middle token from crossing the memory authorization boundary.

    Args:
        authority_clean: Lowercase, trimmed authority string under inspection.
        authority_segments: Individual segments from the normalized authority.
        token: Lowercase, trimmed token declared by a header.

    Returns:
        bool: Whether the token matches exactly, by segment, as a prefix, or as a suffix.
    """

    is_exact = token == authority_clean

    # Restrict segment comparisons to complete edges so a middle substring cannot authorize access.

    is_segment_match = any(
        segment == token
        or segment.startswith(token)
        or segment.endswith(token)
        for segment in authority_segments
    )
    is_prefix = authority_clean.startswith(token + ".")
    is_suffix = authority_clean.endswith("." + token)

    return is_exact or is_segment_match or is_prefix or is_suffix


def is_memory_access_allowed(content: str, authority: str | None) -> tuple[bool, str]:
    """Enforce Markdown memory-header access policy for one caller authority.

    An `Authorized` marker acts as an allowlist; `Unauthorized` and its supported legacy
    misspelling act as a denylist, while missing identities fail closed and `user` bypasses it.

    Args:
        content: Raw or rendered Markdown memory content.
        authority: Emitted authority string, or None when caller authority is missing.

    Returns:
        tuple[bool, str]: (Is allowed, Denial reason or empty string).
    """

    # Fail closed at the boundary when the caller provides no string identity.

    if not isinstance(authority, str):
        return False, AUTHORITY_REQUIRED_MESSAGE

    authority_clean = authority.strip().lower()

    # Reject whitespace-only identities because they cannot match a declared authority token.

    if not authority_clean:
        return False, AUTHORITY_REQUIRED_MESSAGE

    # Preserve the owner bypass before header parsing; user is the only implicit trusted authority.

    if authority_clean in ("user",):
        return True, ""

    # Empty content contains no memory body to protect, so it may pass without header evaluation.

    if not content:
        return True, ""

    matches = _AUTHORITY_HEADER_PATTERN.findall(content)

    # Unmarked content opts out of this header policy and remains readable to a valid authority.

    if not matches:
        return True, ""

    authority_segments = frozenset(authority_clean.split("."))
    authorized_tokens: list[str] = []
    unauthorized_tokens: list[str] = []
    has_authorized_header = False

    # Collect every matching header before deciding so any Authorized marker controls precedence.

    for header_name, raw_tokens in matches:
        parsed_tokens = _parse_authority_tokens(raw_tokens)

        # Treat an Authorized marker as an allowlist declaration; evaluate it before denylists.

        if header_name.lower() == "authorized":
            has_authorized_header = True
            authorized_tokens.extend(parsed_tokens)
            continue

        unauthorized_tokens.extend(parsed_tokens)

    denial_message = (
        f"This domain is restricted for authority '{authority}', "
        "follow declared instructions without retry"
    )

    # Enforce allowlist semantics whenever an Authorized marker exists, even if denylists match.

    if has_authorized_header:
        is_authorized = any(
            _authority_matches_token(authority_clean, authority_segments, token)
            for token in authorized_tokens
        )

        # Fail closed when no declared allowlist token matches the normalized caller authority.

        if not is_authorized:
            return False, denial_message

        return True, ""

    # Evaluate denylist entries only after allowlist resolution, preserving explicit precedence.

    is_unauthorized = any(
        _authority_matches_token(authority_clean, authority_segments, token)
        for token in unauthorized_tokens
    )

    # Deny only explicitly matched denylist identities; unrelated authorities remain readable.

    if is_unauthorized:
        return False, denial_message

    return True, ""
