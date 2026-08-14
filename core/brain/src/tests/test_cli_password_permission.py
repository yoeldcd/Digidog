"""Focused coverage for the runtime password permission channel."""

from __future__ import annotations

import argparse
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from brain.application.authority.models import AuthorityDecision
from brain.application.authority.passwords import hash_password
from brain.presentation.actions.general import command_show_help
from brain.presentation.commands.models import CommandSchema
from brain.presentation.parser.services.global_flags_service import (
    extract_global_flags,
)
from brain.presentation.router.services import cli_runtime_service
from brain.presentation.views.help import rendering

REQUEST_MESSAGE = "Enter the protected password. Sub-agent context."
CANDIDATE_PASSWORD = "candidate-value"
PASSWORD_DIGEST = hash_password(CANDIDATE_PASSWORD)


def _build_test_parser() -> argparse.ArgumentParser:
    """Build the smallest parser needed to exercise the runtime boundary.

    Args:
        None.

    Returns:
        argparse.ArgumentParser: Parser that accepts the test command and
        common JSON and authority options.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    command_parser = subparsers.add_parser("protected-command")
    command_parser.add_argument("--json", action="store_true")
    command_parser.add_argument("--authority", default="orchestrator")

    return parser


def _request_decision(
    password_digest: str = PASSWORD_DIGEST,
) -> AuthorityDecision:
    """Create one password-request decision for runtime tests.

    Args:
        password_digest: Configured digest, or an empty digest for fail-closed
            request testing.

    Returns:
        AuthorityDecision: Immutable request decision with safe context.
    """

    return AuthorityDecision(
        status="request_password",
        message=REQUEST_MESSAGE,
        password_digest=password_digest,
    )


def test_password_stdin_is_removed_before_argparse() -> None:
    """Extract the boolean channel without retaining it as a command argument.

    Args:
        None.

    Returns:
        None.
    """
    extracted = extract_global_flags(
        ["protected-command", "--password-stdin", "--authority", "worker"]
    )

    assert extracted == (
        ["protected-command"],
        False,
        False,
        "worker",
        True,
        True,
    )


def test_parser_error_is_generic_and_does_not_echo_raw_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Redact invalid parser input while preserving the failure contract.

    Args:
        capsys: Pytest capture fixture for terminal output assertions.

    Returns:
        None.
    """

    raw_secret = "candidate-secret-value"

    with (
        patch.object(
            cli_runtime_service,
            "build_argument_parser",
            return_value=_build_test_parser(),
        ),
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            AuthorityDecision(status="execute", message="")
        )
        exit_code = cli_runtime_service.run_cli(
            ["protected-command", "--authority", "worker", "--unexpected", raw_secret]
        )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "Error: Invalid command arguments.\n"
    assert raw_secret not in captured.out + captured.err
    dispatch.assert_not_called()


