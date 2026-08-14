"""Focused contracts for the user-only generate-pwd command."""

from __future__ import annotations

import argparse
import io
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from brain.application.authority import passwords
from brain.presentation.actions.general import command_generate_pwd
from brain.presentation.actions.registry import ACTION_HANDLERS
from brain.presentation.commands.general import command_generate_pwd as command_generate_pwd_command
from brain.presentation.commands.general.command_generate_pwd import SCHEMA
from brain.presentation.commands.registry import COMMAND_MODULES
from brain.presentation.parser.services.argument_parser_service import (
    build_argument_parser,
)
from brain.presentation.router.services.command_router_service import dispatch_command
from brain.presentation.router.services.narration_policy import (
    build_narration_draft,
    narration_for,
    render_without_refinement,
)


def _user_args(*, stdin: bool = False, json_output: bool = False) -> argparse.Namespace:
    """Build the smallest direct-action namespace for the user authority.

    Args:
        stdin: Whether the action should read the strict stdin utility.
        json_output: Whether the action should prepare machine-readable output.

    Returns:
        argparse.Namespace: Direct action arguments with the required authority.
    """

    return argparse.Namespace(
        authority="user",
        stdin=stdin,
        json=json_output,
        color=False,
    )


def test_schema_exposes_only_boolean_stdin_input_and_rejects_value_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep password material out of argv and expose only the boolean stdin flag.

    Args:
        monkeypatch: Pytest fixture used to provide the parser workspace root.

    Returns:
        None.
    """

    assert SCHEMA.name == "generate-pwd"
    assert [
        (argument.flags, argument.action, argument.type, argument.nargs)
        for argument in SCHEMA.arguments
    ] == [
        (["--stdin"], "store_true", None, None),
    ]

    monkeypatch.setenv("WORKSPACE_ROOT", ".")
    parser = build_argument_parser([SimpleNamespace(SCHEMA=SCHEMA)])
    parsed = parser.parse_args(
        ["generate-pwd", "--stdin", "--json", "--authority", "user"]
    )

    assert parsed.stdin is True
    assert parsed.json is True
    assert parsed.authority == "user"

    for invalid_arguments in (
        ["generate-pwd", "candidate"],
        ["generate-pwd", "--password", "candidate"],
        ["generate-pwd", "--stdin", "candidate"],
    ):
        with pytest.raises(SystemExit):
            parser.parse_args(invalid_arguments)


def test_hidden_reader_uses_known_sha256_vector_and_prints_only_the_digest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Use the default hidden reader path without echoing source input.

    Args:
        capsys: Pytest capture fixture used to inspect terminal output.

    Returns:
        None.
    """

    args = _user_args()

    with (
        patch.object(
            command_generate_pwd.sys,
            "stdin",
            SimpleNamespace(isatty=lambda: True),
        ),
        patch.object(command_generate_pwd, "read_password", return_value="abc") as reader,
    ):
        assert command_generate_pwd.handle(args) == 0

    captured = capsys.readouterr()
    expected_digest = (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )

    reader.assert_called_once_with()
    assert captured.out == f"{expected_digest}\n"
    assert captured.err == ""
    assert "abc" not in captured.out
    assert args.json_payload == {
        "ok": True,
        "command": "generate-pwd",
        "hash": expected_digest,
    }
    assert args.narration_output == ""


