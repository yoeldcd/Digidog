# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Client and lifecycle launcher for the local voice daemon.

Provides engine-independent speech dispatch, synchronous instance waiting,
and state snapshot retrieval over HTTP transport. Manages daemon process
supervision, health checks, and exact-instance cancellation.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TypeAlias
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from brain.infrastructure.avatar.configuration.avatar_config import (
    resolve_voice_daemon_endpoint,
)
from brain.infrastructure.voice.daemon.process_lease import core_runtime_id
from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.contracts.instance_results import (
    InstanceEnqueueResult,
    InstanceTerminalResult,
    instance_id_from_payload,
    terminal_result_from_payload,
)


VoiceJson: TypeAlias = dict[str, object]
"""JSON object exchanged with the local daemon."""

VOICE_DAEMON_HOST, VOICE_DAEMON_PORT = resolve_voice_daemon_endpoint()
VOICE_DAEMON_URL = f"http://{VOICE_DAEMON_HOST}:{VOICE_DAEMON_PORT}"
VOICE_CORE_ID = core_runtime_id()
VOICE_DAEMON_STARTUP_TIMEOUT_SECONDS = 10.0
VOICE_DAEMON_REQUEST_TIMEOUT_SECONDS = 1.0
VOICE_INSTANCE_WAIT_TIMEOUT_SECONDS = 30.0
VOICE_INSTANCE_CANCEL_TIMEOUT_SECONDS = 2.0


def consumer_repository_path(start: Path | None = None) -> str:
    """Find the nearest repository root for the process issuing speech.

    Args:
        start (Path | None): Search origin, or ``None`` for the working directory.

    Returns:
        str: Nearest ancestor containing ``.git``, or the resolved origin.
    """
    current = (start or Path.cwd()).resolve()

    # Iteration: loop over collection elements
    for candidate in (current, *current.parents):
        # Conditional check: evaluate domain preconditions and invariants
        if (candidate / ".git").exists():
            return str(candidate)

    return str(current)


def runs_inside_codex_sandbox() -> bool:
    """Detect whether Windows assigned the process to a Codex sandbox account.

    Args:
        None.

    Returns:
        bool: ``True`` for a Windows Codex sandbox account.
    """
    username = os.environ.get("USERNAME", "")

    return sys.platform == "win32" and username.casefold().startswith("codexsandbox")


