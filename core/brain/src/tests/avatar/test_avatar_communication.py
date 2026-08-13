# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Unit coverage for avatar communication contracts and services.

Validates DTO data structures, idempotency UUID invariants, target serialization,
and application service routing between the avatar UI and communication ports.
"""

from __future__ import annotations

# Standard Libraries Imports
from dataclasses import dataclass, field
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Third-party Libraries Imports
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

# Application Modules Imports
from brain.presentation.avatar.communication.outbox.database import connect_communication_database
from brain.presentation.avatar.communication.app_server.gateway import CodexAppServerGateway
from brain.presentation.avatar.communication.app_server.transport import (
    CodexAppServerError,
    resolve_codex_executable,
)
from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    DeliveryMode,
    ReplyRequestDTO,
    ReplyResultDTO,
)
from brain.presentation.avatar.communication.outbox.message_store import AvatarMessageStore
from brain.presentation.avatar.communication.outbox.repository import AvatarOutboxRepository
from brain.presentation.avatar.communication.outbox.gateway import NativeOutboxGateway
from brain.presentation.avatar.communication.reply.service import AvatarReplyService
from brain.presentation.avatar.qt.runtime.window import (
    QtAvatarWindow,
    reply_composer_geometry,
)


THREAD_ID = "019f5dad-af67-7533-b394-8fb55258adb2"


@dataclass
class CodexReplyGatewayMock:
    """Record requests while returning deterministic accepted outcomes.

    Attributes:
        requests: Reply requests received by the mock gateway.
    """

    requests: list[ReplyRequestDTO] = field(default_factory=list)

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Record and accept one normalized request.

        Args:
            request_dto: Validated reply request sent through the service.

        Returns:
            ReplyResultDTO: Accepted result bound to the request instance.
        """
        self.requests.append(request_dto)

        return ReplyResultDTO(
            accepted=True,
            instance_id=request_dto.target.instance_id,
            thread_id=request_dto.target.thread_id,
            mode=request_dto.mode,
        )


@dataclass
class AppServerTransportMock:
    """Record JSON-RPC operations and optionally reject one active turn.

    Attributes:
        calls: Ordered JSON-RPC method and parameter pairs.
        reject_active_turn_once: Whether the next turn start should fail.
        active_turn_id: Active turn identifier returned by resume.
    """

    calls: list[tuple[str, dict]] = field(default_factory=list)
    reject_active_turn_once: bool = False
    active_turn_id: str = ""

    def request(self, method: str, params: dict) -> dict:
        """Record one JSON-RPC request and return its deterministic response.

        Args:
            method: JSON-RPC method requested by the App Server gateway.
            params: JSON-RPC parameters supplied with the request.

        Returns:
            dict: Simulated JSON-RPC response mapping.

        Raises:
            CodexAppServerError: If the configured active-turn rejection is consumed.
        """
        self.calls.append((method, params))

        if method == "thread/resume" and self.active_turn_id:
            return {
                "thread": {
                    "turns": [
                        {"id": "completed-turn", "status": "completed"},
                        {"id": self.active_turn_id, "status": "inProgress"},
                    ]
                }
            }

        if method == "turn/start" and self.reject_active_turn_once:
            self.reject_active_turn_once = False

            raise CodexAppServerError("active turn in progress")

        return {}

    def notify(self, method: str, params: dict) -> None:
        """Record one JSON-RPC notification without returning a response.

        Args:
            method: JSON-RPC notification method.
            params: JSON-RPC parameters supplied with the notification.

        Returns:
            None: The notification is appended to the call log.
        """
        self.calls.append((method, params))


def test_reply_service_delivers_typed_request_to_gateway() -> None:
    """Deliver a typed reply request through the application service.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate service delegation and instance identity.
    """
    gateway = CodexReplyGatewayMock()
    service = AvatarReplyService(gateway=gateway)
    target_dto = CodexThreadTargetDTO(
        instance_id="speak-1",
        thread_id=THREAD_ID,
        source_message_id="speak-1",
    )
    request_dto = ReplyRequestDTO(
        target=target_dto,
        text="Prioriza el daemon.",
        mode=DeliveryMode.STEER,
    )
    result_dto = service.send(request_dto=request_dto)
    assert result_dto.accepted is True
    assert result_dto.instance_id == target_dto.instance_id
    assert gateway.requests == [request_dto]