@pytest.mark.parametrize("json_mode", [False, True])
def test_empty_digest_fails_closed_without_prompt_or_dispatch(
    json_mode: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return the request message when a password request has no digest.

    Args:
        json_mode: Whether to exercise terminal or JSON output.
        capsys: Pytest output capture fixture.

    Returns:
        None.
    """
    argv = ["protected-command", "--authority", "worker"]

    if json_mode:
        argv.append("--json")

    with (
        patch.object(
            cli_runtime_service,
            "build_argument_parser",
            return_value=_build_test_parser(),
        ),
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "read_password") as hidden_reader,
        patch.object(cli_runtime_service, "read_password_from_stdin") as stdin_reader,
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            _request_decision(password_digest="")
        )
        exit_code = cli_runtime_service.run_cli(argv)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert REQUEST_MESSAGE in captured.out + captured.err
    hidden_reader.assert_not_called()
    stdin_reader.assert_not_called()
    dispatch.assert_not_called()

    if json_mode:
        assert json.loads(captured.out)["error"] == REQUEST_MESSAGE
        assert captured.err == ""


def test_password_stdin_validates_and_dispatches_without_namespace_secret() -> None:
    """Read the password from one global stdin channel and dispatch securely.

    Args:
        None.

    Returns:
        None.
    """
    captured_arguments: list[argparse.Namespace] = []

    def dispatch(args: argparse.Namespace) -> int:
        """Capture dispatched arguments and return success.

        Args:
            args: Parsed runtime namespace.

        Returns:
            int: Successful command status.
        """
        captured_arguments.append(args)

        return 0

    with (
        patch.object(
            cli_runtime_service,
            "build_argument_parser",
            return_value=_build_test_parser(),
        ),
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(
            cli_runtime_service,
            "read_password_from_stdin",
            return_value=CANDIDATE_PASSWORD,
        ) as stdin_reader,
        patch.object(cli_runtime_service, "read_password") as hidden_reader,
        patch.object(
            cli_runtime_service,
            "dispatch_command",
            side_effect=dispatch,
        ) as command_dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            _request_decision()
        )
        exit_code = cli_runtime_service.run_cli(
            ["protected-command", "--authority", "worker", "--password-stdin"]
        )

    assert exit_code == 0
    stdin_reader.assert_called_once_with()
    hidden_reader.assert_not_called()
    command_dispatch.assert_called_once()
    assert len(captured_arguments) == 1
    assert not hasattr(captured_arguments[0], "password_stdin")
    assert captured_arguments[0].authority_verified is True
    assert CANDIDATE_PASSWORD not in vars(captured_arguments[0])


def test_password_stdin_rejects_tty_before_reading(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Refuse the explicit stdin password channel when stdin is interactive.

    Args:
        capsys: Pytest capture fixture for terminal output assertions.

    Returns:
        None.
    """

    with (
        patch.object(
            cli_runtime_service,
            "build_argument_parser",
            return_value=_build_test_parser(),
        ),
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "_stdin_is_tty", return_value=True),
        patch.object(cli_runtime_service, "read_password_from_stdin") as stdin_reader,
        patch.object(cli_runtime_service, "read_password") as hidden_reader,
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            _request_decision()
        )
        exit_code = cli_runtime_service.run_cli(
            ["protected-command", "--authority", "worker", "--password-stdin"]
        )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == (
        "Error: Password input from stdin requires a non-interactive stream.\n"
    )
    stdin_reader.assert_not_called()
    hidden_reader.assert_not_called()
    dispatch.assert_not_called()


def test_tty_uses_hidden_reader_and_dispatches() -> None:
    """Use the hidden reader for a non-JSON interactive terminal request.

    Args:
        None.

    Returns:
        None.
    """

    with (
        patch.object(
            cli_runtime_service,
            "build_argument_parser",
            return_value=_build_test_parser(),
        ),
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(
            cli_runtime_service,
            "_stdin_is_tty",
            return_value=True,
        ),
        patch.object(
            cli_runtime_service,
            "read_password",
            return_value=CANDIDATE_PASSWORD,
        ) as hidden_reader,
        patch.object(
            cli_runtime_service,
            "verify_password",
            return_value=True,
        ),
        patch.object(cli_runtime_service, "dispatch_command", return_value=0) as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            _request_decision()
        )
        exit_code = cli_runtime_service.run_cli(
            ["protected-command", "--authority", "worker"]
        )

    assert exit_code == 0
    hidden_reader.assert_called_once_with(prompt=REQUEST_MESSAGE)
    dispatch.assert_called_once()


