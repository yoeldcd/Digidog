"""Verify synchronous lifecycle coordination for daemon speak instances.

Tests InstanceLifecycleRegistry thread-safety, atomic first-winner transitions,
waiter synchronization, timeout handling, and terminal entry pruning.
"""

from __future__ import annotations

import threading
import time

import pytest

from brain.infrastructure.voice.daemon.daemon import VoiceMemory

from brain.infrastructure.voice.messaging.instance_lifecycle import (
    InstanceLifecycleRegistry,
    InstanceTerminalResult,
    InstanceTerminalState,
)


def test_waiter_releases_only_for_matching_instance() -> None:
    """Verify that a terminal result wakes only its matching instance waiter.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate instance-specific waiter release.
    """
    registry = InstanceLifecycleRegistry()
    registry.register("speak-a")
    registry.register("speak-b")

    registry.terminalize("speak-b", InstanceTerminalState.SPEAKED)

    assert registry.wait("speak-a", timeout=0) is None
    assert registry.wait("speak-b", timeout=0).instance_id == "speak-b"


def test_terminal_race_has_exactly_one_winner() -> None:
    """Verify that concurrent terminal attempts publish one immutable result.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the single-winner race contract.
    """
    registry = InstanceLifecycleRegistry()
    registry.register("speak-race")
    barrier = threading.Barrier(3)
    winners: list[InstanceTerminalState] = []

    def terminalize(state: InstanceTerminalState, response: str = "") -> None:
        """Attempt one terminal transition from a concurrent worker.

        Args:
            state: Terminal state proposed by this worker.
            response: Optional response payload proposed by this worker.

        Returns:
            None: A winning state is recorded for the enclosing test.
        """

        barrier.wait()

        result = registry.terminalize("speak-race", state, response)

        if result is not None:
            winners.append(result.state)

    threads = (
        threading.Thread(target=terminalize, args=(InstanceTerminalState.SPEAKED,)),
        threading.Thread(target=terminalize, args=(InstanceTerminalState.RESPONSED, "yes")),
    )

    for thread in threads:
        thread.start()

    barrier.wait()

    for thread in threads:
        thread.join()

    assert len(winners) == 1
    assert registry.wait("speak-race", timeout=0).state in winners


def test_shutdown_cancels_every_live_instance() -> None:
    """Verify shutdown cancels live waiters without replacing terminal data.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate shutdown cancellation and retention.
    """
    registry = InstanceLifecycleRegistry()
    registry.register("speak-done")
    registry.register("speak-live")
    registry.terminalize("speak-done", InstanceTerminalState.SPEAKED)

    cancelled = registry.cancel_all()

    assert tuple(result.instance_id for result in cancelled) == ("speak-live",)
    assert registry.result("speak-done").state is InstanceTerminalState.SPEAKED
    assert registry.result("speak-live").state is InstanceTerminalState.CANCELED


def test_registry_rejects_invalid_public_values() -> None:
    """Verify malformed public values fail explicitly.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate public input rejection.
    """
    registry = InstanceLifecycleRegistry()

    with pytest.raises(ValueError):
        registry.register("")

    registry.register("speak-valid")

    with pytest.raises(ValueError):
        registry.wait("speak-valid", timeout=-1)

    with pytest.raises(ValueError):
        registry.terminalize("speak-valid", InstanceTerminalState.RESPONSED)

    with pytest.raises(KeyError):
        registry.wait("speak-unknown", timeout=0)


def test_response_text_is_preserved_exactly_and_stale_transition_cannot_replace_it() -> None:
    """Verify a response remains byte-for-byte available to its waiter.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate response preservation and stale rejection.
    """
    registry = InstanceLifecycleRegistry()
    registry.register("speak-response")
    response = "  exact response\nwith spacing  "

    winner = registry.terminalize(
        "speak-response", InstanceTerminalState.RESPONSED, response
    )

    assert winner == InstanceTerminalResult(
        "speak-response", InstanceTerminalState.RESPONSED, response
    )

    assert registry.terminalize("speak-response", InstanceTerminalState.CANCELED) is None
    assert registry.wait("speak-response", timeout=0) == winner


