# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Unit coverage for avatar communication contracts and services."""

from __future__ import annotations

# Standard Libraries Imports
from dataclasses import dataclass, field
import os
from pathlib import Path
from tempfile import TemporaryDirectory

# Application Modules Imports
from brain.presentation.avatar.communication.models import (
    CodexThreadTargetDTO,
    DeliveryMode,
    ReplyRequestDTO,
    ReplyResultDTO,
)
from brain.presentation.avatar.communication.message_store import AvatarMessageStore
from brain.presentation.avatar.communication.outbox import AvatarOutboxRepository
from brain.presentation.avatar.communication.outbox_gateway import NativeOutboxGateway
from brain.presentation.avatar.communication.app_server_gateway import CodexAppServerGateway
from brain.presentation.avatar.communication.app_server_transport import CodexAppServerError, resolve_codex_executable
from brain.presentation.avatar.communication.service import AvatarReplyService


THREAD_ID = "019f5dad-af67-7533-b394-8fb55258adb2"


@dataclass
class CodexReplyGatewayMock:
    """Record requests while returning deterministic accepted outcomes."""

    requests: list[ReplyRequestDTO] = field(default_factory=list)

    def send(self, request_dto: ReplyRequestDTO) -> ReplyResultDTO:
        """Record and accept one normalized request."""
        self.requests.append(request_dto)
        return ReplyResultDTO(
            accepted=True,
            thread_id=request_dto.target.thread_id,
            mode=request_dto.mode,
        )


@dataclass
class AppServerTransportMock:
    """Record JSON-RPC operations and optionally reject one active turn."""

    calls: list[tuple[str, dict]] = field(default_factory=list)
    reject_active_turn_once: bool = False
    active_turn_id: str = ""

    def request(self, method: str, params: dict) -> dict:
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
        self.calls.append((method, params))


def test_reply_service_delivers_typed_request_to_gateway() -> None:
    gateway = CodexReplyGatewayMock()
    service = AvatarReplyService(gateway=gateway)
    target_dto = CodexThreadTargetDTO(thread_id=THREAD_ID, source_message_id="speak-1")
    request_dto = ReplyRequestDTO(target=target_dto, text="Prioriza el daemon.", mode=DeliveryMode.STEER)
    result_dto = service.send(request_dto=request_dto)
    assert result_dto.accepted is True
    assert gateway.requests == [request_dto]


def test_reply_contract_rejects_invalid_target_and_blank_text() -> None:
    try:
        CodexThreadTargetDTO(thread_id="not-a-thread")
    except ValueError as exc:
        assert "valid UUID" in str(exc)
    else:
        raise AssertionError("Invalid thread id was accepted.")

    target_dto = CodexThreadTargetDTO(thread_id=THREAD_ID)
    try:
        ReplyRequestDTO(target=target_dto, text="   ", mode=DeliveryMode.QUEUE)
    except ValueError as exc:
        assert "cannot be empty" in str(exc)
    else:
        raise AssertionError("Blank reply was accepted.")


