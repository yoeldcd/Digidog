"""Focused coverage for mandatory explicit CLI authority handling."""

from __future__ import annotations

import argparse
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from brain.application.authority.models import AuthorityDecision
from brain.presentation.commands.models import ArgumentSchema, CommandSchema
from brain.presentation.parser.services.argument_parser_service import (
    build_argument_parser,
)
from brain.presentation.parser.services.global_flags_service import (
    extract_global_flags,
)
from brain.presentation.router.services import (
    cli_runtime_service,
    command_router_service,
)

REQUIRED_AUTHORITY_MESSAGE = (
    "Required Command Authority flag  --authority <AUTHORITY> to execute scoped command"
)
REQUIRED_HELP_AUTHORITY_MESSAGE = (
    "Required Command Authority flag  --authority <UTHORITY> to read scoped help."
)


def test_omitted_authority_uses_orchestrator_fallback_and_marks_omission() -> None:
    """Return the compatibility value without marking authority as explicit.

    Args:
        None.

    Returns:
        None.
    """
    assert extract_global_flags(["list-profiles"]) == (
        ["list-profiles"],
        False,
        False,
        "orchestrator",
        False,
        False,
    )


@pytest.mark.parametrize(
    ("argv", "expected_argv", "expected_authority"),
    [
        (
            ["get-memory-entry", "domain.key", "--authority", "worker"],
            ["get-memory-entry", "domain.key"],
            "worker",
        ),
        (
            ["--authority=root", "get-memory-entry", "domain.key"],
            ["get-memory-entry", "domain.key"],
            "root",
        ),
        (
            ["get-memory-entry", "domain.key", "--authority=user"],
            ["get-memory-entry", "domain.key"],
            "user",
        ),
    ],
)
def test_authority_extraction_preserves_positional_and_inline_placement(
    argv: list[str],
    expected_argv: list[str],
    expected_authority: str,
) -> None:
    """Remove authority syntax without disturbing positional arguments.

    Args:
        argv: Raw command arguments containing authority syntax.
        expected_argv: Command arguments expected after global flag extraction.
        expected_authority: Authority value expected from the supplied syntax.

    Returns:
        None.
    """
    assert extract_global_flags(argv) == (
        expected_argv,
        False,
        False,
        expected_authority,
        True,
        False,
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["list-profiles", "--authority", ""],
        ["list-profiles", "--authority="],
        ["list-profiles", "--authority"],
    ],
)
def test_empty_authority_remains_distinct_from_omission(argv: list[str]) -> None:
    """Expose empty explicit values so runtime validation can reject them.

    Args:
        argv: Authority spelling carrying no usable value.

    Returns:
        None.
    """
    (
        cleaned_argv,
        color_enabled,
        verbose_log,
        authority,
        authority_provided,
        password_stdin,
    ) = extract_global_flags(argv)

    assert cleaned_argv == ["list-profiles"]
    assert color_enabled is False
    assert verbose_log is False
    assert authority == ""
    assert authority_provided is True
    assert password_stdin is False