def test_retention_prunes_only_old_terminal_entries_and_keeps_live_waiters() -> None:
    """Verify retention prunes old terminals while keeping live instances.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate bounded terminal retention.
    """
    registry = InstanceLifecycleRegistry(retention=1)
    registry.register("speak-live")
    registry.register("speak-old")
    registry.register("speak-new")
    registry.terminalize("speak-old", InstanceTerminalState.SPEAKED)
    registry.terminalize("speak-new", InstanceTerminalState.CANCELED)

    with pytest.raises(KeyError):
        registry.result("speak-old")

    assert registry.result("speak-live") is None
    assert registry.result("speak-new").state is InstanceTerminalState.CANCELED


def test_wait_is_bounded_and_released_by_matching_terminal_transition() -> None:
    """Verify a matching terminal event releases a bounded waiter promptly.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate prompt event-driven waiter release.
    """
    registry = InstanceLifecycleRegistry()
    registry.register("speak-wait")
    observed: list[InstanceTerminalResult | None] = []

    def waiter() -> None:
        """Wait for and capture the instance's terminal result.

        Args:
            No external arguments are accepted; the thread invokes the waiter.

        Returns:
            None: The observed result is appended to the enclosing test list.
        """

        observed.append(registry.wait("speak-wait", timeout=30))

    thread = threading.Thread(target=waiter)
    started = time.monotonic()

    thread.start()
    time.sleep(0.01)
    registry.terminalize("speak-wait", InstanceTerminalState.SPEAKED)
    thread.join(timeout=1)

    assert thread.is_alive() is False
    assert time.monotonic() - started < 1
    assert observed[0] is not None


def test_waiter_keeps_captured_result_after_retention_prunes_lookup() -> None:
    """A waiter already observing an entry survives terminal retention pruning.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the wait and retention race contract.
    """
    registry = InstanceLifecycleRegistry(retention=1)
    registry.register("speak-wait")
    registry.register("speak-other")
    entry = registry._entries["speak-wait"]
    event_released = threading.Event()
    allow_return = threading.Event()
    original_wait = entry.event.wait

    def delayed_wait(timeout: float | None = None) -> bool:
        """Pause a waiter after release and before result lookup.

        Args:
            timeout: Maximum duration passed to the original event waiter.

        Returns:
            bool: Whether the original event wait observed a release.
        """

        result = original_wait(timeout)
        event_released.set()
        allow_return.wait(timeout=1)

        return result

    entry.event.wait = delayed_wait  # type: ignore[method-assign]
    observed: list[InstanceTerminalResult | None] = []
    waiter = threading.Thread(
        target=lambda: observed.append(registry.wait("speak-wait", timeout=1)),
    )
    waiter.start()
    registry.terminalize("speak-wait", InstanceTerminalState.SPEAKED)
    assert event_released.wait(timeout=1)

    registry.terminalize("speak-other", InstanceTerminalState.CANCELED)

    with pytest.raises(KeyError):
        registry.result("speak-wait")

    allow_return.set()
    waiter.join(timeout=1)
    assert waiter.is_alive() is False
    assert observed == [InstanceTerminalResult("speak-wait", InstanceTerminalState.SPEAKED)]


def test_duplicate_terminal_status_cannot_replace_first_result() -> None:
    """Verify a completed instance keeps its first terminal state and record.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate first-terminal-wins behavior.
    """
    registry = InstanceLifecycleRegistry()
    registry.register("speak-once")

    assert (
        registry.terminalize("speak-once", InstanceTerminalState.SPEAKED) is not None
    )

    assert registry.terminalize("speak-once", InstanceTerminalState.CANCELED) is None
    assert registry.result("speak-once") == InstanceTerminalResult(
        "speak-once", InstanceTerminalState.SPEAKED
    )


def test_only_terminal_states_are_publicly_constructible() -> None:
    """Verify the enum rejects arbitrary values and exposes terminal states only.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate enum value rejection.
    """

    with pytest.raises(ValueError):
        InstanceTerminalState("WORKING")


