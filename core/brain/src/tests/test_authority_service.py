"""Focused tests for strict authority configuration and typed command decisions."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

from brain.application.authority.models import (
    AuthorityDecision,
    BrainAuthoritySpec,
)
from brain.application.authority.service import AuthorityService


PASSWORD_DIGEST = "a" * 64
POSTFIX = "Sub-agent lacks authority for system administrative commands."


def _create_service(
    tmp_path: Path,
    entries: list[dict[str, object]],
) -> AuthorityService:
    """Create an authority service backed by an isolated JSON configuration.

    Args:
        tmp_path: Temporary directory used for the isolated configuration.
        entries: Authority specification dictionaries to serialize.

    Returns:
        AuthorityService: Service loaded from the isolated configuration.
    """

    config_path = tmp_path / "authority.json"
    config_path.write_text(json.dumps(entries), encoding="utf-8")

    return AuthorityService(config_path=config_path)


def _entry(
    name_word: str,
    allowed: str | list[str],
    disallowed: list[str] | None = None,
    **extra: object,
) -> dict[str, object]:
    """Build one valid authority entry for a focused test.

    Args:
        name_word: Authority name word or dotted name word.
        allowed: Literal all or command allowlist.
        disallowed: Optional command denylist.
        extra: Optional message or password fields.

    Returns:
        dict[str, object]: JSON-compatible authority entry.
    """

    entry: dict[str, object] = {
        "name_word": name_word,
        "allowed": allowed,
        "disallowed": disallowed or [],
    }
    entry.update(extra)

    return entry


def test_new_spec_shape_is_immutable_and_excludes_legacy_fields() -> None:
    """Parse the new fields and reject the removed legacy configuration keys.

    Args:
        None.

    Returns:
        None.
    """

    spec = BrainAuthoritySpec.from_dict(
        _entry(
            "worker",
            ["help"],
            ask_message="Enter the user password.",
            user_password=PASSWORD_DIGEST,
            disallow_message_postfix=POSTFIX,
        )
    )

    assert spec.name_word == "worker"
    assert spec.allowed == ("help",)
    assert spec.disallowed == ()
    assert spec.user_password == PASSWORD_DIGEST
    assert "prefix" not in spec.__dataclass_fields__
    assert "permission" not in spec.__dataclass_fields__
    assert "ask_acceptance_words" not in spec.__dataclass_fields__

    with pytest.raises(ValueError):
        BrainAuthoritySpec.from_dict(
            {
                "prefix": "worker",
                "allowed": "all",
                "disallowed": [],
            }
        )


def test_malformed_password_digest_is_rejected() -> None:
    """Reject every non-empty value that is not a SHA-256 hexadecimal digest.

    Args:
        None.

    Returns:
        None.
    """

    malformed_digests: tuple[object, ...] = (
        "not-a-digest",
        None,
        "f" * 63,
        "g" * 64,
        "A" * 64,
    )

    for malformed_digest in malformed_digests:
        entry = _entry(
            "worker",
            "all",
            user_password=malformed_digest,
        )

        with pytest.raises((TypeError, ValueError)):
            BrainAuthoritySpec.from_dict(entry)


def test_empty_password_digest_is_the_only_empty_exception() -> None:
    """Accept an explicitly empty password digest for migrated configurations.

    Args:
        None.

    Returns:
        None.
    """

    spec = BrainAuthoritySpec.from_dict(_entry("worker", "all", user_password=""))

    assert spec.user_password == ""


def test_malformed_configuration_fails_closed_for_the_whole_service(
    tmp_path: Path,
) -> None:
    """Deny valid-looking entries when any configuration entry is malformed.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    service = _create_service(
        tmp_path,
        [
            _entry("worker", ["help"]),
            _entry("root", "all", user_password="malformed"),
        ],
    )

    decision = service.evaluate_command_permission("help", "worker")

    assert decision.status == "deny"
    assert "restricted for authority 'worker'" in decision.message


@pytest.mark.parametrize(
    ("name_word", "authority", "expected"),
    [
        ("worker", "worker", True),
        ("worker", "workers.python", True),
        ("writer", "python.python_writer", True),
        ("python", "worker.python_writer", True),
        ("ork", "worker", False),
    ],
)
def test_name_word_matches_only_exact_segment_edges(
    tmp_path: Path,
    name_word: str,
    authority: str,
    expected: bool,
) -> None:
    """Match name words at dotted segment starts or ends, never in the middle.

    Args:
        tmp_path: Temporary directory used for isolated configuration.
        name_word: Configured name word under test.
        authority: Emitted authority under test.
        expected: Whether the configured name word should resolve.

    Returns:
        None.
    """

    service = _create_service(tmp_path, [_entry(name_word, ["help"])])

    assert (service.get_spec_for_authority(authority) is not None) is expected


