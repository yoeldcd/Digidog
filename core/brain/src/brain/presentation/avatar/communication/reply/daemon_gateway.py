# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""HTTP gateway for exact daemon instance-bound reply terminalization.

Communicates with local daemon endpoints (/instance/hold, /instance/respond,
/instance/cancel) using exact speak instance identifiers. Provides bounded HTTP
transport calls to transition speaking instances into RESPONSED or CANCELED.
"""

from __future__ import annotations

# Standard Libraries Imports
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Application Modules Imports
from brain.infrastructure.voice.daemon.daemon_client import VOICE_DAEMON_URL
from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    DeliveryMode,
    ReplyRequestDTO,
    ReplyResultDTO,
    ReplyTerminalState,
)


class DaemonReplyGateway:
    """Terminalize exactly one daemon speak instance per user action.

    Attributes:
        _daemon_url (str): Base URL of the local voice daemon.
        _timeout (float): Maximum HTTP wait for one terminal request.
    """

    def __init__(
        self, daemon_url: str = VOICE_DAEMON_URL, timeout: float = 0.5
    ) -> None:
        """Initialize the gateway with a bounded local HTTP timeout.

        Args:
            daemon_url (str): Base URL of the local voice daemon.
            timeout (float): Maximum request duration in seconds.

        Returns:
            None: The gateway is ready for asynchronous controller use.
        """
        self._daemon_url = daemon_url.rstrip("/")
        self._timeout = max(0.1, float(timeout))

    def open(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Open a hold for the exact daemon instance captured by the composer.

        Args:
            target: Immutable message target captured when the composer opened.

        Returns:
            ReplyResultDTO: Hold acknowledgement or an identity-preserving failure.
        """

        return self._post_terminal(
            target=target,
            path="/instance/composer-open",
            expected_state=None,
            default_state="HELD",
            mode=DeliveryMode.STEER,
        )

    def hold(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Preserve a hold-oriented alias for opening the exact target.

        Args:
            target: Immutable message target captured when the composer opened.

        Returns:
            ReplyResultDTO: Hold acknowledgement or an identity-preserving failure.
        """

        return self.open(target)

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Submit response text to the exact captured daemon instance.

        Args:
            request_dto (ReplyRequestDTO): Reply containing the immutable target.

        Returns:
            ReplyResultDTO: ``RESPONSED`` acknowledgement or failure detail.
        """

        return self._post_terminal(
            target=request_dto.target,
            path="/instance/respond",
            expected_state=ReplyTerminalState.RESPONSED,
            response=request_dto.text,
            mode=request_dto.mode,
        )

    def cancel(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Cancel the exact captured daemon instance.

        Args:
            target (CodexThreadTargetDTO): Immutable target captured on open.

        Returns:
            ReplyResultDTO: ``CANCELED`` acknowledgement or failure detail.
        """

        return self._post_terminal(
            target=target,
            path="/instance/cancel",
            expected_state=ReplyTerminalState.CANCELED,
            mode=DeliveryMode.STEER,
        )

    def close(self, target: CodexThreadTargetDTO) -> ReplyResultDTO:
        """Close the exact composer, releasing or terminalizing its instance.

        Dispatches an instance close request to the voice daemon for the target ID,
        releasing the active composer hold or marking it cancelled.

        Args:
            target (CodexThreadTargetDTO): Target conversation identifier.

        Returns:
            ReplyResultDTO: Transport-independent result describing the outcome.
        """

        return self._post_terminal(
            target=target,
            path="/instance/composer-close",
            expected_state=None,
            accepted_states={
                ReplyTerminalState.RELEASED.value,
                ReplyTerminalState.CANCELED.value,
            },
            require_hold=False,
            mode=DeliveryMode.STEER,
        )

    def _post_terminal(
        self,
        target: CodexThreadTargetDTO,
        path: str,
        expected_state: ReplyTerminalState | None,
        response: str = "",
        mode: DeliveryMode = DeliveryMode.STEER,
        default_state: str = "",
        accepted_states: set[str] | frozenset[str] | None = None,
        require_hold: bool = True,
    ) -> ReplyResultDTO:
        """Post one terminal operation and validate its exact daemon result.

        Args:
            target (CodexThreadTargetDTO): Immutable instance-bound target.
            path (str): Exact daemon terminal route.
            expected_state (ReplyTerminalState | None): Terminal state required for
                acceptance, or ``None`` for a non-terminal hold acknowledgement.
            response (str): Response text for the respond route.
            mode (DeliveryMode): UI delivery mode retained in the result only.
            default_state (str): State used when a successful hold omits its state.
            accepted_states (set[str] | frozenset[str] | None): Set of permitted terminal states.
            require_hold (bool): Whether an active composer hold is required.

        Returns:
            ReplyResultDTO: Validated terminal result or bounded failure.
        """
        instance_id = target.instance_id

        # Identity check: verify instance ID invariants
        if not instance_id:
            return self._failure(target, "Daemon instance id is required.", mode=mode)

        payload: dict[str, str] = {"instanceId": instance_id}

        # Conditional check: evaluate domain preconditions and invariants
        if response:
            payload["response"] = response

        request = Request(
            f"{self._daemon_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        # Exception safety: execute operation within error boundary
        try:
            # Context management: enter managed resource scope
            with urlopen(request, timeout=self._timeout) as http_response:
                response_payload = json.loads(http_response.read().decode("utf-8"))

        # HTTP error handling: process server response status
        except HTTPError as exc:
            return self._http_failure(target, exc, mode=mode)

        # Failure recovery: handle execution or transport exception
        except Exception as exc:  # noqa: BLE001 - gateway failures are UI-visible outcomes.

            return self._failure(target, str(exc), mode=mode)

        # Type validation: verify parameter data type
        if not isinstance(response_payload, dict):
            return self._failure(
                target, "Daemon response must be a JSON object.", mode=mode
            )

        returned_instance_id = self._response_instance_id(response_payload)
        returned_state = str(response_payload.get("state", ""))
        error = str(response_payload.get("error", ""))

        # Conditional check: evaluate domain preconditions and invariants
        if not bool(response_payload.get("ok")):
            return self._failure(
                target,
                error or f"Daemon rejected {returned_state or 'the operation'}.",
                returned_state,
                mode,
            )

        # Identity check: verify instance ID invariants
        if returned_instance_id != instance_id:
            return self._failure(
                target,
                "Daemon returned a different instance id.",
                returned_state,
                mode,
            )

        # State guard: verify lifecycle status preconditions
        if expected_state is not None and returned_state != expected_state.value:
            return self._failure(
                target,
                f"Daemon returned unexpected state: {returned_state or 'empty'}.",
                returned_state,
                mode,
            )

        # State guard: verify lifecycle status preconditions
        if expected_state is None and require_hold:
            # Conditional check: evaluate domain preconditions and invariants
            if not bool(response_payload.get("held", True)):
                return self._failure(
                    target,
                    error or "Daemon did not open the composer hold.",
                    returned_state,
                    mode,
                )

            # State guard: verify component lifecycle state preconditions
            if not returned_state:
                returned_state = default_state

            # State guard: verify component lifecycle state preconditions
            if returned_state in {
                ReplyTerminalState.CANCELED.value,
                ReplyTerminalState.SPEAKED.value,
                ReplyTerminalState.RESPONSED.value,
            }:
                return self._failure(
                    target,
                    f"Daemon returned terminal state: {returned_state}.",
                    returned_state,
                    mode,
                )

        # State guard: verify component lifecycle state preconditions
        if accepted_states is not None and returned_state not in accepted_states:
            return self._failure(
                target,
                f"Daemon returned unexpected state: {returned_state or 'empty'}.",
                returned_state,
                mode,
            )

            # State guard: verify lifecycle status preconditions
            if not returned_state:
                returned_state = default_state

            # State guard: verify lifecycle status preconditions
            if returned_state in {
                ReplyTerminalState.CANCELED.value,
                ReplyTerminalState.SPEAKED.value,
                ReplyTerminalState.RESPONSED.value,
            }:
                return self._failure(
                    target,
                    f"Daemon returned terminal state: {returned_state}.",
                    returned_state,
                    mode,
                )

        return ReplyResultDTO(
            accepted=True,
            thread_id=target.thread_id,
            mode=mode,
            instance_id=returned_instance_id,
            state=returned_state,
            response=str(response_payload.get("response", "")),
        )

    @staticmethod
    def _failure(
        target: CodexThreadTargetDTO,
        error: str,
        state: str = "",
        mode: DeliveryMode = DeliveryMode.STEER,
    ) -> ReplyResultDTO:
        """Build a failure while retaining the target identity for UI matching.

        Args:
            target (CodexThreadTargetDTO): Target associated with the failure.
            error (str): Human-readable transport or protocol failure.
            state (str): Optional state returned by the daemon.
            mode (DeliveryMode): UI delivery mode retained in the result only.

        Returns:
            ReplyResultDTO: Rejected result that leaves editor input untouched.
        """

        return ReplyResultDTO(
            accepted=False,
            thread_id=target.thread_id,
            mode=mode,
            error=error,
            instance_id=target.instance_id,
            state=state,
        )

    @classmethod
    def _http_failure(
        cls,
        target: CodexThreadTargetDTO,
        error: HTTPError,
        mode: DeliveryMode,
    ) -> ReplyResultDTO:
        """Convert an HTTP rejection into an exact-ID result.

        Args:
            target: Immutable instance target associated with the request.
            error: HTTP rejection returned by the local daemon.
            mode: UI delivery mode retained in the result.

        Returns:
            ReplyResultDTO: Rejected result with any daemon state preserved.
        """

        # Exception safety: execute operation within error boundary
        try:
            payload = json.loads(error.read().decode("utf-8"))

        # Failure recovery: handle execution or transport exception
        except Exception:  # noqa: BLE001 - transport fallback must always work.
            payload = None

        # Type validation: verify parameter data type
        if not isinstance(payload, dict):
            return cls._failure(target, str(error.reason or error), mode=mode)

        returned_instance_id = cls._response_instance_id(payload)
        state = str(payload.get("state", ""))
        error_text = str(payload.get("error", ""))

        # Identity check: verify instance ID invariants
        if returned_instance_id and returned_instance_id != target.instance_id:
            error_text = "Daemon returned a different instance id."

        # Content check: validate message text payload
        if not error_text:
            error_text = f"Daemon rejected {state or 'the operation'}."

        return ReplyResultDTO(
            accepted=False,
            thread_id=target.thread_id,
            mode=mode,
            error=error_text,
            instance_id=target.instance_id,
            state=state,
            response=str(payload.get("response", "")),
        )

    @staticmethod
    def _response_instance_id(payload: dict[str, object]) -> str:
        """Read the canonical or legacy exact instance field from a payload.

        Args:
            payload: Daemon JSON object containing an instance identity.

        Returns:
            str: Instance identity, or an empty string when absent.
        """

        # Iteration: process speak instances sequentially
        for field in ("instanceId", "speakId"):
            value = payload.get(field)

            # Type validation: verify parameter data type
            if isinstance(value, str) and value:
                return value

        return ""

    @staticmethod
    def _http_error(error: HTTPError) -> str:
        """Extract a useful daemon error without allowing body parsing to fail.

        Args:
            error (HTTPError): HTTP failure raised by the local daemon request.

        Returns:
            str: Daemon-provided error text or the HTTP reason.
        """

        # Exception safety: execute operation within error boundary
        try:
            payload = json.loads(error.read().decode("utf-8"))

        # Failure recovery: handle execution or transport exception
        except Exception:  # noqa: BLE001 - fallback must always be available.
            payload = None

        # Type validation: verify parameter data type
        if isinstance(payload, dict) and payload.get("error"):
            return str(payload["error"])

        return str(error.reason or error)