def test_reply_contract_rejects_invalid_target_and_blank_text() -> None:
    """Reject missing or blank message instance identities and blank replies.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate instance and reply text boundaries.

    Raises:
        AssertionError: If an invalid target or blank reply is accepted.
    """
    invalid_targets = ("", "   ")

    for instance_id in invalid_targets:
        try:
            CodexThreadTargetDTO(instance_id=instance_id)

        except ValueError as exc:
            assert "instance id is required" in str(exc).casefold()

        else:
            raise AssertionError("Invalid instance id was accepted.")

    target_dto = CodexThreadTargetDTO(instance_id="speak-validation")

    try:
        ReplyRequestDTO(target=target_dto, text="   ", mode=DeliveryMode.QUEUE)

    except ValueError as exc:
        assert "cannot be empty" in str(exc)

    else:
        raise AssertionError("Blank reply was accepted.")


def test_app_server_gateway_queues_until_the_active_turn_finishes() -> None:
    """Queue a reply until a transient active-turn conflict clears.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate retry ordering and accepted delivery.
    """
    transport = AppServerTransportMock(reject_active_turn_once=True)
    gateway = CodexAppServerGateway(
        transport,
        queue_timeout_seconds=0.1,
        retry_interval_seconds=0.01,
    )
    request_dto = ReplyRequestDTO(
        target=CodexThreadTargetDTO(instance_id="speak-queue", thread_id=THREAD_ID),
        text="Continúa con la validación.",
        mode=DeliveryMode.QUEUE,
    )
    assert gateway.send(request_dto).accepted is True
    assert [method for method, _params in transport.calls] == [
        "thread/resume",
        "turn/start",
        "turn/start",
    ]


def test_app_server_gateway_interrupts_before_starting_replacement_turn() -> None:
    """Interrupt an active turn before starting its replacement.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the interruption ordering.
    """
    transport = AppServerTransportMock()
    gateway = CodexAppServerGateway(transport)
    request_dto = ReplyRequestDTO(
        target=CodexThreadTargetDTO(instance_id="speak-interrupt", thread_id=THREAD_ID),
        text="Detén el enfoque anterior.",
        mode=DeliveryMode.INTERRUPT,
    )
    assert gateway.send(request_dto).accepted is True
    assert [method for method, _params in transport.calls] == [
        "thread/resume",
        "turn/interrupt",
        "turn/start",
    ]


def test_app_server_gateway_steers_with_the_active_turn_precondition() -> None:
    """Steer an active turn with the exact active-turn precondition.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the precondition sent to App Server.
    """
    transport = AppServerTransportMock(active_turn_id="turn-active-42")
    gateway = CodexAppServerGateway(transport)
    request_dto = ReplyRequestDTO(
        target=CodexThreadTargetDTO(instance_id="speak-steer", thread_id=THREAD_ID),
        text="Añade este detalle al turno actual.",
        mode=DeliveryMode.STEER,
    )
    assert gateway.send(request_dto).accepted is True
    assert [method for method, _params in transport.calls] == ["thread/resume", "turn/steer"]
    assert transport.calls[-1][1]["expectedTurnId"] == "turn-active-42"


def test_app_server_gateway_starts_when_send_now_has_no_active_turn() -> None:
    """Start a new turn when the resumed thread has no active turn.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the direct start sequence.
    """
    transport = AppServerTransportMock()
    gateway = CodexAppServerGateway(transport)
    request_dto = ReplyRequestDTO(
        target=CodexThreadTargetDTO(instance_id="speak-start", thread_id=THREAD_ID),
        text="Abre un turno nuevo.",
        mode=DeliveryMode.STEER,
    )
    assert gateway.send(request_dto).accepted is True
    assert [method for method, _params in transport.calls] == ["thread/resume", "turn/start"]