def test_app_server_gateway_queues_until_the_active_turn_finishes() -> None:
    transport = AppServerTransportMock(reject_active_turn_once=True)
    gateway = CodexAppServerGateway(transport, queue_timeout_seconds=.1, retry_interval_seconds=.01)
    request_dto = ReplyRequestDTO(
        target=CodexThreadTargetDTO(thread_id=THREAD_ID),
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
    transport = AppServerTransportMock()
    gateway = CodexAppServerGateway(transport)
    request_dto = ReplyRequestDTO(
        target=CodexThreadTargetDTO(thread_id=THREAD_ID),
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
    transport = AppServerTransportMock(active_turn_id="turn-active-42")
    gateway = CodexAppServerGateway(transport)
    request_dto = ReplyRequestDTO(
        target=CodexThreadTargetDTO(thread_id=THREAD_ID),
        text="Añade este detalle al turno actual.",
        mode=DeliveryMode.STEER,
    )
    assert gateway.send(request_dto).accepted is True
    assert [method for method, _params in transport.calls] == ["thread/resume", "turn/steer"]
    assert transport.calls[-1][1]["expectedTurnId"] == "turn-active-42"


def test_app_server_gateway_starts_when_send_now_has_no_active_turn() -> None:
    transport = AppServerTransportMock()
    gateway = CodexAppServerGateway(transport)
    request_dto = ReplyRequestDTO(
        target=CodexThreadTargetDTO(thread_id=THREAD_ID),
        text="Abre un turno nuevo.",
        mode=DeliveryMode.STEER,
    )
    assert gateway.send(request_dto).accepted is True
    assert [method for method, _params in transport.calls] == ["thread/resume", "turn/start"]


def test_qt_reply_composer_keeps_captured_target_during_new_speak() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from brain.presentation.avatar.qt.window import QtAvatarWindow

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
        assert avatar.reply_window.target.thread_id == THREAD_ID
        assert avatar.current_display_text == "Segundo"
    finally:
        avatar.close()


def test_explicit_codex_executable_is_validated_without_using_path() -> None:
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
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    from brain.presentation.avatar.qt.window import QtAvatarWindow

    avatar = QtAvatarWindow(start_polling=False)
    try:
        flags = avatar.reply_window.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint
        assert avatar.reply_window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert avatar.reply_window.editor.font().family() == "Arial"
        assert avatar.reply_window.status_label.wordWrap() is True
        avatar._set_text("Mensaje", message_id="s1", codex_thread_id=THREAD_ID)
        avatar._open_reply_composer()
        assert THREAD_ID in avatar.reply_window.target_label.text()
        assert avatar.reply_window.geometry() == avatar.bubble.frameGeometry()
        assert avatar.reply_window.send_shortcut.key() == QKeySequence("Ctrl+Return")
    finally:
        avatar.close()


def test_accepted_external_reply_does_not_claim_native_visual_delivery() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from brain.presentation.avatar.communication.models import ReplyResultDTO
    from brain.presentation.avatar.qt.window import QtAvatarWindow

    avatar = QtAvatarWindow(start_polling=False)
    try:
        avatar.reply_window.editor.setPlainText("Mensaje persistido")
        result = ReplyResultDTO(accepted=True, thread_id=THREAD_ID, mode=DeliveryMode.STEER)
        avatar.reply_window._delivery_finished(result)
        assert "referencia encolada" in avatar.reply_window.status_label.text().casefold()
        assert "entregado" not in avatar.reply_window.status_label.text().casefold()
        assert avatar.reply_window.editor.toPlainText() == ""
        assert avatar.reply_window.interrupt_button.isEnabled() is False
    finally:
        avatar.close()


def test_native_outbox_claims_atomically_and_acknowledges_idempotently() -> None:
    with TemporaryDirectory() as directory:
        repository = AvatarOutboxRepository(Path(directory))
        message_store = AvatarMessageStore(Path(directory))
        gateway = NativeOutboxGateway(message_store)
        request_dto = ReplyRequestDTO(
            target=CodexThreadTargetDTO(thread_id=THREAD_ID, source_message_id="speak-9"),
            text="Mensaje por el canal nativo.",
            mode=DeliveryMode.STEER,
        )
        assert gateway.send(request_dto).accepted is True
        assert gateway.send(request_dto).accepted is True
        pending = repository.pending()
        assert len(pending) == 1
        assert pending[0].message_id == request_dto.idempotency_key
        assert set(pending[0].as_mapping()) == {"message_id", "thread_id", "host_id", "created_at"}
        claim_token, claimed = repository.claim()
        assert [message.message_id for message in claimed] == [request_dto.idempotency_key]
        assert request_dto.text not in repr(claimed)
        other_token, competing_claim = repository.claim()
        assert other_token != claim_token
        assert competing_claim == []
        assert repository.acknowledge(request_dto.idempotency_key, other_token) is False
        assert repository.acknowledge(request_dto.idempotency_key, claim_token) is True
        assert repository.acknowledge(request_dto.idempotency_key, claim_token) is False
        assert repository.pending() == []


def test_native_outbox_can_release_a_claim_for_later_delivery() -> None:
    with TemporaryDirectory() as directory:
        repository = AvatarOutboxRepository(Path(directory))
        message_store = AvatarMessageStore(Path(directory))
        request_dto = ReplyRequestDTO(
            target=CodexThreadTargetDTO(thread_id=THREAD_ID, source_message_id="speak-10"),
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
    with TemporaryDirectory() as directory:
        workspace_root = Path(directory)
        repository = AvatarOutboxRepository(workspace_root)
        message_store = AvatarMessageStore(workspace_root)
        request_dto = ReplyRequestDTO(
            target=CodexThreadTargetDTO(thread_id=THREAD_ID, source_message_id="speak-11"),
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
    with TemporaryDirectory() as directory:
        message_store = AvatarMessageStore(Path(directory))
        try:
            message_store.read("not-a-message-id")
        except ValueError as exc:
            assert "valid UUID" in str(exc)
        else:
            raise AssertionError("Invalid avatar message id was accepted.")
        assert message_store.read("11111111-1111-1111-1111-111111111111") is None