def test_natural_close_terminalizes_speaked_without_a_composer_hold() -> None:
    """Verify ordinary playback completion releases the active message normally.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the ordinary SPEAKED terminal transition.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("Natural completion", "es")
    assert speak_id is not None
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    session = memory.begin_message_session(request)
    assert session is not None
    memory.prepare_playback("Natural completion", "focused", speak_id=speak_id)
    memory.mark_playback_started()

    memory.close_message_session(session, "DONE")

    result = memory.instance_lifecycle.result(speak_id)
    assert result is not None
    assert result.state is InstanceTerminalState.SPEAKED
    assert memory.active_session is None


def test_response_releases_exact_composer_hold_and_unblocks_natural_close() -> None:
    """Verify a response resolves only the held active message.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate exact hold release and response precedence.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("Reply target", "es")
    assert speak_id is not None
    request = memory.requests.get_nowait()
    memory.requests.task_done()
    session = memory.begin_message_session(request)
    assert session is not None
    memory.prepare_playback("Reply target", "focused", speak_id=speak_id)
    memory.mark_playback_started()

    assert memory.open_composer_hold(speak_id) is True
    close_started = threading.Event()
    close_finished = threading.Event()

    def close_naturally() -> None:
        """Run the natural close and expose both lifecycle boundaries.

        Args:
            No arguments are accepted; the enclosing test supplies the session.

        Returns:
            None: The close completion event is set after the lifecycle returns.
        """

        close_started.set()
        memory.close_message_session(session, "DONE")
        close_finished.set()

    close_thread = threading.Thread(target=close_naturally)
    close_thread.start()
    assert close_started.wait(timeout=1)
    assert memory.instance_lifecycle.result(speak_id) is None
    assert close_finished.is_set() is False

    result = memory.respond_instance(speak_id, "exact response")

    assert result is not None
    assert result.state is InstanceTerminalState.RESPONSED
    assert close_finished.wait(timeout=1)
    close_thread.join(timeout=1)
    assert close_thread.is_alive() is False
    assert memory.instance_lifecycle.result(speak_id) == result
    assert memory.active_session is None


def test_cancel_releases_exact_composer_hold_without_waking_another_instance() -> None:
    """Verify cancellation releases the held session and preserves instance scope.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate cancellation and non-cross-waking behavior.
    """

    memory = VoiceMemory()
    first_id = memory.enqueue("Held message", "es")
    second_id = memory.enqueue("Other message", "es")
    assert first_id is not None and second_id is not None
    first_request = memory.requests.get_nowait()
    memory.requests.task_done()
    first_session = memory.begin_message_session(first_request)
    assert first_session is not None
    memory.prepare_playback("Held message", "focused", speak_id=first_id)
    memory.mark_playback_started()
    assert memory.open_composer_hold(first_id) is True

    close_finished = threading.Event()

    def close_naturally() -> None:
        """Run the first message's natural close behind its hold.

        Args:
            No arguments are accepted; the enclosing test supplies the session.

        Returns:
            None: The close completion event is set after the lifecycle returns.
        """

        memory.close_message_session(first_session, "DONE")
        close_finished.set()

    close_thread = threading.Thread(target=close_naturally)
    close_thread.start()

    result = memory.cancel_instance(first_id)

    assert result is not None
    assert result.state is InstanceTerminalState.CANCELED
    assert close_finished.wait(timeout=1)
    close_thread.join(timeout=1)
    assert close_thread.is_alive() is False
    assert memory.instance_lifecycle.result(second_id) is None


def test_held_fifo_head_keeps_b_and_c_pending_until_head_resolves() -> None:
    """Verify an A/B/C FIFO activates B once only after held A resolves.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate FIFO order, barrier ownership, and accounting.
    """

    memory = VoiceMemory()
    ids = [memory.enqueue(label, "es") for label in ("A", "B", "C")]
    assert all(ids)
    first_id, second_id, third_id = (str(item) for item in ids)
    first_request = memory.requests.get_next()
    first_session = memory.begin_message_session(first_request)
    assert first_session is not None
    memory.prepare_playback("A", "focused", speak_id=first_id)
    memory.mark_playback_started()
    assert memory.open_composer_hold(first_id) is True
    assert memory.requests.qsize() == 2

    assert memory.respond_instance(first_id, "release A") is not None
    memory.close_message_session(first_session, "DONE")
    memory.requests.task_done()

    second_request = memory.requests.get_next()
    second_session = memory.begin_message_session(second_request)
    assert second_request["id"] == second_id
    assert second_session is not None
    assert memory.begin_message_session(second_request) is None
    assert memory.requests.qsize() == 1
    memory.close_message_session(second_session, "DONE")
    memory.requests.task_done()

    third_request = memory.requests.get_next()
    third_session = memory.begin_message_session(third_request)
    assert third_request["id"] == third_id
    assert third_session is not None
    memory.close_message_session(third_session, "DONE")
    memory.requests.task_done()
    assert memory.requests.unfinished_work_count() == 0


