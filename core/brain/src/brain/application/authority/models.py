# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Define immutable models for Brain CLI authority specifications and decisions.

Centralizes strict, fail-closed parsing for authority names, command sets, and password digests.
Carries safe decision metadata without exposing password material through dataclass representations.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
import re
from typing import Final, Literal


AllowedCommands = tuple[str, ...] | Literal["all"]
DecisionStatus = Literal["execute", "request_password", "deny"]

_ALLOWED_CONFIG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "name_word",
        "allowed",
        "disallowed",
        "ask_message",
        "user_password",
        "disallow_message_postfix",
    }
)
_REQUIRED_CONFIG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "name_word",
        "allowed",
        "disallowed",
    }
)
_NAME_WORD_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[^\s.]+(?:\.[^\s.]+)*$")
_PASSWORD_DIGEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_DECISION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "execute",
        "request_password",
        "deny",
    }
)


def _parse_name_word(raw_value: object) -> str:
    """Validate and return one authority name word.

    Authority names are hierarchical tokens, so strict segment validation keeps matching deterministic.
    Rejecting malformed values before they reach the matcher prevents configuration from widening scope.

    Args:
        raw_value: Raw name word loaded from an authority configuration entry.

    Returns:
        str: Validated dotted name word.

    Raises:
        TypeError: If the raw value is not text.
        ValueError: If the name word is empty, padded, or malformed.
    """

    # Type boundary: reject non-text values before any string normalization or matching.

    if not isinstance(raw_value, str):
        raise TypeError("name_word must be a string")

    # Grammar boundary: reject padding and empty dotted segments so authority scope stays deterministic.

    if raw_value != raw_value.strip() or _NAME_WORD_PATTERN.fullmatch(raw_value) is None:
        raise ValueError("name_word must contain non-empty dotted segments")

    return raw_value


def _parse_text_field(
    data: Mapping[str, object],
    field_name: str,
    default: str = "",
) -> str:
    """Read one required-or-default text field without coercion.

    Authority messages and text settings must remain textual so callers do not receive implicit conversions.
    Keeping the default explicit preserves empty request or denial messages with their configured meaning.

    Args:
        data: Raw authority configuration entry.
        field_name: Configuration key to read.
        default: Value used when the key is absent.

    Returns:
        str: The validated text value.

    Raises:
        TypeError: If the configured value is not text.
    """

    raw_value = data.get(field_name, default)

    # Type boundary: keep configuration text explicit instead of coercing arbitrary values.

    if not isinstance(raw_value, str):
        raise TypeError(f"{field_name} must be a string")

    return raw_value


def _parse_command_values(
    raw_value: object,
    field_name: str,
    allow_all: bool,
) -> AllowedCommands | tuple[str, ...]:
    """Validate one command allowlist or denylist without coercion.

    The literal all marker is accepted only for allowlists, while validated lists become immutable tuples.
    Rejecting every other shape prevents malformed policy data from being interpreted as an unintended grant.

    Args:
        raw_value: Raw command collection from configuration.
        field_name: Configuration key being validated.
        allow_all: Whether the literal all is valid for this field.

    Returns:
        AllowedCommands | tuple[str, ...]: Immutable parsed command values.

    Raises:
        TypeError: If the value is not a list, uses all when unsupported, or contains non-text entries.
    """

    # Allowlists alone may opt into the explicit unrestricted marker; denylists remain enumerated.

    if allow_all and raw_value == "all":
        return "all"

    # Shape boundary: fail closed when command policy is not in the expected list form.

    if not isinstance(raw_value, list):
        raise TypeError(f"{field_name} must be 'all' or a list of strings")

    # Element boundary: reject mixed-type command entries before freezing the policy.

    if any(not isinstance(item, str) for item in raw_value):
        raise TypeError(f"{field_name} must contain only strings")

    return tuple(raw_value)


def _parse_password_digest(raw_value: object, field_name: str) -> str:
    """Validate an optional empty-or-SHA-256 password digest.

    Canonical lowercase hexadecimal output gives downstream verification one stable representation to compare.
    Field-only validation errors preserve fail-closed behavior without echoing credential material to callers.

    Args:
        raw_value: Raw digest value from configuration or a decision.
        field_name: Name used in validation failures.

    Returns:
        str: The empty digest or a validated lowercase hexadecimal digest.

    Raises:
        TypeError: If the value is not text.
        ValueError: If the non-empty digest is not a SHA-256 hexadecimal value.
    """

    # Type boundary: keep credential fields textual so validation errors remain unambiguous.

    if not isinstance(raw_value, str):
        raise TypeError(f"{field_name} must be a string")

    # Empty digest is the explicit unconfigured state; preserving it keeps protected access fail closed.

    if raw_value == "":
        return ""

    # Digest boundary: reject non-SHA-256 text without including the candidate secret in the error.

    if _PASSWORD_DIGEST_PATTERN.fullmatch(raw_value) is None:
        raise ValueError(
            f"{field_name} must be empty or a 64-character hexadecimal SHA-256 digest"
        )

    return raw_value