def test_longest_matching_name_word_wins_independently_of_entry_order(
    tmp_path: Path,
) -> None:
    """Choose the most specific matching name word deterministically.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    service = _create_service(
        tmp_path,
        [
            _entry("worker", ["short"]),
            _entry("worker.python", ["long"]),
        ],
    )

    spec = service.get_spec_for_authority("worker.python.writer")

    assert spec is not None
    assert spec.name_word == "worker.python"


def test_disallowed_command_requests_password_before_allowed_command(
    tmp_path: Path,
) -> None:
    """Return a password request when a command appears in both command lists.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    service = _create_service(
        tmp_path,
        [
            _entry(
                "worker",
                ["delete-task"],
                ["delete-task"],
                ask_message="Enter the user password.",
                user_password=PASSWORD_DIGEST,
                disallow_message_postfix=POSTFIX,
            )
        ],
    )

    decision = service.evaluate_command_permission("delete-task", "worker")

    assert isinstance(decision, AuthorityDecision)
    assert decision.status == "request_password"
    assert decision.message == f"Enter the user password. {POSTFIX}"
    assert decision.password_digest == PASSWORD_DIGEST
    assert decision.password == PASSWORD_DIGEST
    assert PASSWORD_DIGEST not in repr(decision)


def test_empty_request_message_uses_safe_default(tmp_path: Path) -> None:
    """Build a non-empty request message when configured prompt text is empty.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    service = _create_service(
        tmp_path,
        [
            _entry(
                "root",
                "all",
                ["delete-task"],
                ask_message="",
                user_password="",
                disallow_message_postfix="",
            )
        ],
    )

    decision = service.evaluate_command_permission("delete-task", "root")

    assert decision.status == "request_password"
    assert decision.message == (
        "Command 'delete-task' requires user permission for authority 'root'."
    )
    assert decision.password_digest == ""


def test_empty_request_message_uses_default_before_postfix(tmp_path: Path) -> None:
    """Append a configured postfix once after the generated safe request message.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    service = _create_service(
        tmp_path,
        [
            _entry(
                "root",
                "all",
                ["delete-task"],
                ask_message="",
                user_password=PASSWORD_DIGEST,
                disallow_message_postfix=POSTFIX,
            )
        ],
    )

    decision = service.evaluate_command_permission("delete-task", "root")

    assert decision.message == (
        "Command 'delete-task' requires user permission for authority 'root'. "
        f"{POSTFIX}"
    )
    assert decision.message.count(POSTFIX) == 1
    assert PASSWORD_DIGEST not in decision.message


def test_custom_request_message_is_preserved_before_postfix(tmp_path: Path) -> None:
    """Preserve configured request text verbatim before appending its postfix.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    custom_message = "Use the configured approval channel."
    service = _create_service(
        tmp_path,
        [
            _entry(
                "worker",
                "all",
                ["delete-task"],
                ask_message=custom_message,
                user_password=PASSWORD_DIGEST,
                disallow_message_postfix=POSTFIX,
            )
        ],
    )

    decision = service.evaluate_command_permission("delete-task", "worker")

    assert decision.message == f"{custom_message} {POSTFIX}"
    assert decision.message.startswith(custom_message)
    assert decision.message.count(POSTFIX) == 1
    assert PASSWORD_DIGEST not in decision.message


def test_unlisted_and_unknown_commands_are_denied(tmp_path: Path) -> None:
    """Deny commands absent from an authority allowlist and unknown authorities.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    service = _create_service(tmp_path, [_entry("worker", ["help"])])

    unlisted = service.evaluate_command_permission("query", "worker")
    unknown = service.evaluate_command_permission("help", "unknown")
    empty_authority = service.evaluate_command_permission("help", "")

    assert unlisted.status == "deny"
    assert unknown.status == "deny"
    assert empty_authority.status == "deny"
    assert unlisted.password_digest == ""
    assert unknown.password_digest == ""
    assert empty_authority.password_digest == ""


def test_denial_postfix_is_appended_once(tmp_path: Path) -> None:
    """Append the configured postfix once to an unlisted-command denial.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    service = _create_service(
        tmp_path,
        [
            _entry(
                "worker",
                ["help"],
                disallow_message_postfix=POSTFIX,
            )
        ],
    )

    decision = service.evaluate_command_permission("query", "worker")

    assert decision.message.endswith(POSTFIX)
    assert decision.message.count(POSTFIX) == 1


def test_existing_postfix_is_not_duplicated_on_password_request(
    tmp_path: Path,
) -> None:
    """Avoid duplicating a postfix already present in the request message.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    message = f"Enter the user password. {POSTFIX}"
    service = _create_service(
        tmp_path,
        [
            _entry(
                "worker",
                ["delete-task"],
                ["delete-task"],
                ask_message=message,
                user_password=PASSWORD_DIGEST,
                disallow_message_postfix=POSTFIX,
            )
        ],
    )

    decision = service.evaluate_command_permission("delete-task", "worker")

    assert decision.status == "request_password"
    assert decision.message == message
    assert decision.message.count(POSTFIX) == 1


