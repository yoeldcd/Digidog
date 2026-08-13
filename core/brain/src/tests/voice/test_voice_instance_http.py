"""Verify bounded HTTP lifecycle routes for daemon-owned speak instances.

Tests REST endpoint handlers for /instance/wait, /instance/hold, /instance/respond,
and /instance/cancel routes, ensuring proper HTTP status codes and JSON payloads.
"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import Mock

from brain.infrastructure.voice.daemon.daemon import VoiceDaemonHandler, VoiceMemory
from brain.infrastructure.voice.messaging.instance_lifecycle import (
    InstanceTerminalState,
)


def _post(handler: VoiceDaemonHandler, path: str, payload: dict[str, object]) -> Mock:
    """Invoke one handler route with an in-memory JSON request.

    Args:
        handler: Uninitialized daemon handler configured for the test memory.
        path: HTTP route to dispatch.
        payload: JSON-compatible request body.

    Returns:
        Mock: Captured JSON response sender.
    """

    body = json.dumps(payload).encode("utf-8")
    handler.path = path
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler._send_json = Mock()
    handler.send_error = Mock()
    handler.do_POST()

    return handler._send_json


def test_instance_wait_respond_and_cancel_routes_return_terminal_payloads() -> None:
    """Each route targets one exact speakId and exposes its terminal state.

    Args:
        None.

    Returns:
        None: Assertions validate terminal route payloads.
    """

    memory = VoiceMemory()
    response_id = memory.enqueue("Response", "es")
    cancel_id = memory.enqueue("Cancel", "es")
    assert response_id and cancel_id
    handler = object.__new__(VoiceDaemonHandler)
    handler.memory_provider = staticmethod(lambda: memory)

    response = _post(
        handler, "/instance/respond", {"instanceId": response_id, "response": "exact"}
    )
    assert response.call_args.kwargs["status"].value == 202
    assert response.call_args.args[0] == {
        "ok": True,
        "speakId": response_id,
        "state": "RESPONSED",
        "response": "exact",
    }

    wait = _post(
        handler, "/instance/wait", {"instanceId": response_id, "timeoutSeconds": 0}
    )
    assert wait.call_args.args[0]["state"] == "RESPONSED"

    cancel = _post(handler, "/instance/cancel", {"instanceId": cancel_id})
    assert cancel.call_args.kwargs["status"].value == 202
    assert cancel.call_args.args[0]["state"] == InstanceTerminalState.CANCELED.value


def test_instance_http_validation_unknown_and_timeout_statuses_are_explicit() -> None:
    """Malformed, unknown, and not-yet-terminal requests map to clear statuses.

    Args:
        None.

    Returns:
        None: Assertions validate explicit HTTP status mappings.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("Pending", "es")
    assert speak_id
    handler = object.__new__(VoiceDaemonHandler)
    handler.memory_provider = staticmethod(lambda: memory)

    missing = _post(handler, "/instance/wait", {"timeoutSeconds": 0})
    assert missing.call_args.kwargs["status"].value == 400

    unknown = _post(handler, "/instance/cancel", {"instanceId": "missing"})
    assert unknown.call_args.kwargs["status"].value == 404

    timeout = _post(
        handler, "/instance/wait", {"instanceId": speak_id, "timeoutSeconds": 0}
    )
    assert timeout.call_args.kwargs["status"].value == 408
    assert timeout.call_args.args[0]["state"] == "TIMEOUT"


