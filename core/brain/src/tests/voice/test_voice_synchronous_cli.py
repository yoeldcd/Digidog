"""Verify synchronous CLI emission ordering and terminal propagation.

Tests command_speak action handling, CLI argument parsing, timeout overrides,
stdin envelope processing, and compact public JSON output formatting.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from brain.infrastructure.voice.contracts.instance_results import (
    InstanceTerminalResult,
    InstanceTerminalState,
)
from brain.presentation.commands.general.command_speak import SCHEMA
from brain.presentation.commands.registry import COMMAND_MODULES
from brain.presentation.parser.services.argument_parser_service import (
    build_argument_parser,
)
from brain.presentation.actions.general.command_speak import handle


def _args(**overrides: object) -> Namespace:
    """Build the minimal speak action namespace used by focused tests.

    Args:
        overrides: Argument values that replace the test defaults.

    Returns:
        Namespace: Minimal command argument namespace.
    """

    values: dict[str, object] = {
        "text": "Texto base",
        "body": None,
        "file": "",
        "lang": "es",
        "emotion": "focused",
        "codex_thread_id": "session-metadata",
        "stdin_json": False,
        "color": False,
        "json": True,
    }
    values.update(overrides)

    return Namespace(**values)


@pytest.mark.parametrize(
    ("state", "response", "expected_state", "expected_output"),
    [
        (InstanceTerminalState.SPEAKED, "", "SPEAKED", None),
        (
            InstanceTerminalState.RESPONSED,
            "  daemon response\nwith spacing  ",
            "RESPONDED",
            "  daemon response\nwith spacing  ",
        ),
        (InstanceTerminalState.CANCELED, "", "SPEAKED", None),
    ],
)
def test_cli_returns_exact_compact_response_for_terminal_state(
    state: InstanceTerminalState,
    response: str,
    expected_state: str,
    expected_output: str | None,
) -> None:
    """Expose only the compact JSON contract for each terminal state.

    Args:
        state: Internal terminal state returned by the mocked service.
        response: Exact response associated with the terminal state.
        expected_state: Public state expected in the JSON payload.
        expected_output: Public output expected in the JSON payload.

    Returns:
        None.
    """

    service_result = InstanceTerminalResult(
        "speak-result",
        state,
        response,
    )
    args = _args()

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService"
    ) as service_type:
        service_type.return_value.speak.return_value = service_result
        assert handle(args) == 0

    expected_payload: dict[str, object] = {
        "ok": True,
        "command": "speak",
        "state": expected_state,
    }

    if expected_output is not None:
        expected_payload["output"] = expected_output

    else:
        expected_payload["instruction"] = "continue"

    assert args.json_payload == expected_payload


@pytest.mark.parametrize(
    ("state", "response", "expected_state", "expected_output"),
    [
        (InstanceTerminalState.SPEAKED, "", "SPEAKED", None),
        (InstanceTerminalState.RESPONSED, "repeat response", "RESPONDED", "repeat response"),
        (InstanceTerminalState.CANCELED, "", "SPEAKED", None),
    ],
)
def test_cli_returns_exact_compact_response_for_repeat_last(
    state: InstanceTerminalState,
    response: str,
    expected_state: str,
    expected_output: str | None,
) -> None:
    """Expose repeat-last through the same compact synchronous JSON contract.

    Args:
        state: Internal terminal state returned by the mocked service.
        response: Exact response associated with the terminal state.
        expected_state: Public state expected in the JSON payload.
        expected_output: Optional public output expected in the JSON payload.

    Returns:
        None.
    """

    args = _args(text="")

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService"
    ) as service_type:
        service_type.return_value.speak.return_value = InstanceTerminalResult(
            "speak-repeat",
            state,
            response,
        )
        assert handle(args) == 0

    service_type.return_value.speak.assert_called_once_with(
        text="",
        lang="es",
        emotion="focused",
        codex_thread_id="session-metadata",
    )
    expected_payload: dict[str, object] = {
        "ok": True,
        "command": "speak",
        "state": expected_state,
    }

    if expected_output is not None:
        expected_payload["output"] = expected_output

    else:
        expected_payload["instruction"] = "continue"

    assert args.json_payload == expected_payload


def test_cli_applies_content_timeout_floor_to_empty_repeat() -> None:
    """Apply the base timeout floor when repeating without new content.

    Args:
        None.

    Returns:
        None.
    """

    args = _args(text="", timeout=0.0)

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService"
    ) as service_type:
        service_type.return_value.speak.return_value = InstanceTerminalResult(
            "speak-repeat-floor",
            InstanceTerminalState.SPEAKED,
        )

        assert handle(args) == 0

    service_type.assert_called_once_with(synchronous=True, timeout_seconds=120.0)


def test_cli_applies_content_timeout_floor_to_text() -> None:
    """Scale the timeout floor from the exact text emission length.

    Args:
        None.

    Returns:
        None.
    """

    text = "Texto breve"
    args = _args(text=text, timeout=0.0)

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService"
    ) as service_type:
        service_type.return_value.speak.return_value = InstanceTerminalResult(
            "speak-text-floor",
            InstanceTerminalState.SPEAKED,
        )

        assert handle(args) == 0

    expected_timeout = 120.0 + 2.0 * len(text)
    service_type.assert_called_once_with(
        synchronous=True,
        timeout_seconds=expected_timeout,
    )


def test_cli_counts_task_heading_in_timeout_floor() -> None:
    """Include the prefixed task heading in the timeout character count.

    Args:
        None.

    Returns:
        None.
    """

    task_id = "T-42"
    text = "Resultado listo"
    line_breaks = chr(10) * 2
    prefixed_text = f"Reporte de la tarea {task_id}{line_breaks}{text}"
    args = _args(text=text, task_id=task_id, timeout=0.0)

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService"
    ) as service_type:
        service_type.return_value.speak.return_value = InstanceTerminalResult(
            "speak-task-floor",
            InstanceTerminalState.SPEAKED,
        )

        assert handle(args) == 0

    service_type.return_value.speak.assert_called_once_with(
        text=prefixed_text,
        lang="es",
        emotion="focused",
        codex_thread_id="session-metadata",
    )
    expected_timeout = 120.0 + 2.0 * len(prefixed_text)
    service_type.assert_called_once_with(
        synchronous=True,
        timeout_seconds=expected_timeout,
    )


def test_cli_counts_full_embedded_markdown_in_timeout_floor(tmp_path: Path) -> None:
    """Include the complete decoded Markdown content in the timeout count.

    Args:
        tmp_path: Pytest temporary directory for the embedded Markdown fixture.

    Returns:
        None.
    """

    line_breaks = chr(10) * 2
    markdown = f"# Plan{line_breaks}Contenido completo."
    file_path = tmp_path / "plan.md"
    file_path.write_bytes(markdown.encode("utf-8"))
    args = _args(text="", file=str(file_path), timeout=0.0)

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService"
    ) as service_type:
        service_type.return_value.present.return_value = InstanceTerminalResult(
            "speak-file-floor",
            InstanceTerminalState.SPEAKED,
        )

        assert handle(args) == 0

    expected_timeout = 120.0 + 2.0 * len(markdown)
    service_type.assert_called_once_with(
        synchronous=True,
        timeout_seconds=expected_timeout,
    )


def test_cli_counts_text_and_embedded_markdown_for_compound_timeout(
    tmp_path: Path,
) -> None:
    """Sum text and Markdown character counts for compound input.

    Args:
        tmp_path: Pytest temporary directory for the embedded Markdown fixture.

    Returns:
        None.
    """

    text = "Texto"
    line_breaks = chr(10) * 2
    markdown = f"## Plan{line_breaks}Contenido"
    file_path = tmp_path / "compound.md"
    file_path.write_bytes(markdown.encode("utf-8"))
    args = _args(text=text, file=str(file_path), timeout=0.0)

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService"
    ) as service_type:
        service_type.return_value.speak.return_value = InstanceTerminalResult(
            "speak-compound-text",
            InstanceTerminalState.SPEAKED,
        )
        service_type.return_value.present.return_value = InstanceTerminalResult(
            "speak-compound-file",
            InstanceTerminalState.SPEAKED,
        )

        assert handle(args) == 0

    expected_timeout = 120.0 + 2.0 * (len(text) + len(markdown))
    service_type.assert_called_once_with(
        synchronous=True,
        timeout_seconds=expected_timeout,
    )


def test_cli_propagates_explicit_larger_timeout_override() -> None:
    """Prefer a larger explicit timeout over the content-sized minimum.

    Args:
        None.

    Returns:
        None.
    """

    args = _args(timeout=999.5)

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService"
    ) as service_type:
        service_type.return_value.speak.return_value = InstanceTerminalResult(
            "speak-explicit-timeout",
            InstanceTerminalState.SPEAKED,
        )

        assert handle(args) == 0

    service_type.assert_called_once_with(synchronous=True, timeout_seconds=999.5)


def test_parser_exposes_timeout_with_safe_default_and_help(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Expose a finite non-negative timeout option through the live parser.

    Args:
        monkeypatch: Pytest environment fixture used to configure the workspace root.
        capsys: Pytest output capture fixture used to inspect command help.

    Returns:
        None.
    """

    timeout_argument = next(
        argument for argument in SCHEMA.arguments if "--timeout" in argument.flags
    )
    assert timeout_argument.type == "float"
    assert timeout_argument.default == 300.0
    assert timeout_argument.default > 30.0
    assert "finite" in timeout_argument.help
    assert "non-negative" in timeout_argument.help
    assert "120" in timeout_argument.help
    assert "2" in timeout_argument.help
    assert "emitted characters" in timeout_argument.help
    assert "larger explicit values win" in timeout_argument.help

    workspace_root = Path(__file__).resolve().parents[4]
    monkeypatch.setenv("WORKSPACE_ROOT", str(workspace_root))
    parser = build_argument_parser(COMMAND_MODULES)
    parsed = parser.parse_args(["speak", "--text", "Mensaje breve"])
    assert parsed.timeout == 300.0
    zero_timeout = parser.parse_args(["speak", "--timeout", "0"])
    assert zero_timeout.timeout == 0.0

    with pytest.raises(SystemExit):
        parser.parse_args(["speak", "--help"])

    assert "--timeout" in capsys.readouterr().out


