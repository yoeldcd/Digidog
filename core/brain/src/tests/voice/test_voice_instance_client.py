"""Verify typed synchronous client routing for daemon voice instances.

Validates VoiceDaemonClient enqueueing, segmented instance waiting, cancellation
on timeout or Ctrl-C, and legacy speakId compatibility layers.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from io import BytesIO
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pytest

from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.contracts.instance_results import (
    InstanceEnqueueResult,
    InstanceTerminalResult,
    InstanceTerminalState,
)
from brain.infrastructure.voice.daemon import daemon_client
from brain.infrastructure.voice.daemon.daemon_client import VoiceDaemonClient


def test_terminal_result_is_immutable_and_preserves_exact_response_text() -> None:
    """The typed terminal DTO keeps response bytes and rejects mutation.

    Args:
        None.

    Returns:
        None.
    """

    response = "  exact response\nwith spacing  "
    terminal_result = InstanceTerminalResult(
        instance_id="speak-response",
        state=InstanceTerminalState.RESPONSED,
        response=response,
    )

    assert terminal_result.response == response
    assert terminal_result.to_payload() == {
        "instanceId": "speak-response",
        "state": "RESPONSED",
        "response": response,
    }

    with pytest.raises(FrozenInstanceError):
        terminal_result.response = "changed"  # type: ignore[misc]


def test_speak_and_wait_routes_only_the_returned_instance_id() -> None:
    """Enqueue, wait, and terminal parsing stay bound to one daemon identity.

    Args:
        None.

    Returns:
        None.
    """

    client = VoiceDaemonClient()
    request = AvatarSpeakRequest(
        text="One logical emission",
        codex_thread_id="session-metadata",
    )
    request_mock = Mock(
        side_effect=[
            {"ok": True, "queued": True, "speakId": "speak-one"},
            {"ok": True, "instanceId": "speak-one", "state": "SPEAKED"},
        ]
    )

    with (
        patch.object(client, "_ensure_daemon"),
        patch.object(client, "_request_json", request_mock),
    ):
        terminal_result = client.speak_and_wait(request, timeout_seconds=2.5)

    assert terminal_result == InstanceTerminalResult(
        instance_id="speak-one",
        state=InstanceTerminalState.SPEAKED,
    )
    wait_call = request_mock.call_args_list[1]
    assert wait_call.kwargs["path"] == "/instance/wait"
    assert wait_call.kwargs["payload"] == {
        "instanceId": "speak-one",
        "timeoutSeconds": 2.5,
    }
    assert "codexThreadId" not in wait_call.kwargs["payload"]


def test_wait_instance_segments_a_long_budget_into_bounded_exact_id_requests() -> None:
    """A 75-second budget is sent as 30, 30, and 15 second exact-ID waits.

    Args:
        None.

    Returns:
        None.
    """

    client = VoiceDaemonClient()
    request_mock = Mock(
        side_effect=[
            {"ok": False, "instanceId": "speak-long", "state": "TIMEOUT"},
            {"ok": False, "instanceId": "speak-long", "state": "TIMEOUT"},
            {"ok": True, "instanceId": "speak-long", "state": "SPEAKED"},
        ]
    )
    monotonic_mock = Mock(side_effect=[100.0, 130.0, 160.0])

    with (
        patch.object(daemon_client.time, "monotonic", monotonic_mock),
        patch.object(client, "_request_json", request_mock),
    ):
        terminal_result = client.wait_instance("speak-long", timeout_seconds=75.0)

    assert terminal_result == InstanceTerminalResult(
        instance_id="speak-long",
        state=InstanceTerminalState.SPEAKED,
    )
    assert [
        call.kwargs["payload"]["timeoutSeconds"]
        for call in request_mock.call_args_list
    ] == [30.0, 30.0, 15.0]
    assert [
        call.kwargs["payload"]["instanceId"]
        for call in request_mock.call_args_list
    ] == ["speak-long", "speak-long", "speak-long"]


@pytest.mark.parametrize(
    "segment_outcome",
    (
        {"ok": False, "instanceId": "speak-retry", "state": "TIMEOUT"},
        HTTPError(
            url="http://127.0.0.1/instance/wait",
            code=408,
            msg="wait timeout",
            hdrs=None,
            fp=BytesIO(),
        ),
        TimeoutError(),
    ),
    ids=("daemon-timeout", "http-408", "transport-timeout"),
)
def test_wait_instance_continues_after_a_segment_timeout(
    segment_outcome: object,
) -> None:
    """A transient segment timeout does not discard the caller's remaining budget.

    Args:
        segment_outcome: Daemon, HTTP, or transport timeout from the first wait.

    Returns:
        None.
    """

    client = VoiceDaemonClient()
    request_mock = Mock(
        side_effect=[
            segment_outcome,
            {"ok": True, "instanceId": "speak-retry", "state": "SPEAKED"},
        ]
    )
    monotonic_mock = Mock(side_effect=[100.0, 130.0])

    with (
        patch.object(daemon_client.time, "monotonic", monotonic_mock),
        patch.object(client, "_request_json", request_mock),
    ):
        terminal_result = client.wait_instance("speak-retry", timeout_seconds=75.0)

    assert terminal_result == InstanceTerminalResult(
        instance_id="speak-retry",
        state=InstanceTerminalState.SPEAKED,
    )
    assert [
        call.kwargs["payload"]["timeoutSeconds"]
        for call in request_mock.call_args_list
    ] == [30.0, 30.0]
    assert all(
        call.kwargs["payload"]["instanceId"] == "speak-retry"
        for call in request_mock.call_args_list
    )


def test_wait_instance_returns_none_only_after_the_total_budget_is_exhausted() -> None:
    """Repeated segment timeouts end only when the exact total deadline expires.

    Args:
        None.

    Returns:
        None.
    """

    client = VoiceDaemonClient()
    request_mock = Mock(
        side_effect=[
            {"ok": False, "instanceId": "speak-exhausted", "state": "TIMEOUT"},
            {"ok": False, "instanceId": "speak-exhausted", "state": "TIMEOUT"},
            {"ok": False, "instanceId": "speak-exhausted", "state": "TIMEOUT"},
        ]
    )
    monotonic_mock = Mock(side_effect=[100.0, 130.0, 160.0, 175.0])

    with (
        patch.object(daemon_client.time, "monotonic", monotonic_mock),
        patch.object(client, "_request_json", request_mock),
    ):
        terminal_result = client.wait_instance(
            "speak-exhausted", timeout_seconds=75.0
        )

    assert terminal_result is None
    assert [
        call.kwargs["payload"]["timeoutSeconds"]
        for call in request_mock.call_args_list
    ] == [30.0, 30.0, 15.0]
    assert all(
        call.kwargs["payload"]["instanceId"] == "speak-exhausted"
        for call in request_mock.call_args_list
    )


def test_wait_instance_zero_budget_performs_one_exact_id_probe() -> None:
    """A zero budget preserves the immediate exact-ID terminal probe.

    Args:
        None.

    Returns:
        None.
    """

    client = VoiceDaemonClient()
    request_mock = Mock(
        return_value={
            "ok": False,
            "instanceId": "speak-zero",
            "state": "TIMEOUT",
        }
    )
    monotonic_mock = Mock(return_value=100.0)

    with (
        patch.object(daemon_client.time, "monotonic", monotonic_mock),
        patch.object(client, "_request_json", request_mock),
    ):
        terminal_result = client.wait_instance("speak-zero", timeout_seconds=0.0)

    assert terminal_result is None
    assert request_mock.call_count == 1
    assert request_mock.call_args.kwargs["payload"] == {
        "instanceId": "speak-zero",
        "timeoutSeconds": 0.0,
    }


def test_wait_instance_short_budget_uses_one_segment_without_sleeping() -> None:
    """A short caller budget remains exact and uses only one daemon request.

    Args:
        None.

    Returns:
        None.
    """

    client = VoiceDaemonClient()
    request_mock = Mock(
        return_value={
            "ok": True,
            "instanceId": "speak-short",
            "state": "SPEAKED",
        }
    )
    monotonic_mock = Mock(return_value=100.0)

    with (
        patch.object(daemon_client.time, "monotonic", monotonic_mock),
        patch.object(client, "_request_json", request_mock),
    ):
        terminal_result = client.wait_instance("speak-short", timeout_seconds=2.5)

    assert terminal_result == InstanceTerminalResult(
        instance_id="speak-short",
        state=InstanceTerminalState.SPEAKED,
    )
    assert request_mock.call_count == 1
    assert request_mock.call_args.kwargs["payload"] == {
        "instanceId": "speak-short",
        "timeoutSeconds": 2.5,
    }


def test_timeout_cancels_the_same_id_and_returns_explicit_canceled_state() -> None:
    """A bounded wait must cancel its own speak ID, never a global active item.

    Args:
        None.

    Returns:
        None.
    """

    client = VoiceDaemonClient()
    request_mock = Mock(
        side_effect=[
            {"ok": True, "queued": True, "speakId": "speak-timeout"},
            {"ok": False, "instanceId": "speak-timeout", "state": "TIMEOUT"},
            {"ok": True, "instanceId": "speak-timeout", "state": "CANCELED"},
        ]
    )

    with (
        patch.object(client, "_ensure_daemon"),
        patch.object(client, "_request_json", request_mock),
    ):
        terminal_result = client.speak_and_wait(
            AvatarSpeakRequest(text="Bounded"), timeout_seconds=0
        )

    assert terminal_result == InstanceTerminalResult(
        instance_id="speak-timeout",
        state=InstanceTerminalState.CANCELED,
    )
    cancel_call = request_mock.call_args_list[2]
    assert cancel_call.kwargs["path"] == "/instance/cancel"
    assert cancel_call.kwargs["payload"] == {"instanceId": "speak-timeout"}


def test_keyboard_interrupt_cancels_the_exact_accepted_id() -> None:
    """Ctrl-C propagates after requesting cancellation for the accepted ID.

    Args:
        None.

    Returns:
        None.
    """

    client = VoiceDaemonClient()
    cancel_mock = Mock(
        return_value=InstanceTerminalResult(
            instance_id="speak-interrupt",
            state=InstanceTerminalState.CANCELED,
        )
    )

    with (
        patch.object(client, "_ensure_daemon"),
        patch.object(
            client,
            "_request_json",
            return_value={"ok": True, "queued": True, "speakId": "speak-interrupt"},
        ),
        patch.object(client, "wait", side_effect=KeyboardInterrupt),
        patch.object(client, "cancel", cancel_mock),
        pytest.raises(KeyboardInterrupt),
    ):
        client.speak_and_wait(AvatarSpeakRequest(text="Interruptible"))

    cancel_mock.assert_called_once_with("speak-interrupt")


def test_canonical_wait_falls_back_to_legacy_local_daemon_request_keys() -> None:
    """The current client contract remains usable with the local legacy daemon.

    Args:
        None.

    Returns:
        None.
    """

    client = VoiceDaemonClient()
    bad_request_error = HTTPError(
        url="http://127.0.0.1/instance/wait",
        code=400,
        msg="speakId required",
        hdrs=None,
        fp=BytesIO(),
    )
    request_mock = Mock(
        side_effect=[
            bad_request_error,
            {"ok": True, "speakId": "speak-legacy", "state": "SPEAKED"},
        ]
    )

    with patch.object(client, "_request_json", request_mock):
        terminal_result = client.wait_instance("speak-legacy", timeout_seconds=1.0)

    assert terminal_result == InstanceTerminalResult(
        instance_id="speak-legacy",
        state=InstanceTerminalState.SPEAKED,
    )
    assert request_mock.call_args_list[0].kwargs["payload"] == {
        "instanceId": "speak-legacy",
        "timeoutSeconds": 1.0,
    }
    assert request_mock.call_args_list[1].kwargs["payload"] == {
        "speakId": "speak-legacy",
        "timeout": 1.0,
    }


def test_enqueue_returns_an_immutable_typed_identity() -> None:
    """The enqueue acknowledgement is converted into a typed identity DTO.

    Args:
        None.

    Returns:
        None.
    """

    client = VoiceDaemonClient()

    request_mock = Mock(
        return_value={"ok": True, "queued": True, "speakId": "speak-typed"}
    )

    with (
        patch.object(client, "_ensure_daemon"),
        patch.object(client, "_request_json", request_mock),
    ):
        enqueue_result = client.enqueue(AvatarSpeakRequest(text="Typed"))

    assert enqueue_result == InstanceEnqueueResult(
        instance_id="speak-typed",
    )
    assert enqueue_result.speak_id == "speak-typed"



def test_wait_instance_held_segments_do_not_consume_total_timeout_budget() -> None:
    """REQ-04: Multiple HELD segments preserve the caller's remaining budget.

    Args:
        None.

    Returns:
        None: Assertions validate repeated bounded hold probes and terminal parsing.
    """

    client = VoiceDaemonClient()
    request_mock = Mock(
        side_effect=[
            {"ok": False, "instanceId": "speak-held", "state": "HELD"},
            {"ok": False, "instanceId": "speak-held", "state": "HELD"},
            {
                "ok": True,
                "instanceId": "speak-held",
                "state": "RESPONSED",
                "response": "held response",
            },
        ]
    )
    monotonic_mock = Mock(side_effect=[100.0, 130.0, 10_000.0])

    with (
        patch.object(daemon_client.time, "monotonic", monotonic_mock),
        patch.object(client, "_request_json", request_mock),
    ):
        terminal_result = client.wait_instance("speak-held", timeout_seconds=75.0)

    assert terminal_result == InstanceTerminalResult(
        instance_id="speak-held",
        state=InstanceTerminalState.RESPONSED,
        response="held response",
    )
    assert [
        call.kwargs["payload"]["timeoutSeconds"]
        for call in request_mock.call_args_list
    ] == [30.0, 30.0, 30.0]
    assert [
        call.kwargs["payload"]["instanceId"]
        for call in request_mock.call_args_list
    ] == ["speak-held", "speak-held", "speak-held"]