def test_qt_reply_composer_keeps_captured_target_during_new_speak() -> None:
    """Keep the first exact instance target when a newer message arrives.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate immutable target capture and display updates.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    avatar = QtAvatarWindow(start_polling=False)

    try:
        avatar._set_text("Primero", message_id="s1", codex_thread_id=THREAD_ID)
        avatar._open_reply_composer()
        avatar._set_text(
            "Segundo",
            message_id="s2",
            codex_thread_id="11111111-1111-1111-1111-111111111111",
        )
        assert avatar.reply_window.parent() is None
        assert avatar.reply_window.target is not None
        assert avatar.reply_window.target.instance_id == "s1"
        assert avatar.reply_window.target.thread_id == ""
        assert avatar.current_display_text == "Segundo"

    finally:
        avatar.close()


def test_explicit_codex_executable_is_validated_without_using_path() -> None:
    """Validate an explicit executable path without consulting PATH.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate configured and missing executable behavior.

    Raises:
        AssertionError: If a missing configured executable is accepted.
    """

    with TemporaryDirectory() as directory:
        executable = Path(directory) / "codex.exe"
        executable.touch()
        assert resolve_codex_executable(str(executable)) == str(executable)

    try:
        resolve_codex_executable(str(executable))

    except CodexAppServerError as exc:
        assert "CODEX_EXECUTABLE" in str(exc)

    else:
        raise AssertionError("Missing configured executable was accepted.")


def test_reply_composer_uses_frameless_translucent_avatar_chrome() -> None:
    """Preserve composer chrome, geometry, shortcut, and exact instance target.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the visual and interaction contract.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    avatar = QtAvatarWindow(start_polling=False)

    try:
        flags = avatar.reply_window.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint
        assert avatar.reply_window.testAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        assert avatar.reply_window.editor.font().family() == "Arial"
        assert avatar.reply_window.status_label.wordWrap() is True
        avatar._set_text("Mensaje", message_id="s1", codex_thread_id=THREAD_ID)
        avatar._open_reply_composer()
        assert avatar.reply_window.target is not None
        assert avatar.reply_window.target.instance_id == "s1"
        bubble_geometry = avatar.bubble.frameGeometry()
        bubble_center = bubble_geometry.center()
        screen = avatar.app.screenAt(bubble_center)

        if screen is None:
            screen = avatar.app.primaryScreen()

        expected_geometry = reply_composer_geometry(
            screen.availableGeometry(),
            bubble_geometry,
            avatar._bubble_is_above_avatar(),
        )
        assert avatar.reply_window.geometry() == expected_geometry
        assert avatar.reply_window.send_shortcut.key() == QKeySequence("Ctrl+Return")

    finally:
        avatar.close()