@dataclass(frozen=True)
class BrainAuthoritySpec:
    """Represent one immutable authority rule loaded from JSON.

    This model is the fail-closed boundary between untrusted configuration and command authorization.
    It stores normalized command sets and a validated digest while excluding credential material from repr.

    Attributes:
        name_word: Dotted authority token used for hierarchical matching.
        allowed: Immutable command allowlist or the literal all.
        disallowed: Immutable commands that require a password decision.
        ask_message: Prompt text returned with a password request.
        user_password: Optional SHA-256 digest carried by a password request.
        disallow_message_postfix: Text appended once to deny and request messages.
    """

    name_word: str
    allowed: AllowedCommands
    disallowed: tuple[str, ...]
    ask_message: str = ""
    user_password: str = field(default="", repr=False)
    disallow_message_postfix: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> BrainAuthoritySpec:
        """Parse one strict authority configuration entry.

        Rejecting unknown and missing keys before normalization prevents legacy or partial data from changing policy.
        Each field is validated without coercion before an immutable specification is constructed for matching.

        Args:
            data: Raw mapping loaded from the authority JSON document.

        Returns:
            BrainAuthoritySpec: Validated immutable authority specification.

        Raises:
            TypeError: If the entry or a field has an incompatible type.
            ValueError: If fields are missing, deprecated, or malformed.
        """

        # Schema boundary: reject non-object entries before any configuration keys are trusted.

        if not isinstance(data, Mapping):
            raise TypeError("authority configuration entries must be objects")

        unknown_keys = set(data).difference(_ALLOWED_CONFIG_KEYS)

        # Compatibility boundary: reject unsupported fields so deprecated controls cannot affect authorization.

        if unknown_keys:
            raise ValueError("authority configuration contains unsupported fields")

        missing_keys = _REQUIRED_CONFIG_KEYS.difference(data)

        # Fail-closed boundary: require identity and command policies before constructing an immutable rule.

        if missing_keys:
            raise ValueError("authority configuration is missing required fields")

        name_word = _parse_name_word(data["name_word"])
        allowed = _parse_command_values(data["allowed"], "allowed", allow_all=True)
        disallowed = _parse_command_values(
            data["disallowed"],
            "disallowed",
            allow_all=False,
        )
        ask_message = _parse_text_field(data, "ask_message")
        user_password = _parse_password_digest(
            data.get("user_password", ""),
            "user_password",
        )
        disallow_message_postfix = _parse_text_field(
            data,
            "disallow_message_postfix",
        )

        # Allowlist normalization: preserve the explicit unrestricted marker for service-level precedence.

        if allowed == "all":
            parsed_allowed: AllowedCommands = "all"

        # Allowlist normalization: retain the immutable tuple when no unrestricted marker is configured.

        else:
            parsed_allowed = allowed

        return cls(
            name_word=name_word,
            allowed=parsed_allowed,
            disallowed=disallowed,
            ask_message=ask_message,
            user_password=user_password,
            disallow_message_postfix=disallow_message_postfix,
        )


@dataclass(frozen=True)
class AuthorityDecision:
    """Represent one immutable result of command authority evaluation.

    This DTO makes execute, password-request, and denial states explicit at the router boundary.
    Its digest field carries only protected-request metadata and is excluded from repr for redaction.

    Attributes:
        status: One of execute, request_password, or deny.
        message: User-facing text associated with the decision.
        password_digest: Validated digest needed for a password request.
    """

    status: DecisionStatus
    message: str
    password_digest: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        """Validate the decision status, message, and optional digest.

        These invariants keep unknown states and malformed digests from reaching command dispatch.
        Validation preserves frozen dataclass semantics while allowing only canonical decision metadata.

        Args:
            None.

        Returns:
            None.

        Raises:
            TypeError: If the message is not text.
            ValueError: If the status or digest is malformed.
        """

        # State boundary: reject unknown statuses so callers cannot route an unrecognized decision.

        if self.status not in _DECISION_STATUSES:
            raise ValueError("authority decision status is invalid")

        # Output boundary: keep user-facing decision messages textual for safe rendering.

        if not isinstance(self.message, str):
            raise TypeError("authority decision message must be a string")

        normalized_digest = _parse_password_digest(
            self.password_digest,
            "password_digest",
        )

        # Frozen-state normalization: use the internal escape hatch only for canonicalized digest values.

        if normalized_digest != self.password_digest:
            object.__setattr__(self, "password_digest", normalized_digest)

    @property
    def password(self) -> str:
        """Return the requested password digest under its short compatibility name.

        This alias preserves existing callers while the canonical field retains validation and repr redaction.
        Callers receive only the validated digest metadata required by the protected-command handshake.

        Args:
            None.

        Returns:
            str: Empty text or the validated SHA-256 password digest.
        """

        return self.password_digest

    def __iter__(self) -> Iterator[bool | str]:
        """Expose the historical two-value permission view to existing callers.

        Tuple-unpacking remains compatible with older callers while richer status and digest fields stay available.
        The yielded values intentionally preserve the original execute-boolean and message ordering.

        Args:
            None.

        Returns:
            Iterator[bool | str]: Execute boolean followed by the decision message.
        """

        yield self.status == "execute"

        yield self.message