def test_parser_rejects_non_numeric_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject a timeout that cannot be converted to a floating-point value.

    Args:
        monkeypatch: Pytest environment fixture used to configure the workspace root.

    Returns:
        None.
    """

    workspace_root = Path(__file__).resolve().parents[4]
    monkeypatch.setenv("WORKSPACE_ROOT", str(workspace_root))
    parser = build_argument_parser(COMMAND_MODULES)

    with pytest.raises(SystemExit):
        parser.parse_args(["speak", "--timeout", "not-a-number"])


@pytest.mark.parametrize("timeout", [-1.0, float("nan"), float("inf")])
def test_action_rejects_invalid_timeout_before_speech(timeout: float) -> None:
    """Reject negative or non-finite values before any speech method is called.

    Args:
        timeout: Invalid timeout candidate passed through the action boundary.

    Returns:
        None.
    """

    args = _args(timeout=timeout)

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService.speak"
    ) as speak:
        assert handle(args) == 1

    speak.assert_not_called()


def test_cli_maps_mixed_text_and_file_emissions_in_deterministic_order() -> None:
    """Text and file emissions wait and report in their submission order.

    Args:
        None.

    Returns:
        None.
    """

    text_result = InstanceTerminalResult("speak-text", InstanceTerminalState.SPEAKED)
    file_result = InstanceTerminalResult(
        "speak-file",
        InstanceTerminalState.RESPONSED,
        "exact file response",
    )
    args = _args(file="plan.md")

    with (
        patch(
            "brain.presentation.actions.general.command_speak._read_embedded_markdown",
            return_value=("plan.md", "# Plan"),
        ),
        patch(
            "brain.presentation.actions.general.command_speak.VoiceService"
        ) as service_type,
    ):
        service_type.return_value.speak.return_value = text_result
        service_type.return_value.present.return_value = file_result
        assert handle(args) == 0

    service = service_type.return_value
    assert service.speak.call_args.kwargs["codex_thread_id"] == "session-metadata"
    assert service.present.call_args.args[0].codex_thread_id == "session-metadata"
    assert args.json_payload == {
        "ok": True,
        "command": "speak",
        "state": "RESPONDED",
        "output": "exact file response",
    }


def test_cli_maps_canceled_to_speaked_without_output() -> None:
    """Map a canceled emission to the public SPEAKED no-reply state.

    Args:
        None.

    Returns:
        None.
    """

    args = _args()
    canceled = InstanceTerminalResult("speak-canceled", InstanceTerminalState.CANCELED)

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService"
    ) as service_type:
        service_type.return_value.speak.return_value = canceled
        assert handle(args) == 0

    assert args.json_payload == {
        "ok": True,
        "command": "speak",
        "state": "SPEAKED",
        "instruction": "continue",
    }


def test_cli_continues_when_no_terminal_result_is_reachable() -> None:
    """Emit a continuation instruction when the voice service returns no result.

    Args:
        None.

    Returns:
        None.
    """

    args = _args()

    with patch(
        "brain.presentation.actions.general.command_speak.VoiceService"
    ) as service_type:
        service_type.return_value.speak.return_value = None
        assert handle(args) == 0

    assert args.json_payload == {
        "ok": True,
        "command": "speak",
        "state": "SPEAKED",
        "instruction": "continue",
    }