def test_non_tty_hidden_reader_fails_closed_without_prompting(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject hidden input on non-interactive stdin without invoking the reader.

    Args:
        capsys: Pytest capture fixture used to inspect terminal diagnostics.

    Returns:
        None.
    """

    args = _user_args()

    with (
        patch.object(
            command_generate_pwd.sys,
            "stdin",
            SimpleNamespace(isatty=lambda: False),
        ),
        patch.object(command_generate_pwd, "read_password") as reader,
    ):
        assert command_generate_pwd.handle(args) == 1

    reader.assert_not_called()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Error: Password input was rejected.\n"
    assert args.json_payload == {
        "ok": False,
        "command": "generate-pwd",
        "error": "Password input was rejected.",
    }


def test_stdin_utility_preserves_unicode_utf8_hashing() -> None:
    """Hash a Unicode stdin value using the shared strict input utility.

    Args:
        None.

    Returns:
        None.
    """

    args = _user_args(stdin=True)

    with patch.object(command_generate_pwd.sys, "stdin", io.StringIO("é\n")):
        assert command_generate_pwd.handle(args) == 0

    assert args.json_payload == {
        "ok": True,
        "command": "generate-pwd",
        "hash": "4a99557e4033c3539de2eb65472017cad5f9557f7a0625a09f1c3f6e2ba69c4c",
    }


@pytest.mark.parametrize("payload", ("", "\n", "candidate\nextra\n"))
def test_stdin_utility_rejects_empty_and_multiline_input(
    payload: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fail closed for empty or multiline stdin without echoing payload text.

    Args:
        payload: Invalid input framing supplied to the strict stdin utility.
        capsys: Pytest capture fixture used to inspect terminal diagnostics.

    Returns:
        None.
    """

    args = _user_args(stdin=True)

    with patch.object(command_generate_pwd.sys, "stdin", io.StringIO(payload)):
        assert command_generate_pwd.handle(args) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Password input was rejected." in captured.err

    if payload.strip():
        assert payload.strip() not in captured.err
    assert args.json_payload == {
        "ok": False,
        "command": "generate-pwd",
        "error": "Password input was rejected.",
    }


def test_reader_error_is_redacted_and_does_not_escape_the_action(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Convert an injected reader failure into a source-redacted error payload.

    Args:
        capsys: Pytest capture fixture used to inspect terminal diagnostics.

    Returns:
        None.
    """

    args = _user_args()

    with patch.object(
        command_generate_pwd,
        "read_password",
        side_effect=RuntimeError("candidate"),
    ):
        assert command_generate_pwd.handle(args) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Error: Password input was rejected.\n"
    assert "candidate" not in captured.err


@pytest.mark.parametrize("authority", ("worker", "User", None))
def test_direct_action_requires_exact_user_authority(
    authority: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Deny every direct invocation whose authority is not exactly user.

    Args:
        authority: Direct caller authority under test.
        capsys: Pytest capture fixture used to inspect terminal diagnostics.

    Returns:
        None.
    """

    args = argparse.Namespace(
        authority=authority,
        stdin=False,
        json=False,
        color=False,
    )

    with patch.object(command_generate_pwd, "read_password") as reader:
        assert command_generate_pwd.handle(args) == 1

    captured = capsys.readouterr()
    reader.assert_not_called()
    assert captured.out == ""
    assert captured.err == "Error: generate-pwd requires exact --authority user.\n"


def test_json_noninteractive_without_stdin_fails_closed_without_prompting() -> None:
    """Reject a non-interactive JSON prompt request before invoking getpass.

    Args:
        None.

    Returns:
        None.
    """

    args = _user_args(json_output=True)

    with (
        patch.object(command_generate_pwd.sys, "stdin", io.StringIO("")),
        patch.object(command_generate_pwd, "read_password") as reader,
    ):
        assert command_generate_pwd.handle(args) == 1

    reader.assert_not_called()
    assert args.json_payload == {
        "ok": False,
        "command": "generate-pwd",
        "error": "Password input was rejected.",
    }


def test_json_dispatch_emits_exact_hash_only_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise the router JSON boundary and verify the public payload shape.

    Args:
        capsys: Pytest capture fixture used to inspect serialized output.

    Returns:
        None.
    """

    args = argparse.Namespace(
        command="generate-pwd",
        authority="user",
        authority_provided=True,
        authority_verified=True,
        stdin=True,
        json=True,
        no_speak=True,
        color=False,
    )

    with (
        patch.object(command_generate_pwd.sys, "stdin", io.StringIO("abc\n")),
        patch(
            "brain.presentation.router.services.command_router_service.VoiceSignalService"
        ),
    ):
        assert dispatch_command(args) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "ok": True,
        "command": "generate-pwd",
        "hash": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    }


def test_registry_manual_and_narration_contracts_align_without_secret_facts() -> None:
    """Keep command registration, manual metadata, and safe narration aligned.

    Args:
        None.

    Returns:
        None.
    """

    assert command_generate_pwd_command in COMMAND_MODULES
    assert ACTION_HANDLERS["generate-pwd"] == (
        "brain.presentation.actions.general.command_generate_pwd"
    )
    assert SCHEMA.examples
    assert SCHEMA.output_schemas

    narration = narration_for("generate-pwd", argparse.Namespace())
    assert narration is not None
    assert narration.refine_with_llm is False
    assert "password" not in narration.call_template.casefold()
    assert "password" not in narration.output_template.casefold()

    digest = passwords.hash_password("abc")
    draft = build_narration_draft(
        command="generate-pwd",
        template=narration.output_template,
        args=argparse.Namespace(
            json_payload={"ok": True, "command": "generate-pwd", "hash": digest},
            narration_output="",
        ),
        output="",
        phase="output",
    )

    assert digest not in render_without_refinement(draft)
