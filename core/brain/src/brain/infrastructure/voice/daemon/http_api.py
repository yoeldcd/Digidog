# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""HTTP request adaptation for the local voice daemon.

Exposes REST endpoints for speech enqueueing, status reporting, instance
waiting, response submission, and theme toggling. Coordinates HTTP requests
with the underlying runtime state and memory models.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import TypeAlias
from urllib.parse import unquote

from brain.infrastructure.voice.contracts.instance_results import (
    ComposerCloseResult,
    InstanceTerminalResult,
)
from brain.infrastructure.voice.messaging.message_queue import bounded_prelude_seconds

HttpPayload: TypeAlias = dict[str, object]
"""Mutable JSON-compatible payload exchanged with local daemon clients."""

MemoryProvider: TypeAlias = Callable[[], object]
"""Composition-root callable that returns the daemon runtime boundary."""

ReplayCallback: TypeAlias = Callable[[str | None, str | None], bool]
"""Callback that accepts optional retained-message selectors for replay."""


class VoiceHttpHandler(BaseHTTPRequestHandler):
    """Adapt local HTTP requests to the composed voice-runtime boundary.

    Attributes:
        memory_provider: Composition-root callable returning the daemon runtime.
        replay_callback: Callback that queues a selected retained message.
        core_runtime_id: Stable runtime identity exposed by the health route.
        idle_ttl_seconds: Idle shutdown duration exposed by the health route.
    """

    memory_provider: MemoryProvider = staticmethod(lambda: None)
    replay_callback: ReplayCallback = staticmethod(
        lambda name=None, speak_id=None: False
    )
    core_runtime_id = ""
    idle_ttl_seconds = 0

    @property
    def memory(self) -> object:
        """Return the composition-root supplied runtime.

        Args:

            None.

        Returns:

            object: Runtime object configured by the daemon composition root.
        """

        return self.memory_provider()

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default HTTP request logging from the local daemon.

        Args:

            format: Base HTTP server format string.
            *args: Format values supplied by the HTTP server.

        Returns:

            None: The local daemon intentionally emits no request log.
        """

        return

    def do_GET(self) -> None:
        """Serve daemon health, status, message metadata, or audio resources.

        Args:

            None.

        Returns:

            None: The response is written to the HTTP connection.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/health":
            self._send_json(
                {
                    "ok": True,
                    "coreId": self.core_runtime_id,
                    "ttlSeconds": self.idle_ttl_seconds,
                }
            )

            return

        # State guard: verify lifecycle status preconditions
        if self.path == "/status":
            self._send_json(self.memory.status())

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/messages":
            self._send_json({"ok": True, **self.memory.snapshot()})

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/audio/latest":
            self._send_audio(self.memory.find_audio())

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path.startswith("/audio/name/"):
            self._send_audio(
                self.memory.find_audio(unquote(self.path.removeprefix("/audio/name/")))
            )

            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        """Handle local daemon lifecycle, queue, and presentation commands.

        Args:

            None.

        Returns:

            None: The response is written to the HTTP connection.
        """

        self.memory.touch()

        # Conditional check: evaluate domain preconditions and invariants
        if self.path in {
            "/instance/wait",
            "/instance/respond",
            "/instance/cancel",
            "/instance/composer-open",
            "/instance/composer-close",
        }:
            self._handle_instance_route()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/stop":
            self._handle_stop_route()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/window-ready":
            self._handle_window_ready()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path in {
            "/playback-started",
            "/playback-preparing",
            "/playback-duration",
        }:
            self._handle_playback_callback()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/stop-current-message":
            self._handle_stop_current_message()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/dismiss":
            self._handle_dismiss()

            return

        # Compatibility only: the former route is intentionally terminal STOP.
        # No paused state, retained position, or resume operation exists.

        if self.path == "/pause":
            self._handle_pause()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/mute":
            self._handle_mute()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/replay":
            self._handle_replay()

            return

        # State guard: verify lifecycle status preconditions
        if self.path == "/ambient-state":
            self._handle_ambient_state()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/theme":
            self._handle_theme()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/narrate-active-file":
            self._handle_narrate_active_file()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/cancel-processing":
            self._handle_cancel_processing()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if self.path != "/speak":
            self.send_error(HTTPStatus.NOT_FOUND)

            return

        self._handle_speak()

    def _handle_stop_route(self) -> None:
        """Stop playback, request daemon shutdown, and acknowledge the request.

        Args:

            None.

        Returns:

            None: The accepted shutdown response is written to the connection.
        """

        self.memory.stop_playback()
        self.memory.request_daemon_stop()
        self._send_json({"ok": True, "stopping": True}, status=HTTPStatus.ACCEPTED)

    def _handle_window_ready(self) -> None:
        """Validate the optional window PID and publish its readiness state.

        Args:

            None.

        Returns:

            None: The readiness response is written to the connection.
        """

        length = min(int(self.headers.get("Content-Length", "0")), 1_000)
        payload = (
            json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        )

        # Exception safety: execute operation within error boundary
        try:
            pid = int(payload.get("pid"))

        # Validation error handling: convert invalid input to domain exception
        except (TypeError, ValueError):
            pid = None

        accepted = self.memory.mark_window_ready(pid)
        self._send_json(
            {"ok": accepted, "windowReady": accepted, "pid": pid},
            status=HTTPStatus.OK if accepted else HTTPStatus.CONFLICT,
        )

    def _handle_playback_callback(self) -> None:
        """Apply one generation-bound playback callback and report its state.

        Args:

            None.

        Returns:

            None: The callback response is written to the connection.
        """

        length = min(int(self.headers.get("Content-Length", "0")), 1_000)
        payload = (
            json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        )
        speak_id = str(payload.get("speakId", ""))

        # Exception safety: execute operation within error boundary
        try:
            generation = int(payload.get("generation", -1))

        # Validation error handling: convert invalid input to domain exception
        except (TypeError, ValueError):
            generation = -1

        # Conditional check: evaluate domain preconditions and invariants
        if self.path == "/playback-started":
            accepted = self.memory.mark_playback_started_for(speak_id, generation)

        # Conditional check: evaluate domain preconditions and invariants
        elif self.path == "/playback-preparing":
            accepted = self.memory.begin_playback_prelude_for(speak_id, generation)

        else:
            # Exception safety: execute operation within error boundary
            try:
                milliseconds = int(payload.get("milliseconds", 0))

            # Validation error handling: convert invalid input to domain exception
            except (TypeError, ValueError):
                milliseconds = 0

            accepted = self.memory.set_playback_duration_for(
                speak_id, generation, milliseconds
            )

        self._send_json(
            {"ok": accepted, "state": self.memory.status()["state"]},
            status=HTTPStatus.OK if accepted else HTTPStatus.CONFLICT,
        )

    def _handle_stop_current_message(self) -> None:
        """Stop the active speak item and return its terminal identity.

        Args:

            None.

        Returns:

            None: The stop response is written to the connection.
        """

        speak_id = self.memory.stop_active_speak()
        self._send_json(
            {
                "ok": speak_id is not None,
                "stopped": speak_id is not None,
                "speakId": speak_id,
            },
            status=HTTPStatus.ACCEPTED if speak_id else HTTPStatus.NOT_FOUND,
        )

    def _handle_dismiss(self) -> None:
        """Dismiss active speech, falling back to playback cleanup when idle.

        Args:

            None.

        Returns:

            None: The dismissal response is written to the connection.
        """

        speak_id = self.memory.stop_active_speak()

        # Identity check: verify instance ID invariants
        if speak_id is None:
            self.memory.stop_playback()

        self._send_json(
            {
                "ok": speak_id is not None,
                "dismissed": speak_id is not None,
                "speakId": speak_id,
            },
            status=HTTPStatus.ACCEPTED if speak_id else HTTPStatus.NOT_FOUND,
        )

    def _handle_pause(self) -> None:
        """Preserve the compatibility route's terminal-stop behavior.

        Args:

            None.

        Returns:

            None: The compatibility response is written to the connection.
        """

        speak_id = self.memory.stop_active_speak()
        self._send_json(
            {
                "ok": speak_id is not None,
                "stopped": speak_id is not None,
                "speakId": speak_id,
            },
            status=HTTPStatus.ACCEPTED if speak_id else HTTPStatus.NOT_FOUND,
        )

    def _handle_mute(self) -> None:
        """Cycle mute mode and return its current presentation state.

        Args:

            None.

        Returns:

            None: The mute response is written to the connection.
        """

        mute_mode = self.memory.toggle_muted()
        self._send_json(
            {"ok": True, "muted": mute_mode != "off", "muteMode": mute_mode}
        )

    def _handle_replay(self) -> None:
        """Queue a selected retained message for replay.

        Args:

            None.

        Returns:

            None: The replay response is written to the connection.
        """

        length = min(int(self.headers.get("Content-Length", "0")), 4_000)
        payload = (
            json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        )
        message_name = str(payload.get("name", "")).strip() or None
        speak_id = str(payload.get("speakId", "")).strip() or None
        replayable = self.replay_callback(name=message_name, speak_id=speak_id)
        self._send_json(
            {"ok": replayable, "replaying": replayable, "queued": replayable},
            status=HTTPStatus.ACCEPTED if replayable else HTTPStatus.NOT_FOUND,
        )

    def _handle_ambient_state(self) -> None:
        """Update ambient state and map invalid state values to bad requests.

        Args:

            None.

        Returns:

            None: The ambient-state response is written to the connection.
        """

        length = min(int(self.headers.get("Content-Length", "0")), 4_000)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))

        # Exception safety: execute operation within error boundary
        try:
            state = self.memory.set_ambient_state(str(payload.get("state", "")))

        # Validation error handling: convert invalid input to domain exception
        except ValueError as exc:
            self._send_json(
                {"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST
            )

            return

        self._send_json(
            {"ok": True, "state": state, "ambientState": self.memory.ambient_state}
        )

    def _handle_theme(self) -> None:
        """Update theme mode and map invalid modes to bad requests.

        Args:

            None.

        Returns:

            None: The theme response is written to the connection.
        """

        length = min(int(self.headers.get("Content-Length", "0")), 1_000)
        payload = (
            json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        )

        # Exception safety: execute operation within error boundary
        try:
            mode = self.memory.set_theme_mode(str(payload.get("mode", "")))

        # Validation error handling: convert invalid input to domain exception
        except ValueError as exc:
            self._send_json(
                {"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST
            )

            return

        self._send_json({"ok": True, "themeMode": mode})

    def _handle_narrate_active_file(self) -> None:
        """Queue active embedded-file narration and return its speak identity.

        Args:

            None.

        Returns:

            None: The narration response is written to the connection.
        """

        speak_id = self.memory.enqueue_active_file_narration()
        self._send_json(
            {
                "ok": speak_id is not None,
                "queued": speak_id is not None,
                "speakId": speak_id,
            },
            status=HTTPStatus.ACCEPTED if speak_id else HTTPStatus.NOT_FOUND,
        )

    def _handle_cancel_processing(self) -> None:
        """Cancel queued processing and report the number of canceled items.

        Args:

            None.

        Returns:

            None: The cancellation response is written to the connection.
        """

        cancelled = self.memory.cancel_processing()
        self._send_json({"ok": True, "cancelled": cancelled})

    def _handle_speak(self) -> None:
        """Decode one speech request, enqueue it, and acknowledge its identity.

        Args:

            None.

        Returns:

            None: The enqueue response is written to the connection.
        """

        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        speak_id = self.memory.enqueue(
            text=str(payload.get("text", "")),
            display_text=str(payload.get("displayText", "")),
            lang=str(payload.get("lang", "es")),
            emotion=str(payload.get("emotion", "")),
            signal_key=str(payload.get("signalKey", "")),
            prelude_seconds=bounded_prelude_seconds(payload.get("preludeSeconds", 0)),
            consumer_path=str(payload.get("consumerPath", "")),
            codex_thread_id=str(payload.get("codexThreadId", "")),
            source_command=str(payload.get("sourceCommand", "")),
            source_phase=str(payload.get("sourcePhase", "")),
            keep_speaks_only=bool(payload.get("keepSpeaksOnly", False)),
            clear_queue_before=bool(payload.get("clearQueueBefore", False)),
            has_embedded_file=bool(payload.get("hasEmbeddedFile", False)),
            manual_speech=bool(payload.get("manualSpeech", False)),
            show_message=bool(payload.get("showMessage", True)),
            speak_message=bool(payload.get("speakMessage", True)),
            hide_when_muted=bool(payload.get("hideWhenMuted", False)),
            message_level=str(payload.get("messageLevel", "informative")),
            pre_processor=str(payload.get("preProcessor", "<default>")),
        )

        self._send_json(
            {"ok": True, "queued": speak_id is not None, "speakId": speak_id},
            status=HTTPStatus.ACCEPTED,
        )

    def _handle_instance_route(self) -> None:
        """Validate and dispatch one bounded per-instance lifecycle route.

        Args:

            None.

        Returns:

            None: A JSON response is written for the selected route.

        Raises:

            ValueError: Converted to a client-facing bad-request response.
        """

        # Exception safety: execute operation within error boundary
        try:
            payload = self._read_json_payload(maximum=4_000)

        # Validation error handling: convert invalid input to domain exception
        except ValueError as exc:
            self._send_json(
                {"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST
            )

            return

        # Exception safety: execute operation within error boundary
        try:

            # Identity extraction: resolve canonical instance ID from request payload
                instance_id = self._instance_id_from_payload(payload)

        # Validation error handling: convert invalid input to domain exception
        except ValueError as exc:
            self._send_json(
                {"ok": False, "error": str(exc)},
                status=HTTPStatus.BAD_REQUEST,
            )

            return

        # Identity check: verify instance ID invariants
        if instance_id is None:
            self._send_json(
                {"ok": False, "error": "instanceId is required."},
                status=HTTPStatus.BAD_REQUEST,
            )

            return

        is_wait_route = self.path == "/instance/wait"
        is_respond_route = self.path == "/instance/respond"
        is_composer_open_route = self.path == "/instance/composer-open"
        is_composer_close_route = self.path == "/instance/composer-close"

        # Exception safety: execute operation within error boundary
        try:
            # Conditional check: evaluate domain preconditions and invariants
            if is_wait_route:
                timeout = self._timeout_from_payload(payload)

                # Timeout check: verify bounded wait duration
                if timeout is None:
                    raise ValueError("timeout is required.")

                # Synchronization: wait for terminal result from runtime memory
                result = self.memory.wait_instance(instance_id, timeout)

                # Conditional check: evaluate domain preconditions and invariants
                if result is None:
                    hold_open = getattr(self.memory, "composer_hold_open", None)
                    held = bool(hold_open(instance_id)) if callable(hold_open) else False
                    self._send_json(
                        {
                            "ok": False,
                            "speakId": instance_id,
                            "state": "HELD" if held else "TIMEOUT",
                            "held": held,
                        },
                        status=HTTPStatus.REQUEST_TIMEOUT,
                    )

                    return
                self._send_json(self._instance_payload(result))

                return

            # Conditional check: evaluate domain preconditions and invariants
            if is_respond_route:
                response = payload.get("response")

                # Type validation: verify parameter data type
                if not isinstance(response, str) or not response.strip():
                    self._send_json(
                        {"ok": False, "error": "response is required."},
                        status=HTTPStatus.BAD_REQUEST,
                    )

                    return
                result = self.memory.respond_instance(instance_id, response)

                # Conditional check: evaluate domain preconditions and invariants
                if result is None:
                    self._send_stale_instance_response(instance_id)

                    return
                self._send_json(
                    self._instance_payload(result), status=HTTPStatus.ACCEPTED
                )

                return

            # Conditional check: evaluate domain preconditions and invariants
            if is_composer_open_route:
                accepted = self.memory.open_composer_hold(instance_id)
                response_payload = {
                    "ok": accepted,
                    "speakId": instance_id,
                    "held": accepted,
                }
                response_status = (
                    HTTPStatus.ACCEPTED if accepted else HTTPStatus.CONFLICT
                )
                self._send_json(response_payload, status=response_status)

                return

            if is_composer_close_route:
                close_result: ComposerCloseResult = self.memory.close_composer_hold(
                    instance_id
                )
                if close_result.terminal_result is not None:
                    self._send_stale_instance_response(instance_id)
                    return
                self._send_json(
                    {"ok": True, **close_result.to_payload()},
                    status=HTTPStatus.ACCEPTED,
                )
                return

            result = self.memory.cancel_instance(instance_id)

            # Conditional check: evaluate domain preconditions and invariants
            if result is None:
                self._send_stale_instance_response(instance_id)

                return
            self._send_json(self._instance_payload(result), status=HTTPStatus.ACCEPTED)

        # Key error handling: handle missing lookup entity
        except KeyError:
            self._send_json(
                {
                    "ok": False,
                    "speakId": instance_id,
                    "error": "Unknown or stale speakId.",
                },
                status=HTTPStatus.NOT_FOUND,
            )

        # Validation error handling: convert invalid input to domain exception
        except (TypeError, ValueError) as exc:
            self._send_json(
                {"ok": False, "speakId": instance_id, "error": str(exc)},
                status=HTTPStatus.BAD_REQUEST,
            )

    def _send_stale_instance_response(self, instance_id: str) -> None:
        """Report an unknown instance or a previously won terminal transition.

        Args:

            instance_id: Exact canonical identity whose operation was rejected.

        Returns:

            None: The appropriate not-found or conflict response is written.
        """

        # Exception safety: execute operation within error boundary
        try:
            result = self.memory.instance_lifecycle.result(instance_id)

        # Key error handling: handle missing lookup entity
        except KeyError:
            result = None

        # Conditional check: evaluate domain preconditions and invariants
        if result is None:
            self._send_json(
                {
                    "ok": False,
                    "speakId": instance_id,
                    "error": "Unknown or stale speakId.",
                },
                status=HTTPStatus.NOT_FOUND,
            )

            return

        self._send_json(
            self._instance_payload(result, ok=False),
            status=HTTPStatus.CONFLICT,
        )

    @staticmethod
    def _instance_id_from_payload(payload: HttpPayload) -> str | None:
        """Validate one exact identity from the supported instance fields.

        Args:

            payload: Decoded JSON object for an ``/instance/*`` request.

        Returns:

            str | None: Canonical identity, or ``None`` when absent.

        Raises:

            ValueError: If fields are malformed, padded, or contradictory.
        """
        identity_values = tuple(
            payload[field] for field in ("instanceId", "speakId") if field in payload
        )

        # Conditional check: evaluate domain preconditions and invariants
        if not identity_values:
            return None

        # Type validation: verify parameter data type
        if any(not isinstance(value, str) or not value for value in identity_values):
            raise ValueError("instanceId must be non-empty text.")

        canonical_values = tuple(
            value for value in identity_values if isinstance(value, str)
        )

        # Conditional check: evaluate domain preconditions and invariants
        if any(value != value.strip() for value in canonical_values):
            raise ValueError("instanceId must not have surrounding whitespace.")

        # Conditional check: evaluate domain preconditions and invariants
        if len(set(canonical_values)) != 1:
            raise ValueError("instanceId and speakId must identify the same instance.")

        return canonical_values[0]

    @staticmethod
    def _timeout_from_payload(payload: HttpPayload) -> float | None:
        """Resolve one bounded wait value from the supported timeout fields.

        Args:

            payload: Decoded JSON object for an ``/instance/wait`` request.

        Returns:

            float | None: Numeric timeout, or ``None`` when no timeout is given.

        Raises:

            ValueError: If timeout fields are boolean, non-numeric, or conflict.
        """
        timeout_values = tuple(
            payload[field]

            # Iteration: loop over collection elements
            for field in ("timeoutSeconds", "timeout")

            # Conditional check: evaluate domain preconditions and invariants
            if field in payload
        )

        # Timeout check: verify bounded wait duration
        if not timeout_values:
            return None

        # Timeout check: verify bounded wait duration
        if any(isinstance(value, bool) for value in timeout_values):
            raise ValueError("timeout must be numeric.")

        # Exception safety: execute operation within error boundary
        try:
            numeric_values = tuple(float(value) for value in timeout_values)

        # Validation error handling: convert invalid input to domain exception
        except (TypeError, ValueError) as exc:
            raise ValueError("timeout must be numeric.") from exc

        # Conditional check: evaluate domain preconditions and invariants
        if len(numeric_values) == 2 and numeric_values[0] != numeric_values[1]:
            raise ValueError("timeoutSeconds and timeout must match.")

        return numeric_values[0]

    def _read_json_payload(self, maximum: int) -> HttpPayload:
        """Read one bounded JSON object from the request body.

        Args:

            maximum: Maximum accepted request-body length in bytes.

        Returns:

            HttpPayload: Decoded JSON object, or an empty object for no body.

        Raises:

            ValueError: If the length, encoding, or JSON syntax is invalid.
        """

        # Exception safety: execute operation within error boundary
        try:
            length = int(self.headers.get("Content-Length", "0"))

        # Validation error handling: convert invalid input to domain exception
        except (TypeError, ValueError):
            raise ValueError("Content-Length must be an integer.")

        # Conditional check: evaluate domain preconditions and invariants
        if length < 0 or length > maximum:
            raise ValueError("Request payload is too large.")

        # Conditional check: evaluate domain preconditions and invariants
        if length == 0:
            return {}

        # Exception safety: execute operation within error boundary
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))

        # Failure recovery: handle execution or transport exception
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must be valid JSON.") from exc

        # Type validation: verify parameter data type
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")  # noqa: TRY004

        return payload

    @staticmethod
    def _instance_payload(
        result: InstanceTerminalResult, *, ok: bool = True
    ) -> HttpPayload:
        """Serialize one immutable lifecycle result for HTTP.

        Args:

            result: Terminal lifecycle result to expose.
            ok: Whether the enclosing operation succeeded.

        Returns:

            HttpPayload: JSON-compatible terminal result payload.
        """
        payload: HttpPayload = {
            "ok": ok,
            "speakId": result.instance_id,
            "state": result.state.value,
        }

        # State guard: verify lifecycle status preconditions
        if result.state.value == "RESPONSED":
            payload["response"] = result.response

        return payload

    def _send_json(
        self, payload: HttpPayload, status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        """Serialize and send one JSON response with its exact byte length.

        Args:

            payload: JSON-compatible response body.
            status: HTTP status code sent with the response.

        Returns:

            None: The serialized response is written to the HTTP connection.
        """

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_audio(self, audio: bytes | None) -> None:
        """Send audio bytes or preserve the existing missing-resource response.

        Args:

            audio: Encoded audio payload, or ``None`` when no resource exists.

        Returns:

            None: The audio or not-found response is written to the connection.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if audio is None:
            self.send_error(HTTPStatus.NOT_FOUND)

            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)