class VoiceDaemonClient:
    """Dispatch voice work and read in-memory outputs from one warm daemon."""

    def enqueue(self, request: AvatarSpeakRequest) -> InstanceEnqueueResult | None:
        """Enqueue one request and retain its daemon-owned identity immutably.

        Submits an avatar speak request to the warm daemon process via HTTP POST.
        Extracts the accepted canonical speak identifier and returns a typed
        enqueue result for tracking.

        Args:
            request: Complete immutable avatar request to submit.

        Returns:
            InstanceEnqueueResult | None: Canonical identity accepted by the
            daemon, or ``None`` when the daemon accepted no logical emission.

        Raises:
            ValueError: If the daemon acknowledgement does not contain an ID.
        """

        acknowledgement = self.speak(request)

        queued = acknowledgement.get("queued", True)

        # Type validation: verify parameter data type
        if not isinstance(queued, bool):
            raise ValueError("Daemon queue acknowledgement must be boolean.")

        # Conditional check: evaluate domain preconditions and invariants
        if not queued:
            return None

        instance_id = instance_id_from_payload(acknowledgement)

        return InstanceEnqueueResult(instance_id=instance_id, queued=queued)

    def speak_and_wait(
        self,
        request: AvatarSpeakRequest,
        timeout_seconds: float = VOICE_INSTANCE_WAIT_TIMEOUT_SECONDS,
    ) -> InstanceTerminalResult | None:
        """Enqueue one request and await only its own terminal state.

        Submits a speech request to the daemon and blocks until the exact instance
        reaches SPEAKED, RESPONSED, or CANCELED. Handles segmented HTTP polling and
        cancels the instance on interruption or timeout.

        Args:
            request: Complete immutable avatar request to submit.
            timeout_seconds: Total caller wait budget before exact-ID cancellation.

        Returns:
            InstanceTerminalResult | None: Explicit ``SPEAKED``, ``RESPONSED``,
            or ``CANCELED`` result owned by the submitted request, or ``None``
            when no logical emission was accepted.

        Raises:
            KeyboardInterrupt: After cancelling the exact submitted instance.
            TimeoutError: If the daemon cannot acknowledge the cancellation.
            ValueError: If the daemon returns malformed lifecycle data.
        """

        # Enqueue submission: send avatar speak request to daemon
        enqueue_result = self.enqueue(request)

        # Conditional check: evaluate domain preconditions and invariants
        if enqueue_result is None:
            return None

        # Wait loop: poll bounded daemon wait segments until terminal state or deadline
        try:
            terminal = self.wait(
                enqueue_result.instance_id,
                timeout_seconds=timeout_seconds,
            )

        # Interruption fallback: cancel exact speak ID on Ctrl-C
        except KeyboardInterrupt:
            self.cancel(enqueue_result.instance_id)

            raise

        # Failure recovery: handle execution or transport exception
        except TimeoutError:
            terminal = None

        # Conditional check: evaluate domain preconditions and invariants
        if terminal is not None:
            return terminal

        return self.cancel(enqueue_result.instance_id)

    def start(self, mode: str = "light") -> VoiceJson:
        """Idempotently start the daemon and apply an avatar theme.

        Args:
            mode (str): Initial ``light`` or ``dark`` theme.

        Returns:
            VoiceJson: Ready daemon status snapshot.

        Raises:
            ValueError: If ``mode`` is unsupported.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if mode not in {"dark", "light"}:
            raise ValueError(f"Unsupported avatar theme: {mode}")

        self._ensure_daemon()
        self._request_json(path="/theme", method="POST", payload={"mode": mode})

        return self._request_json(path="/status")

    def speak(self, request: AvatarSpeakRequest) -> VoiceJson:
        """Enqueue one message after lazily ensuring the daemon exists.

        Args:
            request: Complete immutable avatar request to submit.

        Returns:
            VoiceJson: Daemon enqueue acknowledgement and speak metadata.
        """

        self._ensure_daemon()
        payload = request.to_payload()

        payload["consumerPath"] = request.consumer_path or consumer_repository_path()
        payload["codexThreadId"] = request.codex_thread_id or os.environ.get(
            "CODEX_THREAD_ID", ""
        )

        return self._request_json(path="/speak", method="POST", payload=payload)

    def wait_instance(
        self,
        instance_id: str,
        timeout_seconds: float = VOICE_INSTANCE_WAIT_TIMEOUT_SECONDS,
    ) -> InstanceTerminalResult | None:
        """Wait for one exact daemon instance with a bounded transport timeout.

        Issues HTTP requests to the /instance/wait route using segmented timeouts.
        Loops until the daemon returns a final terminal result or the total caller
        deadline is reached.

        Args:
            instance_id: Exact ``speakId`` returned by the matching enqueue.
            timeout_seconds: Total caller wait budget; each daemon segment is capped by the client.

        Returns:
            InstanceTerminalResult | None: Matching terminal result, or ``None``
            when the total caller wait budget expires.

        Raises:
            ValueError: If the identity, timeout, or terminal payload is invalid.
            HTTPError: If the daemon rejects the request for another reason.
        """

        # Identity resolution: parse canonical instance identity
        canonical_id = instance_id_from_payload({"instanceId": instance_id})
        total_timeout = _validated_instance_timeout(timeout_seconds)
        deadline = time.monotonic() + total_timeout
        remaining_timeout = total_timeout
        held_remaining_timeout: float | None = None

        # Loop execution: process until boundary condition is satisfied
        while True:
            if held_remaining_timeout is None:
                segment_timeout = _bounded_instance_timeout(remaining_timeout)
            else:
                segment_timeout = VOICE_INSTANCE_WAIT_TIMEOUT_SECONDS
            payload = {
                "instanceId": canonical_id,
                "timeoutSeconds": segment_timeout,
            }

            # Exception safety: execute operation within error boundary
            try:
                response = self._request_instance_json(
                    path="/instance/wait",
                    instance_id=canonical_id,
                    payload=payload,
                    timeout=min(
                        VOICE_INSTANCE_WAIT_TIMEOUT_SECONDS,
                        segment_timeout + VOICE_DAEMON_REQUEST_TIMEOUT_SECONDS,
                    ),
                    legacy_payload={
                        "speakId": canonical_id,
                        "timeout": segment_timeout,
                    },
                )

            # HTTP error handling: process server response status
            except HTTPError as exc:
                # Conditional check: evaluate domain preconditions and invariants
                if exc.code != 408:
                    raise

                try:
                    parsed = json.loads(exc.read().decode("utf-8"))
                except Exception:
                    parsed = None
                response = parsed if isinstance(parsed, dict) else None

            # Failure recovery: handle execution or transport exception
            except TimeoutError:
                response = None

            # State guard: verify lifecycle status preconditions
            response_state = str(response.get("state", "")) if response else ""
            if response_state == "HELD":
                if held_remaining_timeout is None:
                    held_remaining_timeout = max(0.0, deadline - time.monotonic())
                continue

            if response is not None and response_state != "TIMEOUT":
                return terminal_result_from_payload(
                    response,
                    expected_instance_id=canonical_id,
                )

            # Timeout check: verify bounded wait duration
            if held_remaining_timeout is not None:
                remaining_timeout = held_remaining_timeout
                held_remaining_timeout = None
                continue

            if segment_timeout <= 0:
                return None

            remaining_timeout = deadline - time.monotonic()

            # Timeout check: verify bounded wait duration
            if remaining_timeout <= 0:
                return None

    def cancel_instance(self, instance_id: str) -> InstanceTerminalResult:
        """Cancel one exact daemon instance and return its terminal outcome.

        Dispatches a cancellation request to the /instance/cancel route for a given
        speak identifier. Returns the winning terminal result even if a concurrent
        terminal state already won.

        Args:
            instance_id: Exact ``speakId`` returned by the matching enqueue.

        Returns:
            InstanceTerminalResult: Explicit cancellation or already-won state.

        Raises:
            ValueError: If the identity or terminal payload is invalid.
            HTTPError: If the daemon cannot find or cancel the instance.
        """

        canonical_id = instance_id_from_payload({"instanceId": instance_id})

        # Exception safety: execute operation within error boundary
        try:
            response = self._request_instance_json(
                path="/instance/cancel",
                instance_id=canonical_id,
                payload={"instanceId": canonical_id},
                timeout=VOICE_INSTANCE_CANCEL_TIMEOUT_SECONDS,
                legacy_payload={"speakId": canonical_id},
            )

        # HTTP error handling: process server response status
        except HTTPError as exc:
            # Conditional check: evaluate domain preconditions and invariants
            if exc.code != 409:
                raise

            response = json.loads(exc.read().decode("utf-8"))

            # Type validation: verify parameter data type
            if not isinstance(response, dict):
                raise ValueError("Daemon cancellation response must be an object.")

        return terminal_result_from_payload(response, expected_instance_id=canonical_id)

    def wait(
        self,
        instance_id: str,
        timeout_seconds: float = VOICE_INSTANCE_WAIT_TIMEOUT_SECONDS,
    ) -> InstanceTerminalResult | None:
        """Preserve a concise alias for waiting on one exact instance.

        Args:
            instance_id: Exact daemon-created identity to observe.
            timeout_seconds: Total caller wait budget.

        Returns:
            InstanceTerminalResult | None: Matching terminal result or timeout.
        """

        return self.wait_instance(instance_id, timeout_seconds=timeout_seconds)

    def cancel(self, instance_id: str) -> InstanceTerminalResult:
        """Preserve a concise alias for exact-ID cancellation.

        Args:
            instance_id: Exact daemon-created identity to cancel.

        Returns:
            InstanceTerminalResult: Terminal result for the exact identity.
        """

        return self.cancel_instance(instance_id)

    def narrate_active_file(self) -> VoiceJson:
        """Request narration of the active embedded-file message.

        Args:
            None.

        Returns:
            VoiceJson: Daemon acknowledgement for the narration request.
        """

        self._ensure_daemon()

        return self._request_json(
            path="/narrate-active-file", method="POST", payload={}
        )

    def set_ambient_state(self, state: str) -> VoiceJson:
        """Persist the avatar state restored after transient voice activity.

        Args:
            state (str): Canonical ambient state name.

        Returns:
            VoiceJson: Daemon acknowledgement and resulting state.
        """

        self._ensure_daemon()

        return self._request_json(
            path="/ambient-state", method="POST", payload={"state": state}
        )

    def replay(
        self,
        name: str | None = None,
        speak_id: str | None = None,
    ) -> VoiceJson:
        """Replay projected or latest eligible speech without new logical history.

        Args:
            name: Optional retained message name.
            speak_id: Optional retained daemon speak ID.

        Returns:
            VoiceJson: Daemon replay acknowledgement.
        """

        self._ensure_daemon()

        return self._request_json(
            path="/replay",
            method="POST",
            payload={"name": name or "", "speakId": speak_id or ""},
        )

    def stop_current_message(self) -> VoiceJson:
        """Terminally cancel audible or muted current speak and advance its FIFO.

        Args:
            None.

        Returns:
            VoiceJson: Daemon stop acknowledgement.
        """

        self._ensure_daemon()

        return self._request_json(
            path="/stop-current-message", method="POST", payload={}
        )

    def dismiss(self) -> VoiceJson:
        """Dismiss the active muted presentation and continue the queue.

        Args:
            None.

        Returns:
            VoiceJson: Daemon dismissal acknowledgement.
        """

        self._ensure_daemon()

        return self._request_json(path="/dismiss", method="POST", payload={})

    def pause(self) -> VoiceJson:
        """Invoke the legacy pause route, which terminally cancels the current speak.

        The route name remains only for compatibility; paused state and resume do not exist.

        Args:
            None.

        Returns:
            VoiceJson: Daemon compatibility-route acknowledgement.
        """

        self._ensure_daemon()

        return self._request_json(path="/pause", method="POST", payload={})

    def messages(self) -> list[VoiceJson]:
        """Read in-memory message metadata without starting a daemon.

        Args:
            None.

        Returns:
            list[VoiceJson]: Retained message metadata, or an empty list
            when the daemon is unavailable.
        """

        # Exception safety: execute operation within error boundary
        try:
            payload = self._request_json(path="/messages")

        # Failure recovery: handle execution or transport exception
        except (OSError, URLError):
            return []

        return payload.get("messages", [])

    def snapshot(self) -> VoiceJson:
        """Return retained speak jobs and synthesized messages.

        Args:
            None.

        Returns:
            VoiceJson: Queue snapshot, or an empty successful snapshot when
            the daemon is unavailable.
        """

        # Exception safety: execute operation within error boundary
        try:
            return self._request_json(path="/messages")

        # Failure recovery: handle execution or transport exception
        except (OSError, URLError):
            return {"ok": True, "speaks": [], "messages": []}

    def status_snapshot(self) -> VoiceJson:
        """Read daemon lifecycle state and queue data without starting it.

        Args:
            None.

        Returns:
            VoiceJson: Combined status and queue snapshot.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self._is_healthy():
            return {"ok": False, "state": "stopped", "speaks": [], "messages": []}
        status = self._request_json(path="/status")
        status.update(self._request_json(path="/messages"))

        return status

    def status(self) -> VoiceJson:
        """Read the last daemon-owned playback state without starting it.

        Args:
            None.

        Returns:
            VoiceJson: Playback status or a stopped-state fallback.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self._is_healthy():
            return {"ok": False, "state": "stopped", "activeSpeakId": ""}

        return self._request_json(path="/status")

    def stop(self) -> bool:
        """Request graceful shutdown without starting a missing daemon.

        Args:
            None.

        Returns:
            bool: Whether a running daemon accepted the shutdown request.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self._is_healthy():
            return False

        return bool(
            self._request_json(path="/stop", method="POST", payload={}).get("stopping")
        )

    def _request_instance_json(
        self,
        *,
        path: str,
        instance_id: str,
        payload: dict[str, object],
        timeout: float,
        legacy_payload: dict[str, object],
    ) -> VoiceJson:
        """Call one exact-ID lifecycle route with local-daemon compatibility.

        Args:
            path: Canonical daemon lifecycle endpoint.
            instance_id: Exact identity being routed.
            payload: Current ``instanceId`` request payload.
            timeout: HTTP transport cap for this request.
            legacy_payload: Compatibility payload for an older local daemon.

        Returns:
            VoiceJson: Daemon lifecycle response.

        Raises:
            HTTPError: If the daemon rejects the canonical or compatibility call.
            ValueError: If either request payload addresses another instance.
        """

        # Identity check: verify instance ID invariants
        if instance_id_from_payload(payload) != instance_id:
            raise ValueError("Canonical lifecycle payload addresses another instance.")

        # Identity check: verify instance ID invariants
        if instance_id_from_payload(legacy_payload) != instance_id:
            raise ValueError(
                "Compatibility lifecycle payload addresses another instance."
            )

        # Exception safety: execute operation within error boundary
        try:
            return self._request_json(
                path=path, method="POST", payload=payload, timeout=timeout
            )

        # HTTP error handling: process server response status
        except HTTPError as exc:
            # Conditional check: evaluate domain preconditions and invariants
            if exc.code != 400:
                raise

            return self._request_json(
                path=path,
                method="POST",
                payload=legacy_payload,
                timeout=timeout,
            )

    def audio(self, name: str | None = None) -> bytes | None:
        """Read the latest or a named in-memory audio payload.

        Args:
            name (str | None): Message identifier, or ``None`` for the latest.

        Returns:
            bytes | None: Audio bytes, or ``None`` when unavailable.
        """

        path = (
            "/audio/latest" if name is None else f"/audio/name/{quote(name, safe='')}"
        )

        # Exception safety: execute operation within error boundary
        try:
            # Context management: enter managed resource scope
            with urlopen(f"{VOICE_DAEMON_URL}{path}", timeout=1.0) as response:
                return response.read()

        # Failure recovery: handle execution or transport exception
        except (OSError, URLError):
            return None

    def _ensure_daemon(self) -> None:
        """Start the daemon once and wait only until its local socket is ready.

        Args:
            None.

        Returns:
            None: The daemon is healthy when this method returns.

        Raises:
            RuntimeError: If sandbox policy blocks startup or readiness fails.
        """

        # Health check: verify existing daemon availability before launch
        if self._is_healthy():
            return
        daemon_path = Path(__file__).with_name("daemon.py")

        # Conditional check: evaluate domain preconditions and invariants
        if runs_inside_codex_sandbox():
            raise RuntimeError(
                "The avatar service is not running. Start it once from the interactive user CLI with "
                "py '.\\$agent\\scripts\\brain.py' start-avatar-service --json. "
                "Brain will not create an invisible GUI inside the Codex sandbox desktop."
            )
        popen_kwargs: VoiceJson = {
            "cwd": str(daemon_path.parent),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }

        # Conditional check: evaluate domain preconditions and invariants
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NO_WINDOW
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
            )

        else:
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen([sys.executable, str(daemon_path)], **popen_kwargs)
        deadline = time.monotonic() + VOICE_DAEMON_STARTUP_TIMEOUT_SECONDS

        # Loop execution: process until boundary condition is satisfied
        while time.monotonic() < deadline:
            # Conditional check: evaluate domain preconditions and invariants
            if self._is_healthy():
                return

            # Conditional check: evaluate domain preconditions and invariants
            if process is not None and process.poll() is not None:
                raise RuntimeError(
                    f"Voice daemon exited during startup with code {process.returncode}."
                )

            time.sleep(0.025)

        raise RuntimeError("Voice daemon did not become ready.")

    def _is_healthy(self) -> bool:
        """Return whether the configured daemon answers for this core.

        Args:
            None.

        Returns:
            bool: Whether the daemon health response is valid.
        """

        # Exception safety: execute operation within error boundary
        try:
            payload = self._request_json(path="/health")
            remote_core_id = str(payload.get("coreId", ""))

            return bool(payload.get("ok")) and (
                not remote_core_id or remote_core_id == VOICE_CORE_ID
            )

        # Failure recovery: handle execution or transport exception
        except (OSError, URLError):
            return False

    @staticmethod
    def _request_json(
        path: str,
        method: str = "GET",
        payload: VoiceJson | None = None,
        timeout: float = VOICE_DAEMON_REQUEST_TIMEOUT_SECONDS,
    ) -> VoiceJson:
        """Send one bounded JSON request to the local daemon.

        Args:
            path: Daemon route path.
            method: HTTP method.
            payload: Optional JSON object to encode as the request body.
            timeout: Transport timeout in seconds.

        Returns:
            VoiceJson: Decoded daemon JSON object.
        """

        data = (
            None

            # Conditional check: evaluate domain preconditions and invariants
            if payload is None
            else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        )
        request = Request(
            f"{VOICE_DAEMON_URL}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )

        # Context management: enter managed resource scope
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def _validated_instance_timeout(timeout_seconds: float) -> float:
    """Validate one total client-side instance wait duration.

    Args:
        timeout_seconds: Candidate total caller wait duration.

    Returns:
        float: Finite non-negative caller wait duration.

    Raises:
        ValueError: If the candidate is boolean, non-numeric, negative, or non-finite.
    """

    # Timeout check: verify bounded wait duration
    if isinstance(timeout_seconds, bool):
        raise ValueError("Instance wait timeout must be numeric.")

    # Exception safety: execute operation within error boundary
    try:
        validated_timeout = float(timeout_seconds)

    # Validation error handling: convert invalid input to domain exception
    except (TypeError, ValueError) as exc:
        raise ValueError("Instance wait timeout must be numeric.") from exc

    # Timeout check: verify bounded wait duration
    if not math.isfinite(validated_timeout) or validated_timeout < 0:
        raise ValueError("Instance wait timeout must be finite and non-negative.")

    return validated_timeout


def _bounded_instance_timeout(timeout_seconds: float) -> float:
    """Validate and cap one client-side instance wait segment.

    Args:
        timeout_seconds: Candidate daemon-side segment duration.

    Returns:
        float: Finite non-negative duration no greater than the public cap.

    Raises:
        ValueError: If the candidate is boolean, non-numeric, negative, or non-finite.
    """

    bounded_timeout = _validated_instance_timeout(timeout_seconds)

    return min(bounded_timeout, VOICE_INSTANCE_WAIT_TIMEOUT_SECONDS)
