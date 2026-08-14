# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Resolve Brain CLI authority rules without weakening command boundaries.

This module centralizes configuration loading, dotted authority matching, and
typed permission decisions so restricted commands fail closed without exposing
password material.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from brain.application.authority.models import (
    AuthorityDecision,
    BrainAuthoritySpec,
)

DENIAL_MESSAGE_SUFFIX: Final[str] = (
    "follow declared instructions without retry"
)
"""Shared denial suffix used when a caller lacks the required authority."""


def get_authority_config_path() -> Path:
    """Locate the authority policy file used by the Brain CLI.

    This boundary keeps policy discovery tied to the active workspace, so
    callers share one configuration source when deciding whether commands execute.

    Args:
        None.

    Returns:
        Path: Canonical path to core/configs/brain_authority_config.json.
    """
    from brain.infrastructure.runtime.paths import get_workspace_root

    workspace_root = get_workspace_root()

    return workspace_root / "core" / "configs" / "brain_authority_config.json"


def _segment_matches_name_word(segment: str, name_word: str) -> bool:
    """Check edge matching for one normalized authority segment.

    The matcher accepts exact, leading, or trailing tokens only, preserving the
    security rule that middle substrings cannot select an authority policy.

    Args:
        segment: One normalized dotted segment from an emitted authority.
        name_word: One normalized dotted segment from a configured name word.

    Returns:
        bool: Whether the name word is exact, a prefix, or a suffix of the segment.
    """

    return (
        segment == name_word
        or segment.startswith(name_word)
        or segment.endswith(name_word)
    )


def _authority_matches_name_word(authority: str, name_word: str) -> bool:
    """Check whether a configured name word matches authority segment edges.

    Single tokens inspect individual segments, while dotted tokens inspect
    contiguous windows so hierarchy matching stays predictable and fail closed.

    Args:
        authority: Lowercase, trimmed dotted authority string.
        name_word: Configured dotted name word.

    Returns:
        bool: Whether the name word matches an exact, start, or end segment window.
    """

    authority_segments = tuple(authority.split("."))
    name_segments = tuple(name_word.casefold().split("."))

    # Single-token policy: compare the token with every authority segment edge.

    if len(name_segments) == 1:
        return any(
            _segment_matches_name_word(segment, name_segments[0])

            # Segment iteration: test each dotted segment at its authorized edge.

            for segment in authority_segments
        )

    # Multi-token guard: reject windows that cannot contain every configured segment.

    if len(name_segments) > len(authority_segments):
        return False

    window_count = len(authority_segments) - len(name_segments) + 1

    # Window scan: evaluate contiguous segment windows to preserve hierarchy boundaries.

    for window_start in range(window_count):
        window = authority_segments[window_start : window_start + len(name_segments)]

        # Pairwise invariant: every configured token must match its corresponding edge.

        if all(
            _segment_matches_name_word(segment, token)

            # Segment pairing: compare each authority window token in order.

            for segment, token in zip(window, name_segments)
        ):
            return True

    return False


def _append_postfix_once(message: str, postfix: str) -> str:
    """Append one configured postfix while preserving meaningful message text.

    Trailing duplicate suffixes are collapsed, but internal occurrences and
    existing separators remain intact for stable terminal and JSON output.

    Args:
        message: Existing deny or password-request message.
        postfix: Configured explanatory postfix.

    Returns:
        str: Message with one postfix at its end; internal occurrences are preserved.
    """

    # Empty-postfix policy: leave the caller's message unchanged when no suffix exists.

    if not postfix:
        return message

    normalized_message = message.rstrip()
    trailing_separator = ""
    found_trailing_postfix = False

    # Duplicate-suffix guard: remove only terminal copies so internal text is untouched.

    while normalized_message.endswith(postfix):
        found_trailing_postfix = True
        prefix_without_postfix = normalized_message[: -len(postfix)]
        normalized_prefix = prefix_without_postfix.rstrip()
        trailing_separator = prefix_without_postfix[len(normalized_prefix) :]
        normalized_message = normalized_prefix

    # Existing-suffix path: rebuild one terminal copy with its meaningful separator.

    if found_trailing_postfix:
        # Empty-base path: retain the suffix itself when the original message was only suffixes.

        if not normalized_message:
            return postfix

        separator = trailing_separator or " "

        return f"{normalized_message}{separator}{postfix}"

    # Empty-message path: a configured suffix is the only meaningful output available.

    if not message:
        return postfix

    # Whitespace path: retain the caller's existing separator before appending the suffix.

    if message[-1:].isspace():
        return f"{message}{postfix}"

    return f"{message} {postfix}"


def _build_denial_message(authority: str) -> str:
    """Build the standard denial message without including secret data.

    The message identifies the rejected authority only, allowing callers to
    explain a failed policy decision without echoing password material.

    Args:
        authority: Original caller authority displayed to the caller.

    Returns:
        str: Standard denial message.
    """

    return (
        f"This command is restricted for authority '{authority}', "
        f"{DENIAL_MESSAGE_SUFFIX}"
    )