def test_omitted_authority_rejects_terminal_dispatch_before_side_effects(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject omitted authority before permission evaluation or dispatch.

    Args:
        capsys: Pytest capture fixture for terminal output assertions.

    Returns:
        None.
    """

    with (
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        exit_code = cli_runtime_service.run_cli(["list-profiles"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"Error: {REQUIRED_AUTHORITY_MESSAGE}\n"
    authority_service.assert_not_called()
    dispatch.assert_not_called()


def test_omitted_authority_preflights_before_argparse_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject a help request before argparse can bypass the authority guard.

    Args:
        capsys: Pytest capture fixture for terminal output assertions.

    Returns:
        None.
    """

    with (
        patch.object(cli_runtime_service, "build_argument_parser") as build_parser,
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
    ):
        exit_code = cli_runtime_service.run_cli(["get-memory-entry", "--help"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"Error: {REQUIRED_AUTHORITY_MESSAGE}\n"
    build_parser.assert_not_called()
    authority_service.assert_not_called()


def test_omitted_authority_uses_help_specific_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Use the exact read-scoped message for the top-level help command.

    Args:
        capsys: Pytest capture fixture for terminal output assertions.

    Returns:
        None.
    """

    with (
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        exit_code = cli_runtime_service.run_cli(["help"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"Error: {REQUIRED_HELP_AUTHORITY_MESSAGE}\n"
    authority_service.assert_not_called()
    dispatch.assert_not_called()


@pytest.mark.parametrize(
    "argv",
    [
        ["list-profiles", "--authority=", "--json"],
        ["list-profiles", "--authority", "", "--json"],
        ["list-profiles", "--authority", "--json"],
    ],
)
def test_empty_authority_rejects_json_dispatch_before_side_effects(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return the exact JSON error schema for empty authority spellings.

    Args:
        argv: Explicit but empty authority argument vector.
        capsys: Pytest capture fixture for JSON output assertions.

    Returns:
        None.
    """

    with (
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        exit_code = cli_runtime_service.run_cli(argv)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "ok": False,
        "command": "list-profiles",
        "error": REQUIRED_AUTHORITY_MESSAGE,
    }
    authority_service.assert_not_called()
    dispatch.assert_not_called()


@pytest.mark.parametrize("authority", ["user", "root", "orchestrator", "worker"])
def test_explicit_authority_reaches_permission_service_and_dispatch(
    authority: str,
) -> None:
    """Preserve explicit built-in and worker authorities through dispatch.

    Args:
        authority: Explicit caller authority expected at the permission boundary.

    Returns:
        None.
    """

    with (
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "dispatch_command", return_value=0) as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (True, "")
        exit_code = cli_runtime_service.run_cli(["list-profiles", "--authority", authority])

    assert exit_code == 0
    authority_service.return_value.evaluate_command_permission.assert_called_once_with(
        command_name="list-profiles",
        authority=authority,
    )
    dispatch.assert_called_once()
    parsed_args = dispatch.call_args.kwargs["args"]
    assert parsed_args.authority == authority
    assert parsed_args.authority_provided is True
    assert parsed_args.authority_verified is True


def test_explicit_help_authority_keeps_existing_help_dispatch_path() -> None:
    """Allow explicitly authorized help to reach its existing handler.

    Args:
        None.

    Returns:
        None.
    """

    with (
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "dispatch_command", return_value=0) as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (True, "")
        exit_code = cli_runtime_service.run_cli(["help", "--authority=orchestrator"])

    assert exit_code == 0
    authority_service.return_value.evaluate_command_permission.assert_called_once_with(
        command_name="help",
        authority="orchestrator",
    )
    dispatch.assert_called_once()
    parsed_args = dispatch.call_args.kwargs["args"]
    assert parsed_args.command == "help"
    assert parsed_args.authority == "orchestrator"
    assert parsed_args.authority_provided is True


def test_permission_denial_still_uses_existing_authority_rules_before_dispatch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep permission denial text and dispatch ordering unchanged.

    Args:
        capsys: Pytest capture fixture for terminal denial assertions.

    Returns:
        None.
    """
    denial_reason = "existing authority denial"

    with (
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            False,
            denial_reason,
        )
        exit_code = cli_runtime_service.run_cli(["list-profiles", "--authority", "worker"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"Error: {denial_reason}\n"
    dispatch.assert_not_called()


def test_unauthorized_help_is_rejected_before_argparse_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject denied command help before argparse can expose its documentation.

    Args:
        capsys: Pytest capture fixture for terminal output assertions.

    Returns:
        None.
    """

    denial_reason = "Help is restricted for the selected authority."

    with (
        patch.object(cli_runtime_service, "build_argument_parser") as parser_builder,
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            False,
            denial_reason,
        )
        exit_code = cli_runtime_service.run_cli(
            ["list-profiles", "--help", "--authority", "worker"]
        )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"Error: {denial_reason}\n"
    assert "usage:" not in captured.err.casefold()
    parser_builder.assert_not_called()
    authority_service.return_value.evaluate_command_permission.assert_called_once_with(
        command_name="list-profiles",
        authority="worker",
    )


def test_parser_errors_are_generic_and_redact_rejected_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Hide one invalid typed value behind the stable generic parser error.

    Args:
        capsys: Pytest capture fixture for terminal output assertions.

    Returns:
        None.
    """

    rejected_value = "secret-rejected-value"
    schema = CommandSchema(
        name="parse-check",
        help="Check safe parser errors.",
        arguments=[ArgumentSchema(flags=["--count"], type="int")],
    )
    parser = build_argument_parser([SimpleNamespace(SCHEMA=schema)])

    with pytest.raises(SystemExit) as raised:
        parser.parse_args(["parse-check", "--count", rejected_value])

    captured = capsys.readouterr()
    assert raised.value.code == 2
    assert captured.out == ""
    assert captured.err == "Error: Invalid command arguments.\n"
    assert rejected_value not in captured.out + captured.err


def test_router_rejects_direct_dispatch_without_authority_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fail closed when the router is invoked without runtime authority context.

    Args:
        capsys: Pytest capture fixture for terminal output assertions.

    Returns:
        None.
    """

    handler = Mock(return_value=0)
    args = argparse.Namespace(command="list-profiles", no_speak=True)

    with patch.object(
        command_router_service,
        "get_action_handler",
        return_value=handler,
    ) as action_lookup:
        exit_code = command_router_service.dispatch_command(args)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Required Command Authority" in captured.err
    action_lookup.assert_not_called()


def test_router_uses_help_specific_message_without_authority(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Use the exact read-scoped message for direct help dispatch.

    Args:
        capsys: Pytest capture fixture for terminal output assertions.

    Returns:
        None.
    """

    handler = Mock(return_value=0)
    args = argparse.Namespace(command="help", no_speak=True)

    with patch.object(
        command_router_service,
        "get_action_handler",
        return_value=handler,
    ) as action_lookup:
        exit_code = command_router_service.dispatch_command(args)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"Error: {REQUIRED_HELP_AUTHORITY_MESSAGE}\n"
    action_lookup.assert_not_called()


def test_router_revalidates_denial_before_handler_lookup() -> None:
    """Honor a fresh deny decision without resolving or invoking a handler.

    Args:
        None.

    Returns:
        None.
    """

    denial_reason = "The router denied this command."
    args = argparse.Namespace(
        command="list-profiles",
        authority="worker",
        authority_provided=True,
        authority_verified=True,
        no_speak=True,
    )

    with (
        patch.object(command_router_service, "AuthorityService") as authority_service,
        patch.object(command_router_service, "get_action_handler") as action_lookup,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            AuthorityDecision(status="deny", message=denial_reason)
        )
        exit_code = command_router_service.dispatch_command(args)

    assert exit_code == 1
    action_lookup.assert_not_called()
    authority_service.return_value.evaluate_command_permission.assert_called_once_with(
        command_name="list-profiles",
        authority="worker",
    )


@pytest.mark.parametrize("verified", [False, True])
def test_router_request_requires_only_the_nonsecret_verified_marker(
    verified: bool,
) -> None:
    """Dispatch a password-requested command only after marker verification.

    Args:
        verified: Whether the runtime supplied its nonsecret verification marker.

    Returns:
        None.
    """

    handler = Mock(return_value=0)
    args = argparse.Namespace(
        command="protected-command",
        authority="worker",
        authority_provided=True,
        authority_verified=verified,
        no_speak=True,
        json=False,
        color=False,
    )

    with (
        patch.object(command_router_service, "AuthorityService") as authority_service,
        patch.object(
            command_router_service,
            "get_action_handler",
            return_value=handler,
        ) as action_lookup,
        patch.object(command_router_service, "VoiceSignalService"),
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            AuthorityDecision(
                status="request_password",
                message="Password verification required.",
                password_digest="a" * 64,
            )
        )
        exit_code = command_router_service.dispatch_command(args)

    if verified:
        assert exit_code == 0
        action_lookup.assert_called_once_with(command_name="protected-command")

    else:
        assert exit_code == 1
        action_lookup.assert_not_called()


def test_router_rejects_unverified_cli_namespace_before_handler(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject a router call that lacks the runtime's non-secret marker.

    Args:
        capsys: Pytest capture fixture for JSON output assertions.

    Returns:
        None.
    """

    args = argparse.Namespace(
        command="get-memory-entry",
        authority="worker",
        authority_provided=True,
        json=True,
        color=False,
        no_speak=True,
    )

    with (
        patch.object(command_router_service, "AuthorityService") as authority_service,
        patch.object(command_router_service, "get_action_handler") as action_handler,
    ):
        exit_code = command_router_service.dispatch_command(args)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "ok": False,
        "command": "get-memory-entry",
        "error": "Unable to evaluate command authority.",
    }
    authority_service.assert_not_called()
    action_handler.assert_not_called()


def test_router_accepts_verified_marker_after_independent_revalidation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Dispatch only after router authority revalidation accepts the marker.

    Args:
        capsys: Pytest capture fixture for JSON output assertions.

    Returns:
        None.
    """

    args = argparse.Namespace(
        command="get-memory-entry",
        authority="worker",
        authority_provided=True,
        authority_verified=True,
        json=True,
        color=False,
        no_speak=True,
    )

    def handler(handler_args: argparse.Namespace) -> int:
        """Provide a semantic JSON payload for the routed test command.

        Args:
            handler_args: Namespace passed through the router.

        Returns:
            int: Successful handler status.
        """

        handler_args.json_payload = {"ok": True, "command": "get-memory-entry"}

        return 0

    with (
        patch.object(command_router_service, "AuthorityService") as authority_service,
        patch.object(
            command_router_service,
            "get_action_handler",
            return_value=handler,
        ) as action_handler,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            True,
            "",
        )
        exit_code = command_router_service.dispatch_command(args)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "ok": True,
        "command": "get-memory-entry",
    }
    authority_service.return_value.evaluate_command_permission.assert_called_once_with(
        command_name="get-memory-entry",
        authority="worker",
    )
    action_handler.assert_called_once_with(command_name="get-memory-entry")