def test_composer_close_after_natural_close_started_yields_canceled() -> None:
    """REQ-02: A close after the natural boundary cancels the instance.

    Args:
        None.

    Returns:
        None: Assertions validate the post-boundary cancellation transition.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("Natural boundary", "es")
    assert speak_id is not None
    request = memory.requests.get_nowait()
    session = memory.begin_message_session(request)
    assert session is not None
    memory.prepare_playback("Natural boundary", "focused", speak_id=speak_id)
    memory.mark_playback_started()
    assert memory.open_composer_hold(speak_id) is True

    natural_boundary = threading.Event()
    natural_finished = threading.Event()
    original_wait = memory._wait_for_composer_hold

    def wait_for_hold(waiting_session: object) -> None:
        """Expose the exact natural-close boundary before waiting."""

        assert waiting_session is session
        natural_boundary.set()
        original_wait(waiting_session)  # type: ignore[arg-type]

    memory._wait_for_composer_hold = wait_for_hold  # type: ignore[method-assign]

    def close_naturally() -> None:
        """Run natural close until the composer resolves it."""

        memory.close_message_session(session, "DONE")
        natural_finished.set()

    close_thread = threading.Thread(target=close_naturally)
    close_thread.start()

    assert natural_boundary.wait(timeout=1)
    with memory.lock:
        assert session.natural_close_started is True

    close_result = memory.close_composer_hold(speak_id)

    assert close_result.state == InstanceTerminalState.CANCELED.value
    assert close_result.terminal_result is None
    assert natural_finished.wait(timeout=1)
    close_thread.join(timeout=1)
    assert close_thread.is_alive() is False
    assert memory.instance_lifecycle.result(speak_id).state is InstanceTerminalState.CANCELED
    assert memory.active_session is None


def test_response_and_composer_close_race_has_one_terminal_winner() -> None:
    """REQ-03: Concurrent response and close publish one first terminal winner.

    Args:
        None.

    Returns:
        None: Assertions validate winner and loser consistency.
    """

    memory = VoiceMemory()
    speak_id = memory.enqueue("Race target", "es")
    assert speak_id is not None
    request = memory.requests.get_nowait()
    session = memory.begin_message_session(request)
    assert session is not None
    memory.prepare_playback("Race target", "focused", speak_id=speak_id)
    memory.mark_playback_started()
    assert memory.open_composer_hold(speak_id) is True
    with memory.lock:
        session.natural_close_started = True

    barrier = threading.Barrier(3)
    response_results: list[InstanceTerminalResult | None] = []
    close_results = []

    def respond() -> None:
        """Race an exact response against the composer close."""

        barrier.wait()
        response_results.append(memory.respond_instance(speak_id, "race response"))

    def close() -> None:
        """Race an exact composer close against the response."""

        barrier.wait()
        close_results.append(memory.close_composer_hold(speak_id))

    response_thread = threading.Thread(target=respond)
    close_thread = threading.Thread(target=close)
    response_thread.start()
    close_thread.start()
    barrier.wait()
    response_thread.join(timeout=1)
    close_thread.join(timeout=1)

    assert response_thread.is_alive() is False
    assert close_thread.is_alive() is False
    assert len(response_results) == 1
    assert len(close_results) == 1

    response_result = response_results[0]
    close_result = close_results[0]
    lifecycle_result = memory.instance_lifecycle.result(speak_id)

    assert lifecycle_result is not None
    assert lifecycle_result.state in {
        InstanceTerminalState.RESPONSED,
        InstanceTerminalState.CANCELED,
    }

    if response_result is not None:
        assert response_result == lifecycle_result
        assert close_result.state == InstanceTerminalState.RESPONSED.value
        assert close_result.terminal_result == lifecycle_result
    else:
        assert lifecycle_result.state is InstanceTerminalState.CANCELED
        assert close_result.state == InstanceTerminalState.CANCELED.value
        assert close_result.terminal_result is None