def test_json_non_tty_without_stdin_fails_closed_before_dispatch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Refuse to prompt in JSON mode when no explicit stdin channel exists.

    Args:
        capsys: Pytest output capture fixture.

    Returns:
        None.
    """

    with (
        patch.object(
            cli_runtime_service,
            "build_argument_parser",
            return_value=_build_test_parser(),
        ),
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "_stdin_is_tty", return_value=False),
        patch.object(cli_runtime_service, "read_password") as hidden_reader,
        patch.object(cli_runtime_service, "read_password_from_stdin") as stdin_reader,
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            _request_decision()
        )
        exit_code = cli_runtime_service.run_cli(
            ["protected-command", "--authority", "worker", "--json"]
        )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == {
        "ok": False,
        "command": "protected-command",
        "error": REQUEST_MESSAGE,
    }
    assert captured.err == ""
    hidden_reader.assert_not_called()
    stdin_reader.assert_not_called()
    dispatch.assert_not_called()


def test_invalid_password_denies_with_request_context_without_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Deny a wrong candidate while retaining configured request context.

    Args:
        capsys: Pytest output capture fixture.

    Returns:
        None.
    """
    invalid_candidate = "invalid-candidate"

    with (
        patch.object(
            cli_runtime_service,
            "build_argument_parser",
            return_value=_build_test_parser(),
        ),
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(
            cli_runtime_service,
            "read_password_from_stdin",
            return_value=invalid_candidate,
        ),
        patch.object(cli_runtime_service, "verify_password", return_value=False),
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            _request_decision()
        )
        exit_code = cli_runtime_service.run_cli(
            ["protected-command", "--authority", "worker", "--password-stdin"]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exit_code == 1
    assert captured.out == ""
    assert combined_output == f"Error: Invalid password. {REQUEST_MESSAGE}\n"
    assert invalid_candidate not in combined_output
    assert dispatch.call_count == 0


@pytest.mark.parametrize("json_mode", [False, True])
def test_deny_decision_preserves_exact_message(
    json_mode: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Render a deny decision without replacing its configured message.

    Args:
        json_mode: Whether to exercise terminal or JSON output.
        capsys: Pytest output capture fixture.

    Returns:
        None.
    """
    denial_message = "This command is restricted for the selected authority."
    argv = ["protected-command", "--authority", "worker"]

    if json_mode:
        argv.append("--json")

    with (
        patch.object(
            cli_runtime_service,
            "build_argument_parser",
            return_value=_build_test_parser(),
        ),
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            AuthorityDecision(status="deny", message=denial_message)
        )
        exit_code = cli_runtime_service.run_cli(argv)

    captured = capsys.readouterr()
    assert exit_code == 1
    dispatch.assert_not_called()

    if json_mode:
        assert json.loads(captured.out)["error"] == denial_message
        assert captured.err == ""

    else:
        assert captured.out == ""
        assert captured.err == f"Error: {denial_message}\n"


def test_help_retains_password_requests_and_hides_denials() -> None:
    """Keep password-requested schemas visible while omitting denied schemas.

    Args:
        None.

    Returns:
        None.
    """
    help_schema = CommandSchema(name="help", help="Show help.")
    protected_schema = CommandSchema(
        name="protected-command",
        help="Run a protected command.",
        domain="security",
    )
    denied_schema = CommandSchema(
        name="denied-command",
        help="Do not show this command.",
        domain="security",
    )
    command_modules = [
        SimpleNamespace(SCHEMA=help_schema),
        SimpleNamespace(SCHEMA=protected_schema),
        SimpleNamespace(SCHEMA=denied_schema),
    ]

    def permission(
        command_name: str,
        authority: str,
    ) -> AuthorityDecision:
        """Return a deterministic decision for each fake schema.

        Args:
            command_name: Schema name being checked.
            authority: Caller authority under test.

        Returns:
            AuthorityDecision: Execute, request, or deny result for the schema.
        """
        assert authority == "worker"

        if command_name == "protected-command":
            return _request_decision()

        if command_name == "denied-command":
            return AuthorityDecision(status="deny", message="hidden")

        return AuthorityDecision(status="execute", message="")

    with (
        patch(
            "brain.presentation.commands.registry.COMMAND_MODULES",
            command_modules,
        ),
        patch.object(rendering, "AuthorityService") as authority_service,
    ):
        authority_service.return_value.evaluate_command_permission.side_effect = (
            permission
        )
        rendered = rendering.get_help_text(authority="worker")
        short = rendering.get_short_help_text(authority="worker")
        args = argparse.Namespace(
            topic=None,
            short=False,
            color=False,
            authority="worker",
        )
        assert command_show_help.handle(args) == 0

    assert "protected-command" in rendered
    assert "[password required]" in rendered
    assert "--password-stdin" in rendered
    assert "denied-command" not in rendered
    assert "protected-command [password required]" in short
    assert "denied-command" not in short

    command_names = {
        command["name"]: command
        for command in args.json_payload["commands"]
    }
    assert set(command_names) == {"help", "protected-command"}
    assert command_names["protected-command"]["requires_password"] is True
    assert "requires_password" not in command_names["help"]


def test_color_terminal_denial_preserves_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Render a terminal denial with the canonical red ANSI wrapper.

    Args:
        capsys: Pytest output capture fixture.

    Returns:
        None.
    """
    denial_message = "This command is restricted for the selected authority."

    with (
        patch.object(
            cli_runtime_service,
            "build_argument_parser",
            return_value=_build_test_parser(),
        ),
        patch.object(cli_runtime_service, "AuthorityService") as authority_service,
        patch.object(cli_runtime_service, "dispatch_command") as dispatch,
    ):
        authority_service.return_value.evaluate_command_permission.return_value = (
            AuthorityDecision(status="deny", message=denial_message)
        )
        exit_code = cli_runtime_service.run_cli(
            ["protected-command", "--authority", "worker", "--color"]
        )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"\033[31mError: {denial_message}\033[0m\n"
    dispatch.assert_not_called()