def test_instance_http_rejects_noncanonical_ids_and_short_route_aliases() -> None:
    """HTTP rejects noncanonical IDs and routes outside the instance namespace.

    Args:
        None.

    Returns:
        None: Assertions validate route and identifier rejection.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("Alias", "es")
    assert speak_id
    handler = object.__new__(VoiceDaemonHandler)
    handler.memory_provider = staticmethod(lambda: memory)

    whitespace = _post(handler, "/instance/cancel", {"instanceId": f" {speak_id}"})
    assert whitespace.call_args.kwargs["status"].value == 400

    alias = _post(handler, "/cancel", {"speakId": speak_id})
    assert alias.called is False


def test_non_head_cancel_removes_only_target_and_preserves_fifo_unfinished_tasks() -> None:
    """Exact queued cancellation keeps the head and remaining queue accounting.

    Args:
        None.

    Returns:
        None: Assertions validate queue order and unfinished work accounting.
    """

    memory = VoiceMemory()
    head_id = memory.enqueue("Head", "es")
    middle_id = memory.enqueue("Middle", "es")
    tail_id = memory.enqueue("Tail", "es")
    assert head_id and middle_id and tail_id
    unfinished_before = memory.requests.unfinished_work_count()

    result = memory.cancel_instance(middle_id)

    assert result is not None and result.state is InstanceTerminalState.CANCELED
    assert memory.requests.unfinished_work_count() == unfinished_before - 1
    assert memory.requests.get_nowait()["id"] == head_id
    memory.requests.task_done()
    assert memory.requests.get_nowait()["id"] == tail_id
    memory.requests.task_done()
    assert memory.requests.unfinished_work_count() == 0


def test_memory_projects_natural_error_and_shutdown_terminal_outcomes() -> None:
    """Daemon-owned state maps natural completion and failures to public outcomes.

    Args:
        None.

    Returns:
        None: Assertions validate projected terminal outcomes.
    """

    memory = VoiceMemory()
    spoke_id = memory.enqueue("Spoke", "es")
    error_id = memory.enqueue("Error", "es")
    live_id = memory.enqueue("Live", "es")
    assert spoke_id and error_id and live_id

    memory.set_speak_status(spoke_id, "DONE")
    memory.set_speak_status(error_id, "ERROR", error="provider")
    shutdown_results = memory.cancel_all_instances()

    assert (
        memory.instance_lifecycle.result(spoke_id).state
        is InstanceTerminalState.SPEAKED
    )
    assert (
        memory.instance_lifecycle.result(error_id).state
        is InstanceTerminalState.CANCELED
    )
    assert tuple(result.instance_id for result in shutdown_results) == (live_id,)
    assert (
        memory.instance_lifecycle.result(live_id).state
        is InstanceTerminalState.CANCELED
    )


def test_terminal_status_projection_is_first_winner_only() -> None:
    """A later status update cannot overwrite a previously published terminal state.

    Args:
        None.

    Returns:
        None: Assertions validate first-winner terminal projection.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("One winner", "es")
    assert speak_id

    memory.set_speak_status(speak_id, "DONE")
    memory.set_speak_status(speak_id, "ERROR", error="late provider error")

    record = next(item for item in memory.speaks if item["id"] == speak_id)
    assert record["status"] == "DONE"
    assert (
        memory.instance_lifecycle.result(speak_id).state
        is InstanceTerminalState.SPEAKED
    )


def test_composer_open_route_accepts_only_the_live_speaking_instance() -> None:
    """Verify the hold route is exact-ID and rejects duplicate acquisition.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate hold route success and stale rejection.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("Composer target", "es")
    other_id = memory.enqueue("Other target", "es")
    assert speak_id is not None and other_id is not None
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    session = memory.begin_message_session(request)
    assert session is not None
    memory.prepare_playback("Composer target", "focused", speak_id=speak_id)
    memory.mark_playback_started()
    handler = object.__new__(VoiceDaemonHandler)
    handler.memory_provider = staticmethod(lambda: memory)

    opened = _post(
        handler,
        "/instance/composer-open",
        {"instanceId": speak_id},
    )
    assert opened.call_args.kwargs["status"].value == 202
    assert opened.call_args.args[0] == {
        "ok": True,
        "speakId": speak_id,
        "held": True,
    }

    duplicate = _post(
        handler,
        "/instance/composer-open",
        {"instanceId": speak_id},
    )
    assert duplicate.call_args.kwargs["status"].value == 409
    assert duplicate.call_args.args[0]["held"] is False

    mismatched = _post(
        handler,
        "/instance/composer-open",
        {"instanceId": other_id},
    )
    assert mismatched.call_args.kwargs["status"].value == 409
    assert mismatched.call_args.args[0]["speakId"] == other_id

    unknown = _post(
        handler,
        "/instance/composer-open",
        {"instanceId": "missing"},
    )
    assert unknown.call_args.kwargs["status"].value == 404


def test_composer_open_route_rejects_terminal_instance() -> None:
    """Verify a terminal message cannot be retroactively held.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate terminal-state rejection.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("Already done", "es")
    assert speak_id is not None
    memory.set_speak_status(speak_id, "DONE")
    handler = object.__new__(VoiceDaemonHandler)
    handler.memory_provider = staticmethod(lambda: memory)

    response = _post(
        handler,
        "/instance/composer-open",
        {"instanceId": speak_id},
    )

    assert response.call_args.kwargs["status"].value == 409
    assert response.call_args.args[0]["held"] is False