def test_accepted_external_reply_does_not_claim_native_visual_delivery() -> None:
    """Render a matching external response without claiming native delivery.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate success UI and exact result identity.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    avatar = QtAvatarWindow(start_polling=False)

    try:
        avatar._set_text("Mensaje", message_id="s1")
        avatar._open_reply_composer()
        avatar.reply_window._target = CodexThreadTargetDTO(instance_id="s1")
        avatar.reply_window._hold_pending = False
        avatar.reply_window.editor.setPlainText("Mensaje persistido")
        avatar.reply_window._terminal_action = "send"
        avatar.reply_window._hold_live = True
        result = ReplyResultDTO(
            accepted=True,
            mode=DeliveryMode.STEER,
            instance_id="s1",
            state="RESPONSED",
        )
        avatar.reply_window._delivery_finished(result)
        assert "respuesta enviada" in avatar.reply_window.status_label.text().casefold()
        assert "referencia encolada" not in avatar.reply_window.status_label.text().casefold()
        assert avatar.reply_window.editor.toPlainText() == ""
        assert avatar.reply_window.steer_button.isEnabled() is False

    finally:
        avatar.close()


def test_database_without_workspace_configuration_fails_before_cwd_write() -> None:
    """Reject unowned database access before writing beneath the current directory.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate configuration failure and filesystem safety.

    Raises:
        AssertionError: If missing workspace ownership is accepted.
    """

    with TemporaryDirectory() as directory:
        working_directory = Path(directory)
        contaminated_path = (
            working_directory / "$agent" / "database" / "avatar_communication.db"
        )
        previous_directory = Path.cwd()

        try:
            os.chdir(working_directory)

            with patch.dict(os.environ, {}, clear=True):
                try:
                    connect_communication_database()

                except RuntimeError as exc:
                    assert "WORKSPACE_ROOT" in str(exc)

                else:
                    raise AssertionError("Missing workspace ownership was accepted.")

        finally:
            os.chdir(previous_directory)

        assert contaminated_path.exists() is False


def test_native_outbox_claims_atomically_and_acknowledges_idempotently() -> None:
    """Claim one native outbox message atomically and acknowledge it idempotently.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate repository claim and acknowledgement behavior.
    """

    with TemporaryDirectory() as directory:
        repository = AvatarOutboxRepository(Path(directory))
        message_store = AvatarMessageStore(Path(directory))
        gateway = NativeOutboxGateway(message_store)
        request_dto = ReplyRequestDTO(
            target=CodexThreadTargetDTO(
                instance_id="speak-9",
                thread_id=THREAD_ID,
                source_message_id="speak-9",
            ),
            text="Mensaje por el canal nativo.",
            mode=DeliveryMode.STEER,
        )
        assert gateway.send(request_dto).accepted is True
        assert gateway.send(request_dto).accepted is True
        pending = repository.pending()
        assert len(pending) == 1
        assert pending[0].message_id == request_dto.idempotency_key
        assert set(pending[0].as_mapping()) == {
            "message_id",
            "thread_id",
            "host_id",
            "created_at",
        }
        claim_token, claimed = repository.claim()
        claimed_message_ids = [message.message_id for message in claimed]
        assert claimed_message_ids == [request_dto.idempotency_key]
        assert request_dto.text not in repr(claimed)
        other_token, competing_claim = repository.claim()
        assert other_token != claim_token
        assert competing_claim == []
        assert repository.acknowledge(request_dto.idempotency_key, other_token) is False
        assert repository.acknowledge(request_dto.idempotency_key, claim_token) is True
        assert repository.acknowledge(request_dto.idempotency_key, claim_token) is False
        assert repository.pending() == []


def test_native_outbox_can_release_a_claim_for_later_delivery() -> None:
    """Release a native outbox claim so the message can be delivered later.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate claim release and reclamation.
    """

    with TemporaryDirectory() as directory:
        repository = AvatarOutboxRepository(Path(directory))
        message_store = AvatarMessageStore(Path(directory))
        request_dto = ReplyRequestDTO(
            target=CodexThreadTargetDTO(
                instance_id="speak-10",
                thread_id=THREAD_ID,
                source_message_id="speak-10",
            ),
            text="Mensaje aplazado.",
            mode=DeliveryMode.QUEUE,
        )
        message_store.enqueue(request_dto)
        claim_token, claimed = repository.claim()
        assert len(claimed) == 1
        assert repository.release(request_dto.idempotency_key, "wrong-token") is False
        assert repository.release(request_dto.idempotency_key, claim_token) is True
        _, reclaimed = repository.claim()
        assert len(reclaimed) == 1


def test_consumer_resolves_body_by_reference_after_blind_bridge_delivery() -> None:
    """Resolve message content from storage after blind outbox delivery.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate reference-only outbox transport and storage reads.
    """

    with TemporaryDirectory() as directory:
        workspace_root = Path(directory)
        repository = AvatarOutboxRepository(workspace_root)
        message_store = AvatarMessageStore(workspace_root)
        request_dto = ReplyRequestDTO(
            target=CodexThreadTargetDTO(
                instance_id="speak-11",
                thread_id=THREAD_ID,
                source_message_id="speak-11",
            ),
            text="Contenido visible únicamente para el consumer.",
            mode=DeliveryMode.STEER,
        )
        message_store.enqueue(request_dto)
        claim_token, claimed = repository.claim()
        assert claimed[0].message_id == request_dto.idempotency_key
        assert request_dto.text not in repr(claimed[0].as_mapping())
        assert repository.acknowledge(request_dto.idempotency_key, claim_token) is True

        consumer_message = message_store.read(request_dto.idempotency_key)
        assert consumer_message is not None
        assert consumer_message.text == request_dto.text
        assert message_store.acknowledge_consumed(request_dto.idempotency_key) is True


def test_consumer_rejects_invalid_or_unknown_references() -> None:
    """Reject malformed message references and return no result for unknown IDs.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate consumer reference handling.

    Raises:
        AssertionError: If an invalid message reference is accepted.
    """

    with TemporaryDirectory() as directory:
        message_store = AvatarMessageStore(Path(directory))

        try:
            message_store.read("not-a-message-id")

        except ValueError as exc:
            assert "valid UUID" in str(exc)

        else:
            raise AssertionError("Invalid avatar message id was accepted.")

        unknown_message = message_store.read("11111111-1111-1111-1111-111111111111")
        assert unknown_message is None
