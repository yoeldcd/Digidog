"""Write-free regression coverage for the complete help JSON catalog."""

from __future__ import annotations

import argparse
import json
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from brain.application.authority.models import AuthorityDecision
from brain.presentation.actions.general.command_show_help import handle
from brain.presentation.commands.models import CommandSchema


PASSWORD_DIGEST = "a" * 64


def _terminal_visibility_permission(
    command_name: str,
    authority: str,
) -> AuthorityDecision:
    """Return terminal visibility decisions for execute, deny, and request branches.

    Args:
        command_name: Registered command name evaluated by help rendering.
        authority: Authority passed through the help visibility boundary.

    Returns:
        AuthorityDecision: Deterministic decision for the test command.
    """
    assert authority == "worker"

    if command_name == "help":
        return AuthorityDecision(status="execute", message="")

    if command_name == "serve-explorer":
        return AuthorityDecision(status="execute", message="")

    if command_name == "delete-task":
        return AuthorityDecision(
            status="request_password",
            message="Enter the user password.",
            password_digest=PASSWORD_DIGEST,
        )

    return AuthorityDecision(status="deny", message="hidden")


def test_help_catalog_is_json_serializable_with_named_types() -> None:
    """Every registered command schema must render without Python type objects.

    Args:
        None.

    Returns:
        None: Assertions complete when the help payload is JSON serializable.
    """
    args = argparse.Namespace(topic=None, short=False, color=False, authority="user")

    with redirect_stdout(StringIO()):
        assert handle(args) == 0
    encoded = json.dumps(args.json_payload, ensure_ascii=False)
    assert '"type": "int"' in encoded
    assert args.json_payload["count"] > 0


def test_topic_help_keeps_alias_and_domain_filtering() -> None:
    """JSON conversion must preserve the existing topic-selection contract.

    Args:
        None.

    Returns:
        None: Assertions complete when the topic payload is correctly filtered.
    """
    args = argparse.Namespace(
        topic="serve-explorer",
        short=False,
        color=False,
        authority="user",
    )

    with redirect_stdout(StringIO()):
        assert handle(args) == 0
    assert args.json_payload["count"] == 1
    assert args.json_payload["commands"][0]["name"] == "serve-explorer"
    json.dumps(args.json_payload)


@pytest.mark.parametrize("topic", [None, "serve-explorer"])
def test_help_catalog_hides_schemas_when_authority_is_missing(
    topic: str | None,
) -> None:
    """Help JSON must not expose command schemas without explicit authority.

    Args:
        topic: Optional topic supplied without caller authority.

    Returns:
        None: Assertions complete when the missing-authority payload is empty.
    """
    args = argparse.Namespace(topic=topic, short=False, color=False)

    with redirect_stdout(StringIO()):
        assert handle(args) == 0

    assert args.json_payload["count"] == 0
    assert args.json_payload["commands"] == []


@pytest.mark.parametrize("authority", ["", "   "])
def test_help_catalog_hides_schemas_when_authority_is_blank(authority: str) -> None:
    """Help JSON must fail closed for explicit blank authority values.

    Args:
        authority: Explicit blank authority spelling under test.

    Returns:
        None: Assertions complete when the blank-authority payload is empty.
    """
    args = argparse.Namespace(
        topic=None,
        short=False,
        color=False,
        authority=authority,
    )

    with redirect_stdout(StringIO()):
        assert handle(args) == 0

    assert args.json_payload["count"] == 0
    assert args.json_payload["commands"] == []