def test_composer_open_route_rejects_missing_padded_and_contradictory_ids() -> None:
    """Verify composer holds reuse strict exact-ID request validation.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate malformed identity rejection.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("Validation target", "es")
    assert speak_id is not None
    handler = object.__new__(VoiceDaemonHandler)
    handler.memory_provider = staticmethod(lambda: memory)

    missing = _post(handler, "/instance/composer-open", {})
    assert missing.call_args.kwargs["status"].value == 400

    padded = _post(
        handler,
        "/instance/composer-open",
        {"instanceId": f" {speak_id}"},
    )
    assert padded.call_args.kwargs["status"].value == 400

    contradictory = _post(
        handler,
        "/instance/composer-open",
        {"instanceId": speak_id, "speakId": "other"},
    )
    assert contradictory.call_args.kwargs["status"].value == 400


def test_composer_close_releases_and_reopens_same_instance_without_fifo_advance() -> None:
    """REQ-01: RELEASED close reopens the same hold without terminalizing or advancing FIFO.

    Args:
        None.

    Returns:
        None: Assertions validate hold release, reopening, and queue stability.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("Held target", "es")
    queued_id = memory.enqueue("Still pending", "es")
    assert speak_id is not None and queued_id is not None
    request = memory.requests.get_nowait()
    session = memory.begin_message_session(request)
    assert session is not None
    memory.prepare_playback("Held target", "focused", speak_id=speak_id)
    memory.mark_playback_started()
    handler = object.__new__(VoiceDaemonHandler)
    handler.memory_provider = staticmethod(lambda: memory)

    opened = _post(
        handler,
        "/instance/composer-open",
        {"instanceId": speak_id},
    )
    assert opened.call_args.kwargs["status"].value == 202
    assert opened.call_args.args[0]["held"] is True
    queued_before_close = memory.requests.qsize()
    unfinished_before_close = memory.requests.unfinished_work_count()

    closed = _post(
        handler,
        "/instance/composer-close",
        {"instanceId": speak_id},
    )
    assert closed.call_args.kwargs["status"].value == 202
    assert closed.call_args.args[0] == {
        "ok": True,
        "instanceId": speak_id,
        "speakId": speak_id,
        "state": "RELEASED",
        "held": False,
    }
    assert memory.instance_lifecycle.result(speak_id) is None
    assert memory.active_session is session
    assert memory.requests.qsize() == queued_before_close
    assert memory.requests.unfinished_work_count() == unfinished_before_close

    reopened = _post(
        handler,
        "/instance/composer-open",
        {"instanceId": speak_id},
    )
    assert reopened.call_args.kwargs["status"].value == 202
    assert reopened.call_args.args[0] == {
        "ok": True,
        "speakId": speak_id,
        "held": True,
    }
    assert memory.instance_lifecycle.result(speak_id) is None
    assert memory.active_session is session
    assert memory.requests.qsize() == queued_before_close
    assert memory.requests.unfinished_work_count() == unfinished_before_close
