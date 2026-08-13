# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Contract and gateway tests for immutable daemon instance replies.

Tests daemon reply gateway HTTP transport, hold acquisition, reply submission,
and cancellation handling bound to specific speak instance identifiers.
"""

from __future__ import annotations

import json
import os
from dataclasses import FrozenInstanceError
from unittest.mock import Mock, patch

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from brain.presentation.avatar.communication.reply.daemon_gateway import (
    DaemonReplyGateway,
)
from brain.presentation.avatar.qt.reply_window.controller import AvatarReplyController
from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    DeliveryMode,
    ReplyRequestDTO,
    ReplyResultDTO,
    ReplyTerminalState,
)
from brain.presentation.avatar.communication.reply.service import AvatarReplyService


THREAD_ID = "019f5dad-af67-7533-b394-8fb55258adb2"


class JsonResponse:
    """Minimal context manager matching the local HTTP response boundary."""

    def __init__(self, payload: dict[str, object]) -> None:
        """Initialize a response with one JSON payload.

        Args:
            payload: JSON-compatible response data.

        Returns:
            None: The encoded body is retained for reads.
        """

        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "JsonResponse":
        """Return this response for a bounded gateway read.

        Args:
            No external arguments are accepted; the context manager owns the response.

        Returns:
            JsonResponse: This in-memory response.
        """

        return self

    def __exit__(self, *args: object) -> None:
        """Close the in-memory response without side effects.

        Args:
            *args: Context-manager exception details, if any.

        Returns:
            None: The in-memory response has no resources to release.
        """

        return None

    def read(self) -> bytes:
        """Return the encoded response body.

        Args:
            No external arguments are accepted; the response owns its body.

        Returns:
            bytes: UTF-8 encoded JSON response data.
        """

        return self._body


def target(
    *, instance_id: str = "speak-captured", session_id: str = ""
) -> CodexThreadTargetDTO:
    """Build one valid immutable target for gateway tests.

    Args:
        instance_id: Exact daemon speak instance to capture.
        session_id: Optional metadata that must not affect routing.

    Returns:
        CodexThreadTargetDTO: Immutable gateway target.
    """

    return CodexThreadTargetDTO(
        instance_id=instance_id,
        thread_id=THREAD_ID,
        source_message_id="daemon-process-id",
        session_id=session_id,
    )


def request_for(target_dto: CodexThreadTargetDTO) -> ReplyRequestDTO:
    """Build one exact response request for a target.

    Args:
        target_dto: Immutable daemon target receiving the response.

    Returns:
        ReplyRequestDTO: Validated response request.
    """

    return ReplyRequestDTO(
        target=target_dto,
        text="  respuesta exacta\n",
        mode=DeliveryMode.QUEUE,
    )


def request_payload(call: Mock) -> dict[str, object]:
    """Decode the JSON body from one captured urllib request.

    Args:
        call: Mock containing the captured request object.

    Returns:
        dict[str, object]: Decoded request JSON mapping.
    """

    request = call.call_args.args[0]

    return json.loads(request.data.decode("utf-8"))


def test_target_captures_immutable_instance_and_session_is_metadata_only() -> None:
    """The speak identity is frozen while session metadata remains non-routing.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the immutable target contract.
    """

    captured = target(session_id="session-a")

    assert captured.speak_id == "speak-captured"
    assert captured.session_id == "session-a"

    with pytest.raises(FrozenInstanceError):
        captured.instance_id = "speak-new"  # type: ignore[misc]


def test_target_requires_instance_without_requiring_codex_metadata() -> None:
    """Require only the message instance while allowing absent Codex metadata.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the instance-only routing contract.
    """

    captured = CodexThreadTargetDTO(instance_id="speak-only")

    assert captured.instance_id == "speak-only"
    assert captured.thread_id == ""
    assert captured.session_id == ""
    assert captured.host_id == ""

    metadata_target = CodexThreadTargetDTO(
        instance_id="speak-with-metadata",
        thread_id="codex-thread-metadata",
        host_id="codex-host-metadata",
        session_id="codex-session-metadata",
    )

    assert metadata_target.instance_id == "speak-with-metadata"
    assert metadata_target.thread_id == "codex-thread-metadata"

    with pytest.raises(ValueError, match="instance id is required"):
        CodexThreadTargetDTO(instance_id="")

    with pytest.raises(ValueError, match="instance id is required"):
        CodexThreadTargetDTO(instance_id="", source_message_id="source-only")


def test_gateway_submits_response_to_exact_instance_without_session_or_thread_routing() -> None:
    """Response routing uses only the captured speak ID and response text.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the exact response route payload.
    """

    gateway = DaemonReplyGateway(daemon_url="http://daemon.test")
    target_dto = target(session_id="session-present")
    response = JsonResponse(
        {
            "ok": True,
            "speakId": "speak-captured",
            "state": ReplyTerminalState.RESPONSED.value,
            "response": "  respuesta exacta\n",
        }
    )

    with patch(
        "brain.presentation.avatar.communication.reply.daemon_gateway.urlopen",
        return_value=response,
    ) as send:
        result = gateway.send(request_for(target_dto))

    assert send.call_args.args[0].full_url == "http://daemon.test/instance/respond"
    assert request_payload(send) == {
        "instanceId": "speak-captured",
        "response": "  respuesta exacta\n",
    }
    assert result.accepted is True
    assert result.instance_id == "speak-captured"
    assert result.state == ReplyTerminalState.RESPONSED.value
    assert result.response == "  respuesta exacta\n"
    assert result.mode is DeliveryMode.QUEUE


def test_gateway_cancel_targets_exact_instance_and_omits_session_metadata() -> None:
    """Cancellation uses the same immutable ID and never sends session data.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the exact cancellation route payload.
    """

    gateway = DaemonReplyGateway(daemon_url="http://daemon.test")
    target_dto = target(session_id="session-present")
    response = JsonResponse(
        {
            "ok": True,
            "speakId": "speak-captured",
            "state": ReplyTerminalState.CANCELED.value,
        }
    )

    with patch(
        "brain.presentation.avatar.communication.reply.daemon_gateway.urlopen",
        return_value=response,
    ) as cancel:
        result = gateway.cancel(target_dto)

    assert cancel.call_args.args[0].full_url == "http://daemon.test/instance/cancel"
    assert request_payload(cancel) == {"instanceId": "speak-captured"}
    assert result.accepted is True
    assert result.instance_id == "speak-captured"
    assert result.state == ReplyTerminalState.CANCELED.value


def test_gateway_opens_exact_composer_hold_without_metadata_routing() -> None:
    """Open the composer hold for one captured instance only.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the exact hold route and identity payload.
    """

    gateway = DaemonReplyGateway(daemon_url="http://daemon.test")
    target_dto = target(session_id="session-present")
    response = JsonResponse(
        {
            "ok": True,
            "speakId": "speak-captured",
            "held": True,
        }
    )

    with patch(
        "brain.presentation.avatar.communication.reply.daemon_gateway.urlopen",
        return_value=response,
    ) as open_request:
        result = gateway.open(target_dto)

    assert open_request.call_args.args[0].full_url == (
        "http://daemon.test/instance/composer-open"
    )
    assert request_payload(open_request) == {"instanceId": "speak-captured"}
    assert result.accepted is True
    assert result.instance_id == "speak-captured"
    assert result.state == "HELD"


def test_gateway_failure_retains_exact_instance_for_ui_matching() -> None:
    """Transport failure is rejected without losing the target identity.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate failure identity preservation.
    """

    gateway = DaemonReplyGateway(daemon_url="http://daemon.test")
    target_dto = target()

    with patch(
        "brain.presentation.avatar.communication.reply.daemon_gateway.urlopen",
        side_effect=OSError("daemon unavailable"),
    ):
        result = gateway.send(request_for(target_dto))

    assert result.accepted is False
    assert result.instance_id == target_dto.instance_id
    assert "daemon unavailable" in result.error


def test_gateway_rejects_stale_send_after_speaked_without_retargeting() -> None:
    """Reject a late response for a spoken instance without changing its ID.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate stale terminal rejection and identity binding.
    """

    gateway = DaemonReplyGateway(daemon_url="http://daemon.test")
    target_dto = target(instance_id="speak-finished")
    response = JsonResponse(
        {
            "ok": False,
            "speakId": "speak-finished",
            "state": ReplyTerminalState.SPEAKED.value,
            "error": "Instance already spoken.",
        }
    )

    with patch(
        "brain.presentation.avatar.communication.reply.daemon_gateway.urlopen",
        return_value=response,
    ):
        result = gateway.send(request_for(target_dto))

    assert result.accepted is False
    assert result.instance_id == "speak-finished"
    assert result.state == ReplyTerminalState.SPEAKED.value
    assert "spoken" in result.error


def test_service_cancel_delegates_the_immutable_target() -> None:
    """The application boundary delegates cancellation without rewriting IDs.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate service delegation.
    """

    gateway = Mock()
    service = AvatarReplyService(gateway)
    target_dto = target()

    service.cancel(target_dto)

    gateway.cancel.assert_called_once_with(target=target_dto)


def test_service_open_delegates_the_immutable_target() -> None:
    """The service forwards the composer hold without rewriting its target.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the open boundary delegation.
    """

    gateway = Mock()
    service = AvatarReplyService(gateway)
    target_dto = target(session_id="session-present")

    service.open(target_dto)

    gateway.open.assert_called_once_with(target=target_dto)


def test_controller_open_emits_exact_hold_result_without_delivery_signal() -> None:
    """Emit hold acknowledgement on the dedicated controller signal only.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate asynchronous exact-ID open routing.
    """

    QApplication.instance() or QApplication([])
    service = Mock()
    target_dto = target()
    hold_result = ReplyResultDTO(
        accepted=True,
        thread_id=target_dto.thread_id,
        mode=DeliveryMode.STEER,
        instance_id=target_dto.instance_id,
        state="HELD",
    )
    service.open.return_value = hold_result
    controller = AvatarReplyController(service)  # type: ignore[arg-type]
    opened: list[ReplyResultDTO] = []
    delivered: list[ReplyResultDTO] = []

    def record_open(result: ReplyResultDTO) -> None:
        """Record the dedicated open signal.

        Args:
            result: Hold result emitted by the controller.

        Returns:
            None: The result is appended for assertion.
        """

        opened.append(result)

    controller.composerOpened.connect(record_open)
    controller.deliveryFinished.connect(delivered.append)

    def immediate_thread(target: object, daemon: bool, name: str) -> Mock:
        """Run the controller worker inline for deterministic assertions.

        Args:
            target: Worker callable constructed by the controller.
            daemon: Thread daemon flag retained for signature compatibility.
            name: Diagnostic thread name retained for signature compatibility.

        Returns:
            Mock: No-op thread handle after the worker has completed.
        """

        del daemon, name
        assert callable(target)
        target()

        return Mock()

    with patch(
        "brain.presentation.avatar.qt.reply_window.controller.threading.Thread",
        immediate_thread,
    ):
        controller.open(target_dto)

    assert opened == [hold_result]
    assert delivered == []
    service.open.assert_called_once_with(target=target_dto)