def test_help_catalog_hides_digestless_permission_and_denied_schemas() -> None:
    """Only executable or digest-backed permission schemas may be listed.

    Args:
        None.

    Returns:
        None: Assertions complete when hidden schemas are absent from JSON.
    """
    command_modules = [
        SimpleNamespace(SCHEMA=CommandSchema(name="help", help="Show help.")),
        SimpleNamespace(
            SCHEMA=CommandSchema(
                name="protected-with-digest",
                help="Run with a configured permission digest.",
            )
        ),
        SimpleNamespace(
            SCHEMA=CommandSchema(
                name="protected-without-digest",
                help="Do not list without a permission digest.",
            )
        ),
        SimpleNamespace(
            SCHEMA=CommandSchema(
                name="denied-command",
                help="Do not list denied commands.",
            )
        ),
    ]

    def permission(command_name: str, authority: str) -> AuthorityDecision:
        """Return the permission decision for one test schema.

        Args:
            command_name: Schema name being evaluated.
            authority: Caller authority supplied to the permission boundary.

        Returns:
            AuthorityDecision: Deterministic decision for the test schema.
        """
        assert authority == "worker"

        if command_name == "help":
            return AuthorityDecision(status="execute", message="")

        if command_name == "protected-with-digest":
            return AuthorityDecision(
                status="request_password",
                message="permission required",
                password_digest=PASSWORD_DIGEST,
            )

        if command_name == "protected-without-digest":
            return AuthorityDecision(
                status="request_password",
                message="permission unavailable",
                password_digest="",
            )

        return AuthorityDecision(status="deny", message="hidden")

    args = argparse.Namespace(
        topic=None,
        short=False,
        color=False,
        authority="worker",
    )
    terminal_output = StringIO()

    with (
        patch(
            "brain.presentation.commands.registry.COMMAND_MODULES",
            command_modules,
        ),
        patch("brain.presentation.views.help.rendering.AuthorityService") as authority_service,
    ):
        authority_service.return_value.evaluate_command_permission.side_effect = permission

        with redirect_stdout(terminal_output):
            assert handle(args) == 0

    commands = {
        command["name"]: command for command in args.json_payload["commands"]
    }

    assert set(commands) == {"help", "protected-with-digest"}
    assert commands["protected-with-digest"]["requires_password"] is True
    assert "protected-without-digest" not in terminal_output.getvalue()
    assert "denied-command" not in terminal_output.getvalue()
    assert any(
        "protected-with-digest" in line
        and "[password required]" in line
        for line in terminal_output.getvalue().splitlines()
    )


def test_terminal_help_hides_denied_commands_and_marks_requests() -> None:
    """Show executable commands, hide denies, and mark password requests.

    Args:
        None.

    Returns:
        None: Assertions complete when terminal and JSON visibility agree.
    """
    args = argparse.Namespace(
        topic=None,
        short=False,
        color=False,
        authority="worker",
    )
    terminal_output = StringIO()

    with patch(
        "brain.presentation.views.help.rendering.AuthorityService"
    ) as authority_service:
        authority_service.return_value.evaluate_command_permission.side_effect = (
            _terminal_visibility_permission
        )

        with redirect_stdout(terminal_output):
            assert handle(args) == 0

    terminal_lines = terminal_output.getvalue().splitlines()
    command_payloads = {
        command["name"]: command for command in args.json_payload["commands"]
    }

    assert any("serve-explorer" in line for line in terminal_lines)
    assert not any("list-profiles" in line for line in terminal_lines)
    assert any(
        "delete-task" in line and "[password required]" in line
        for line in terminal_lines
    )
    assert set(command_payloads) == {"help", "serve-explorer", "delete-task"}
    assert command_payloads["delete-task"]["requires_password"] is True


def test_help_catalog_evaluates_unknown_authority_for_help_schema() -> None:
    """Do not expose the help schema when its authority is unknown.

    Args:
        None.

    Returns:
        None: Assertions complete when the service denies the help schema.
    """
    command_modules = [
        SimpleNamespace(SCHEMA=CommandSchema(name="help", help="Show help.")),
    ]
    args = argparse.Namespace(
        topic=None,
        short=False,
        color=False,
        authority="unknown",
    )

    with (
        patch(
            "brain.presentation.commands.registry.COMMAND_MODULES",
            command_modules,
        ),
        patch("brain.presentation.views.help.rendering.AuthorityService") as service,
        redirect_stdout(StringIO()),
    ):
        service.return_value.evaluate_command_permission.return_value = AuthorityDecision(
            status="deny",
            message="hidden",
        )
        assert handle(args) == 0

    assert args.json_payload["count"] == 0
    assert args.json_payload["commands"] == []
    permission_calls = service.return_value.evaluate_command_permission.call_args_list

    assert len(permission_calls) == 2
    assert all(
        call.args == ("help", "unknown") and not call.kwargs
        for call in permission_calls
    )


@pytest.mark.parametrize(
    ("short", "topic"),
    [
        (True, None),
        (False, "delete-task"),
    ],
)
def test_password_marker_is_consistent_across_terminal_views(
    short: bool,
    topic: str | None,
) -> None:
    """Use the password marker in short and focused terminal help.

    Args:
        short: Whether to render the compact help layout.
        topic: Optional command topic for focused help rendering.

    Returns:
        None: Assertions complete when the marker and JSON flag are consistent.
    """
    args = argparse.Namespace(
        topic=topic,
        short=short,
        color=False,
        authority="worker",
    )
    terminal_output = StringIO()

    with patch(
        "brain.presentation.views.help.rendering.AuthorityService"
    ) as authority_service:
        authority_service.return_value.evaluate_command_permission.side_effect = (
            _terminal_visibility_permission
        )

        with redirect_stdout(terminal_output):
            assert handle(args) == 0

    assert "[password required]" in terminal_output.getvalue()
    assert any(
        command["name"] == "delete-task"
        and command["requires_password"] is True
        for command in args.json_payload["commands"]
    )