class AuthorityService:
    """Coordinate authority policy loading and typed command decisions.

    The service owns one immutable configuration snapshot and applies fail-closed
    matching rules before callers dispatch a Brain CLI command.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Create a service with the selected authority policy source.

        The snapshot is loaded immediately so later decisions use one consistent
        configuration state and malformed policy cannot silently grant access.

        Args:
            config_path: Custom authority JSON path, or None for the workspace path.

        Returns:
            None.
        """

        self._config_path = config_path or get_authority_config_path()
        self._specs: tuple[BrainAuthoritySpec, ...] = ()

        self._load_specs()

    def _load_specs(self) -> None:
        """Load the policy snapshot while treating failures as no authority rules.

        Reading or parsing errors clear the snapshot so malformed or unavailable
        policy cannot silently broaden command access.

        Args:
            None.

        Returns:
            None.
        """

        # Missing-file policy: an unavailable authority document must deny by default.

        if not self._config_path.is_file():
            return

        # File and JSON boundary: unreadable or malformed policy must fail closed.

        try:
            raw_data = json.loads(self._config_path.read_text(encoding="utf-8"))

        # Load failure recovery: discard any partial interpretation of an invalid document.

        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            self._specs = ()

            return

        # Document-shape guard: only a top-level list can define a complete policy snapshot.

        if not isinstance(raw_data, list):
            self._specs = ()

            return

        parsed_specs: list[BrainAuthoritySpec] = []

        # Entry parsing boundary: reject the whole snapshot if any rule is malformed.

        try:
            # Entry iteration: validate every rule through the strict authority model.

            for entry in raw_data:
                spec = BrainAuthoritySpec.from_dict(entry)
                parsed_specs.append(spec)

        # Parse failure recovery: partial configuration must never grant access.

        except (TypeError, ValueError):
            self._specs = ()

            return

        self._specs = tuple(parsed_specs)

    def get_spec_for_authority(self, authority: str) -> BrainAuthoritySpec | None:
        """Resolve the most specific declared rule for an authority.

        Matching is deterministic: longer name words win, and original
        configuration order breaks ties without introducing implicit authority.

        Args:
            authority: Emitted dotted authority string.

        Returns:
            BrainAuthoritySpec | None: Best matching specification, or None.
        """

        # Type guard: non-text authorities cannot select a declared policy.

        if not isinstance(authority, str):
            return None

        authority_clean = authority.strip().casefold()

        # Empty-authority guard: blank caller identities must fail closed.

        if not authority_clean:
            return None

        best_spec: BrainAuthoritySpec | None = None
        best_score: tuple[int, int] | None = None

        # Candidate scan: compare every loaded rule before selecting a winner.

        for index, spec in enumerate(self._specs):
            name_word_clean = spec.name_word.casefold()

            # Match filter: skip rules that cannot select this authority at segment edges.

            if not _authority_matches_name_word(authority_clean, name_word_clean):
                continue

            candidate_score = (len(name_word_clean), -index)

            # Tie-break policy: prefer specificity, then preserve earlier configuration order.

            if best_score is None or candidate_score > best_score:
                best_score = candidate_score
                best_spec = spec

        return best_spec

    def evaluate_command_permission(
        self,
        command_name: str,
        authority: str,
    ) -> AuthorityDecision:
        """Evaluate one command and return an execute, request, or deny decision.

        The decision path protects restricted commands, honors the exact user
        bypass, and carries only safe output plus a validated digest when needed.

        Args:
            command_name: Registered CLI command name.
            authority: Emitted caller authority string.

        Returns:
            AuthorityDecision: Immutable typed decision with a safe message and,
            when needed, the configured password digest.
        """

        # Input validation: malformed caller data must fail closed without policy lookup.

        if not isinstance(command_name, str) or not isinstance(authority, str):
            return AuthorityDecision(
                status="deny",
                message=_build_denial_message(str(authority)),
            )

        authority_clean = authority.strip().casefold()

        # Sole bypass rule: only the exact user authority may execute without a declaration.

        if authority_clean == "user":
            return AuthorityDecision(status="execute", message="")

        spec = self.get_spec_for_authority(authority)

        # Unknown-authority rule: missing declarations cannot inherit another policy.

        if spec is None:
            return AuthorityDecision(
                status="deny",
                message=_build_denial_message(authority),
            )

        # Restriction precedence: disallowed commands request a password before allowlists.

        if command_name in spec.disallowed:
            request_base_message = spec.ask_message

            # Prompt fallback: provide a safe request when configuration omits custom text.

            if not request_base_message:
                request_base_message = (
                    f"Command '{command_name}' requires user permission "
                    f"for authority '{authority}'."
                )

            request_message = _append_postfix_once(
                request_base_message,
                spec.disallow_message_postfix,
            )

            return AuthorityDecision(
                status="request_password",
                message=request_message,
                password_digest=spec.user_password,
            )

        # Allowlist rule: execute only explicitly allowed commands or an allowed-all policy.

        if spec.allowed == "all" or command_name in spec.allowed:
            return AuthorityDecision(status="execute", message="")

        denial_message = _append_postfix_once(
            _build_denial_message(authority),
            spec.disallow_message_postfix,
        )

        return AuthorityDecision(
            status="deny",
            message=denial_message,
        )