def test_repeated_trailing_postfixes_are_collapsed_with_whitespace(
    tmp_path: Path,
) -> None:
    """Collapse repeated postfix copies while retaining the message separator.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    message = f"Enter the user password. \t{POSTFIX}\n {POSTFIX}\r\n"
    service = _create_service(
        tmp_path,
        [
            _entry(
                "worker",
                ["delete-task"],
                ["delete-task"],
                ask_message=message,
                user_password=PASSWORD_DIGEST,
                disallow_message_postfix=POSTFIX,
            )
        ],
    )

    decision = service.evaluate_command_permission("delete-task", "worker")

    assert decision.message == f"Enter the user password. \t{POSTFIX}"
    assert decision.message.endswith(POSTFIX)
    assert decision.message.count(POSTFIX) == 1


def test_middle_postfix_does_not_suppress_final_postfix(
    tmp_path: Path,
) -> None:
    """Append the final postfix when an earlier copy is only in the middle.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    message = f"Existing {POSTFIX} text remains."
    service = _create_service(
        tmp_path,
        [
            _entry(
                "worker",
                ["delete-task"],
                ["delete-task"],
                ask_message=message,
                user_password=PASSWORD_DIGEST,
                disallow_message_postfix=POSTFIX,
            )
        ],
    )

    decision = service.evaluate_command_permission("delete-task", "worker")

    assert decision.message == f"{message} {POSTFIX}"
    assert decision.message.endswith(POSTFIX)
    assert decision.message.count(POSTFIX) == 2


def test_trailing_whitespace_is_preserved_before_new_postfix(
    tmp_path: Path,
) -> None:
    """Preserve existing trailing whitespace when adding a missing postfix.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    message = "Enter the user password.\t\n"
    service = _create_service(
        tmp_path,
        [
            _entry(
                "worker",
                ["delete-task"],
                ["delete-task"],
                ask_message=message,
                user_password=PASSWORD_DIGEST,
                disallow_message_postfix=POSTFIX,
            )
        ],
    )

    decision = service.evaluate_command_permission("delete-task", "worker")

    assert decision.message == f"{message}{POSTFIX}"
    assert decision.message.endswith(POSTFIX)
    assert decision.message.count(POSTFIX) == 1


def test_user_is_the_sole_bypass(tmp_path: Path) -> None:
    """Allow exact user authority without requiring a declared specification.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    service = _create_service(
        tmp_path,
        [
            _entry("worker", []),
        ],
    )

    user_decision = service.evaluate_command_permission("help", "user")
    nested_user_decision = service.evaluate_command_permission("help", "user.admin")
    unknown_decision = service.evaluate_command_permission("help", "unknown")

    assert user_decision == AuthorityDecision(status="execute", message="")
    assert nested_user_decision.status == "deny"
    assert unknown_decision.status == "deny"

    with pytest.raises(FrozenInstanceError):
        user_decision.status = "deny"  # type: ignore[misc]


def test_legacy_tuple_unpacking_remains_a_read_only_view(
    tmp_path: Path,
) -> None:
    """Keep existing command callers compatible with the typed decision object.

    Args:
        tmp_path: Temporary directory used for isolated configuration.

    Returns:
        None.
    """

    service = _create_service(tmp_path, [_entry("worker", ["help"])])

    allowed, message = service.evaluate_command_permission("help", "worker")

    assert allowed is True
    assert message == ""


def test_live_configuration_is_migrated_to_the_new_schema() -> None:
    """Verify the checked-in authority JSON preserves rules and removes legacy keys.

    Args:
        None.

    Returns:
        None.
    """

    config_path = Path("core/configs/brain_authority_config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert isinstance(config, list)
    assert len(config) == 2

    for entry in config:
        assert "name_word" in entry
        assert "prefix" not in entry
        assert "permission" not in entry
        assert "ask_acceptance_words" not in entry
        assert entry["user_password"] == ""

    assert config[0]["allowed"] == "all"
    assert config[0]["disallowed"] == [
        "delete-memory-entry",
        "delete-task",
        "rebuild-vectorstore",
        "wiki",
        "clone-snippet",
    ]
    assert config[1]["allowed"] == [
        "get-memory-entry",
        "eval-quality",
        "code-quality",
        "apply-patch",
        "help",
    ]
    assert config[1]["disallow_message_postfix"] == POSTFIX
