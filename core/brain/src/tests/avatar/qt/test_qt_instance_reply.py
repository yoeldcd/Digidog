# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Offscreen Qt tests for immutable instance-bound reply lifecycle.

Verifies that Qt composer windows capture exact daemon instance IDs, handle
asynchronous reply submission and cancellation, apply theme styling, and prevent
unintended retargeting across concurrent messages.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt, QObject, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    DeliveryMode,
    ReplyResultDTO,
    ReplyTerminalState,
)
from brain.presentation.avatar.qt.avatar.geometry import reply_composer_geometry
from brain.presentation.avatar.qt.reply_window import QtReplyWindow
from brain.presentation.avatar.qt.bubble.facade import QtMarkdownBubble
from brain.presentation.avatar.qt.runtime.window import QtAvatarWindow


THREAD_ID = "019f5dad-af67-7533-b394-8fb55258adb2"


class ReplyControllerStub(QObject):
    """Record UI operations while exposing the controller signal contract."""

    deliveryFinished = Signal(object)
    composerOpened = Signal(object)

    def __init__(self) -> None:
        """Initialize QObject state and operation logs.

        Args:
            No external arguments are accepted; the stub owns its state.

        Returns:
            None: The signal and operation logs are ready for a test.
        """

        QObject.__init__(self)
        self.opens: list[CodexThreadTargetDTO] = []
        self.submissions: list[tuple[CodexThreadTargetDTO, str, DeliveryMode]] = []
        self.cancellations: list[CodexThreadTargetDTO] = []

    def open(self, target: CodexThreadTargetDTO) -> None:
        """Acknowledge one exact live hold for the composer.

        Args:
            target: Immutable instance-bound target.

        Returns:
            None: The dedicated open signal receives a hold acknowledgement.
        """

        self.opens.append(target)
        self.composerOpened.emit(
            ReplyResultDTO(
                accepted=True,
                thread_id=target.thread_id,
                mode=DeliveryMode.STEER,
                instance_id=target.instance_id,
                state="HELD",
            )
        )

    def submit(
        self, target: CodexThreadTargetDTO, text: str, mode: DeliveryMode
    ) -> None:
        """Record an asynchronous-style submission request.

        Args:
            target: Immutable instance-bound target.
            text: Reply text supplied by the editor.
            mode: Requested delivery mode.

        Returns:
            None: The request is recorded for assertions.
        """

        self.submissions.append((target, text, mode))

    def cancel(self, target: CodexThreadTargetDTO) -> None:
        """Record an asynchronous-style cancellation request.

        Args:
            target: Immutable instance-bound target.

        Returns:
            None: The request is recorded for assertions.
        """

        self.cancellations.append(target)

    def emit_result(self, result: ReplyResultDTO) -> None:
        """Emit one simulated worker result to the Qt window.

        Args:
            result: Delivery result emitted by the simulated worker.

        Returns:
            None: The result is emitted through the Qt signal.
        """

        self.deliveryFinished.emit(result)


class DeferredOpenReplyControllerStub(ReplyControllerStub):
    """Keep the open acknowledgement deferred to expose the initial UI state."""

    def open(self, target: CodexThreadTargetDTO) -> None:
        """Record an open request without acknowledging it immediately."""
        self.opens.append(target)


def make_target(instance_id: str, session_id: str = "") -> CodexThreadTargetDTO:
    """Build one immutable target for the offscreen composer.

    Args:
        instance_id: Exact daemon speak instance to capture.
        session_id: Optional metadata that must not affect routing.

    Returns:
        CodexThreadTargetDTO: Immutable composer target.
    """

    return CodexThreadTargetDTO(
        instance_id=instance_id,
        thread_id=THREAD_ID,
        source_message_id="daemon-process-id",
        session_id=session_id,
    )


def accepted_result(
    target: CodexThreadTargetDTO, state: ReplyTerminalState
) -> ReplyResultDTO:
    """Build one exact terminal result for a captured target.

    Args:
        target: Target whose immutable instance ID is echoed.
        state: Terminal state to simulate.

    Returns:
        ReplyResultDTO: Accepted terminal result for the target.
    """

    return ReplyResultDTO(
        accepted=True,
        thread_id=target.thread_id,
        mode=DeliveryMode.STEER,
        instance_id=target.instance_id,
        state=state.value,
    )


def test_qt_composer_captures_first_speak_id_and_ignores_newer_messages() -> None:
    """Keep a visible composer bound when the avatar projects a newer message.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate immutable target capture.
    """

    QApplication.instance() or QApplication([])
    avatar = QtAvatarWindow(start_polling=False)

    try:
        avatar._set_text(
            "Primero",
            message_id="speak-first",
            codex_thread_id="thread-first",
        )
        avatar._open_reply_composer()
        captured = avatar.reply_window.target

        avatar._set_text(
            "Segundo",
            message_id="speak-newer",
            codex_thread_id="thread-second",
        )
        avatar._open_reply_composer()

        assert captured is not None
        assert avatar.reply_window.target == captured
        assert avatar.reply_window.target.instance_id == "speak-first"
        assert avatar.reply_window.target.thread_id == ""
        assert avatar.current_message_id == "speak-newer"

    finally:
        avatar.close()


def test_qt_changing_codex_metadata_cannot_change_instance_target() -> None:
    """Keep one message target stable while its unrelated metadata changes.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate instance-only target stability.
    """

    QApplication.instance() or QApplication([])
    avatar = QtAvatarWindow(start_polling=False)

    try:
        avatar._set_text(
            "Mensaje inicial",
            message_id="speak-stable",
            codex_thread_id="metadata-before",
        )
        avatar._open_reply_composer()
        captured = avatar.reply_window.target

        avatar._set_text(
            "Mensaje actualizado",
            message_id="speak-stable",
            codex_thread_id="metadata-after",
        )
        avatar._open_reply_composer()

        assert captured is not None
        assert avatar.reply_window.target == captured
        assert avatar.reply_window.target.instance_id == "speak-stable"
        assert avatar.reply_window.target.thread_id == ""

    finally:
        avatar.close()


def test_qt_reply_availability_uses_message_instance_not_codex_metadata() -> None:
    """Enable replies for an instance with absent metadata and reject blank IDs.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the message-bound availability rule.
    """

    QApplication.instance() or QApplication([])
    avatar = QtAvatarWindow(start_polling=False)

    try:
        avatar._set_text("Sin metadata", message_id="speak-only")
        assert avatar.bubble.reply_button.isEnabled() is True

        avatar._set_text(
            "Con metadata",
            message_id="speak-present",
            codex_thread_id=THREAD_ID,
        )
        assert avatar.bubble.reply_button.isEnabled() is True

        avatar._set_text("Sin instancia", message_id="", codex_thread_id=THREAD_ID)
        assert avatar.bubble.reply_button.isEnabled() is False

    finally:
        avatar.close()


def test_qt_composer_target_uses_current_message_without_codex_metadata() -> None:
    """Open a composer from the active instance while metadata remains absent.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate target construction from only the message ID.
    """

    QApplication.instance() or QApplication([])
    avatar = QtAvatarWindow(start_polling=False)

    try:
        avatar.daemon_instance_id = "daemon-process-id"
        avatar._set_text("Instancia activa", message_id="speak-active")
        avatar._open_reply_composer()

        assert avatar.reply_window.target is not None
        assert avatar.reply_window.target.instance_id == "speak-active"
        assert avatar.reply_window.target.instance_id != avatar.daemon_instance_id
        assert avatar.reply_window.target.thread_id == ""
        assert avatar.reply_window.target.session_id == ""
        assert avatar.reply_window.target.source_message_id == ""

    finally:
        avatar.close()


def test_qt_submit_is_one_shot_until_exact_response_terminal_result() -> None:
    """Disable duplicate submits and accept only the exact terminal ID.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate one-shot terminal submission.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    target = make_target("speak-submit")

    try:
        window.open_for(target)
        window.editor.setPlainText("Mensaje de respuesta")
        window._submit(DeliveryMode.STEER)
        window._submit(DeliveryMode.STEER)

        assert controller.opens == [target]
        assert len(controller.submissions) == 1
        assert controller.submissions[0][0].instance_id == "speak-submit"
        assert window.steer_button.isEnabled() is False
        assert window.editor.toPlainText() == "Mensaje de respuesta"

        controller.emit_result(accepted_result(target, ReplyTerminalState.RESPONSED))

        assert window.editor.toPlainText() == ""
        assert window.steer_button.isEnabled() is False
        assert window._terminal_state == ReplyTerminalState.RESPONSED.value
        assert window.isVisible() is False

    finally:
        window.close()



def test_qt_reply_actions_stay_enabled_while_open_ack_is_pending() -> None:
    """Keep the messaging controls visually active during asynchronous opening."""

    QApplication.instance() or QApplication([])
    controller = DeferredOpenReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    target = make_target("speak-open-pending")
    actions = (
        window.screenshot_button,
        window.yes_button,
        window.not_button,
        window.steer_button,
    )

    try:
        window.open_for(target)

        assert controller.opens == [target]
        assert window._hold_pending is True
        assert window._hold_live is False
        assert all(action.isEnabled() for action in actions)

        window.editor.setPlainText("No enviar antes del hold")
        window._submit(DeliveryMode.STEER)
        assert controller.submissions == []

        controller.composerOpened.emit(
            ReplyResultDTO(
                accepted=True,
                thread_id=target.thread_id,
                mode=DeliveryMode.STEER,
                instance_id=target.instance_id,
                state="HELD",
            )
        )
        assert window._hold_pending is False
        assert window._hold_live is True
        assert all(action.isEnabled() for action in actions)

    finally:
        window.close()


def test_qt_bubble_reply_click_ignores_synchronous_reentrant_click() -> None:
    """Emit one reply request when a same-event click re-enters the button."""

    QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    requests: list[None] = []

    def record_request() -> None:
        requests.append(None)
        if len(requests) == 1:
            bubble.reply_button.click()

    bubble.replyRequested.connect(record_request)

    try:
        bubble.set_reply_available(True)
        bubble.reply_button.click()

        assert requests == [None]

    finally:
        bubble.close()


def test_qt_reply_open_is_idempotent_during_same_instance_reentry() -> None:
    """Open one composer request when the target callback re-enters opening."""

    QApplication.instance() or QApplication([])
    avatar = QtAvatarWindow(start_polling=False)
    target_calls: list[CodexThreadTargetDTO] = []

    class ReentrantReplyWindowStub:
        """Capture one open request and synchronously re-enter the avatar."""

        def safe_minimum_size(self, _available: QRect) -> QSize:
            return QSize(320, 92)

        def open_for(
            self,
            target: CodexThreadTargetDTO,
            _geometry: QRect | None = None,
        ) -> None:
            target_calls.append(target)
            if len(target_calls) == 1:
                avatar._open_reply_composer()

        def close(self) -> None:
            """Satisfy the avatar cleanup contract for the replacement stub."""

    try:
        avatar.current_message_id = "speak-reentrant"
        avatar.reply_window = ReentrantReplyWindowStub()  # type: ignore[assignment]
        avatar._open_reply_composer()

        assert target_calls == [CodexThreadTargetDTO(instance_id="speak-reentrant")]

    finally:
        avatar.close()


def test_qt_first_reply_open_matches_custom_bubble_frame_anchor() -> None:
    """Match the custom bubble frame on the first automatic reply opening."""
    app = QApplication.instance() or QApplication([])
    avatar = QtAvatarWindow(start_polling=False)
    original_reply_window = avatar.reply_window
    controller = ReplyControllerStub()
    reply_window = QtReplyWindow(controller)  # type: ignore[arg-type]
    screen = app.primaryScreen().availableGeometry()
    avatar_geometry = QRect(screen.right() - 149, screen.bottom() - 199, 150, 200)
    bubble_geometry = QRect(
        screen.left() + 40,
        avatar_geometry.top() - 133,
        screen.width() - 40,
        260,
    )

    try:
        original_reply_window.close()
        avatar.reply_window = reply_window
        avatar.setGeometry(avatar_geometry)
        avatar.bubble.setGeometry(bubble_geometry)
        avatar.bubble.show()
        app.processEvents()
        assert avatar.bubble.frameGeometry() == bubble_geometry

        avatar.current_message_id = "speak-custom-bubble"
        avatar._open_reply_composer()
        app.processEvents()

        expected = reply_composer_geometry(
            screen,
            bubble_geometry,
            avatar._bubble_is_above_avatar(),
            minimum_size=reply_window.safe_minimum_size(screen),
            avatar=avatar.frameGeometry(),
            horizontal_margin=0,
        )
        actual = reply_window.frameGeometry()

        assert actual.left() == bubble_geometry.left()
        assert actual.width() == bubble_geometry.width()
        assert actual.top() == expected.top()
        assert actual.top() == avatar_geometry.top() - bubble_geometry.height()
        assert screen.contains(actual)
        assert not actual.intersects(avatar.frameGeometry())

    finally:
        avatar.close()


def test_qt_response_terminal_can_reopen_same_and_historical_targets() -> None:
    """Reopen a responded target as a fresh actionable composer session.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate reset state, exact routing, and a second submit.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    target = make_target("speak-reopen")
    historical_target = make_target("speak-history")
    actions = (
        window.screenshot_button,
        window.yes_button,
        window.not_button,
        window.steer_button,
    )

    try:
        window.open_for(target)
        window.editor.setPlainText("Primer mensaje")
        window._submit(DeliveryMode.STEER)
        controller.emit_result(accepted_result(target, ReplyTerminalState.RESPONSED))

        assert window._terminal_state == ReplyTerminalState.RESPONSED.value
        assert all(action.isEnabled() is False for action in actions)
        assert window.isVisible() is False

        window.open_for(target)

        assert controller.opens == [target, target]
        assert window.target == target
        assert window._hold_pending is False
        assert window._hold_live is True
        assert window._terminal_action_pending is False
        assert window._terminal_action == ""
        assert window._terminal_state == ""
        assert window.status_label.text() == ""
        assert "color: #765568" in window.status_label.styleSheet()
        assert window.editor.toPlainText() == ""
        assert all(action.isEnabled() is True for action in actions)

        window.editor.setPlainText("Segundo mensaje")
        window._submit(DeliveryMode.STEER)
        assert controller.submissions == [
            (target, "Primer mensaje", DeliveryMode.STEER),
            (target, "Segundo mensaje", DeliveryMode.STEER),
        ]
        controller.emit_result(accepted_result(target, ReplyTerminalState.RESPONSED))

        window.open_for(historical_target)

        assert controller.opens == [target, target, historical_target]
        assert window.target == historical_target
        assert all(action.isEnabled() is True for action in actions)
        window.editor.setPlainText("Mensaje historico")
        window._submit(DeliveryMode.STEER)
        assert controller.submissions[-1] == (
            historical_target,
            "Mensaje historico",
            DeliveryMode.STEER,
        )

    finally:
        window.close()


def test_qt_reply_footer_has_four_equal_iconified_actions_and_valid_minimum() -> None:
    """Expose four equal footer actions with accessible labels and themed chrome.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the footer contract and minimum geometry.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    buttons = (
        window.screenshot_button,
        window.yes_button,
        window.not_button,
        window.steer_button,
    )

    try:
        assert [button.text() for button in buttons] == [
            "📷 SCREENSHOT",
            "✅ YES",
            "❌ NOT",
            "💭 ENVIAR",
        ]
        assert [button.accessibleName() for button in buttons] == [
            "SCREENSHOT",
            "YES",
            "NOT",
            "ENVIAR",
        ]
        assert all(button.toolTip() for button in buttons)
        assert [window.actions_layout.stretch(index) for index in range(4)] == [
            1,
            1,
            1,
            1,
        ]

        window.set_theme("dark")
        assert window.property("avatarTheme") == "dark"
        assert all("QPushButton" in button.styleSheet() for button in buttons)

        window.resize(720, 260)
        window.show()
        QApplication.processEvents()

        assert len({button.width() for button in buttons}) == 1
        assert window.minimumWidth() >= window._chrome_minimum_size.width()
        assert window.minimumHeight() >= window._chrome_minimum_size.height()

        window.resize(window.minimumSize())
        QApplication.processEvents()

        footer = window.actions_footer.geometry()
        footer_local = window.actions_footer.rect()
        assert window.height() - footer.bottom() >= 8
        assert all(footer_local.contains(button.geometry()) for button in buttons)
        footer_center = footer_local.center().y()
        assert all(
            abs(button.geometry().center().y() - footer_center) <= 1
            for button in buttons
        )
        assert footer.top() - window.editor.geometry().bottom() <= 4

    finally:
        window.close()


def test_qt_yes_and_not_submit_fixed_steer_replies_once_per_target() -> None:
    """Route YES and NOT literals through one exact terminal submit lifecycle.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate literal content, target identity, and one-shot state.
    """

    QApplication.instance() or QApplication([])

    for button_name, expected_text in (("yes_button", "Yes"), ("not_button", "No")):
        controller = ReplyControllerStub()
        window = QtReplyWindow(controller)  # type: ignore[arg-type]
        target = make_target(f"speak-fast-{expected_text.lower()}")

        try:
            window.open_for(target)
            window.editor.setPlainText("Editor content must be ignored")
            assert window._mark_clipboard_attachment(target) is True
            button = getattr(window, button_name)

            button.click()
            button.click()

            assert controller.submissions == [(target, expected_text, DeliveryMode.STEER)]
            assert window.editor.toPlainText() == "Editor content must be ignored"
            assert all(
                not action.isEnabled()
                for action in (
                    window.screenshot_button,
                    window.yes_button,
                    window.not_button,
                    window.steer_button,
                )
            )

            controller.emit_result(accepted_result(target, ReplyTerminalState.RESPONSED))

            assert window._terminal_state == ReplyTerminalState.RESPONSED.value
            assert window._clipboard_attachment_instance_id is None
            assert window.isVisible() is False

        finally:
            window.close()


def test_qt_screenshot_action_emits_only_its_signal_entry_point() -> None:
    """Emit a screenshot request without submitting or terminalizing the reply.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate the signal-only screenshot boundary.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    target = make_target("speak-screenshot")
    requests: list[CodexThreadTargetDTO | None] = []

    def record_request() -> None:
        """Record the active target observed by the screenshot signal.

        Args:
            No external arguments are accepted; Qt invokes the callback.

        Returns:
            None: The current target is appended to the local observation list.
        """

        requests.append(window.target)

    window.screenshotRequested.connect(record_request)

    try:
        window._screenshot_requested()
        assert requests == []

        window.open_for(target)
        window.editor.setPlainText("Keep this editor content")
        window.screenshot_button.click()

        assert requests == [target]
        assert controller.submissions == []
        assert window._terminal_action_pending is False
        assert window._terminal_state == ""
        assert window._hold_live is True
        assert window.editor.toPlainText() == "Keep this editor content"

    finally:
        window.close()


def test_qt_clipboard_attachment_clears_when_target_instance_changes() -> None:
    """Clear a saved screenshot marker when the composer binds a new target.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate target-bound hidden state isolation.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    first_target = make_target("speak-attachment-old")
    next_target = make_target("speak-attachment-new")

    try:
        window.open_for(first_target)
        assert window._mark_clipboard_attachment(first_target) is True
        assert window._clipboard_attachment_instance_id == first_target.instance_id

        window.hide()
        window.open_for(next_target)

        assert window.target == next_target
        assert window._clipboard_attachment_instance_id is None

    finally:
        window.close()


def test_qt_stale_result_cannot_retarget_or_clear_current_input() -> None:
    """Ignore a result for a newer instance in the captured composer.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate stale-result isolation.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    captured = make_target("speak-captured")
    newer = make_target("speak-newer")

    try:
        window.open_for(captured)
        window.editor.setPlainText("Conservar este texto")
        window._delivery_finished(accepted_result(newer, ReplyTerminalState.RESPONSED))

        assert window.target == captured
        assert window.editor.toPlainText() == "Conservar este texto"
        assert window._terminal_state == ""
        assert window.steer_button.isEnabled() is True

    finally:
        window.close()


def test_qt_stale_speaked_result_discards_input_and_locks_exact_instance() -> None:
    """Discard editor text when the captured instance is already terminal.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate stale terminal discard and one-shot locking.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    target = make_target("speak-stale")

    try:
        window.open_for(target)
        window.editor.setPlainText("Descartar si ya terminó")
        window._submit(DeliveryMode.STEER)
        controller.emit_result(
            ReplyResultDTO(
                accepted=False,
                thread_id=target.thread_id,
                mode=DeliveryMode.STEER,
                error="Instance already spoken.",
                instance_id=target.instance_id,
                state=ReplyTerminalState.SPEAKED.value,
            )
        )

        assert window.editor.toPlainText() == ""
        assert window.isVisible() is False
        assert window.steer_button.isEnabled() is False
        assert window._terminal_state == ReplyTerminalState.SPEAKED.value

        controller.emit_result(accepted_result(target, ReplyTerminalState.RESPONSED))
        assert len(controller.submissions) == 1
        assert window._terminal_state == ReplyTerminalState.SPEAKED.value

    finally:
        window.close()


def test_qt_close_requests_one_exact_cancellation_and_blocks_duplicates() -> None:
    """Treat close/cancel as one terminal operation for the immutable target.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate idempotent cancellation.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    target = make_target("speak-cancel", session_id="session-present")

    try:
        window.open_for(target)
        window.editor.setPlainText("Texto que no se debe perder")
        window._close_requested()
        window._close_requested()

        assert controller.submissions == []
        assert controller.cancellations == [target]
        assert window.isVisible() is False
        assert window.editor.toPlainText() == ""

        controller.emit_result(accepted_result(target, ReplyTerminalState.CANCELED))
        controller.emit_result(accepted_result(target, ReplyTerminalState.CANCELED))

        assert window._terminal_state == ReplyTerminalState.CANCELED.value
        assert window.steer_button.isEnabled() is False

        window.open_for(target)
        window._close_requested()

        assert controller.cancellations == [target, target]

    finally:
        window.close()


def test_qt_gateway_failure_reenables_action_and_preserves_input() -> None:
    """Keep editor content intact when asynchronous delivery is rejected.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate failure input preservation.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    target = make_target("speak-failure")

    try:
        window.open_for(target)
        window.editor.setPlainText("Conservar si falla")
        window._submit(DeliveryMode.STEER)
        controller.emit_result(
            ReplyResultDTO(
                accepted=False,
                thread_id=target.thread_id,
                mode=DeliveryMode.STEER,
                error="daemon unavailable",
                instance_id=target.instance_id,
            )
        )

        assert window.editor.toPlainText() == "Conservar si falla"
        assert window.steer_button.isEnabled() is True
        assert "daemon unavailable" in window.status_label.text()

        window._submit(DeliveryMode.STEER)
        assert len(controller.submissions) == 2
        assert controller.submissions[-1][0] == target

    finally:
        window.close()


def test_qt_released_close_hides_resets_and_reopens_before_terminal_close() -> None:
    """Verify RELEASED reopens the hold while terminal close remains final.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate attachment cleanup and close-state transitions.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    close_requests: list[CodexThreadTargetDTO] = []
    controller.close = close_requests.append  # type: ignore[attr-defined]
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    target = make_target("speak-reopen")

    try:
        window.open_for(target)
        action_buttons = (
            window.screenshot_button,
            window.yes_button,
            window.not_button,
            window.steer_button,
        )
        assert all(button.isEnabled() for button in action_buttons)
        assert controller.opens == [target]
        window.editor.setPlainText("Limpiar al cerrar")
        assert window._mark_clipboard_attachment(target) is True
        window._close_requested()

        assert close_requests == [target]
        assert window.isVisible() is False
        assert window.editor.toPlainText() == ""
        assert window._clipboard_attachment_instance_id is None
        assert all(not button.isEnabled() for button in action_buttons)

        controller.emit_result(accepted_result(target, ReplyTerminalState.RELEASED))

        assert window.isVisible() is False
        assert window.editor.toPlainText() == ""
        assert window._hold_live is False
        assert window._terminal_state == ""
        assert all(not button.isEnabled() for button in action_buttons)

        window.open_for(target)
        assert controller.opens == [target, target]
        assert window._hold_live is True
        assert window._terminal_state == ""
        assert all(button.isEnabled() for button in action_buttons)

        assert window._mark_clipboard_attachment(target) is True
        window._close_requested()
        assert close_requests == [target, target]
        assert window._clipboard_attachment_instance_id is None
        controller.emit_result(accepted_result(target, ReplyTerminalState.CANCELED))

        assert window._terminal_state == ReplyTerminalState.CANCELED.value
        assert window._hold_live is False
        assert window._clipboard_attachment_instance_id is None
        assert window.isVisible() is False
        assert all(not button.isEnabled() for button in action_buttons)

        window._close_requested()
        controller.emit_result(accepted_result(target, ReplyTerminalState.RELEASED))
        assert close_requests == [target, target]
        assert window._terminal_state == ReplyTerminalState.CANCELED.value

    finally:
        window.close()


def test_qt_composer_paints_hovered_pink_corner_handle_in_both_themes() -> None:
    """Render only the hovered pink handle fully inside the composer canvas.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate hover-only visibility and complete handle pixels.
    """

    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]

    try:
        window.resize(570, 270)
        window.show()

        logical_centers = {
            "nw": QPointF(2, 2),
            "ne": QPointF(window.width() - 2, 2),
            "sw": QPointF(2, window.height() - 2),
            "se": QPointF(window.width() - 2, window.height() - 2),
        }

        for theme in ("light", "dark"):
            window.set_theme(theme)
            QApplication.processEvents()

            for corner, center in logical_centers.items():
                assert window._resize_corner(center) == corner
                window._hover_corner = corner
                window.update()
                QApplication.processEvents()
                image = window.grab().toImage()
                painted_center = {
                    "nw": QPoint(7, 7),
                    "ne": QPoint(window.width() - 7, 7),
                    "sw": QPoint(7, window.height() - 7),
                    "se": QPoint(window.width() - 7, window.height() - 7),
                }[corner]
                assert image.pixelColor(painted_center).name() == "#f062b7"

            window._hover_corner = ""
            window.update()
            QApplication.processEvents()
            image = window.grab().toImage()
            assert image.pixelColor(QPoint(7, 7)).name() != "#f062b7"

    finally:
        window.close()


def test_qt_composer_corner_resize_handles_are_bounded_and_retained() -> None:
    """Resize from every corner within bounds and retain the resulting geometry.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate hit areas, bounds, cursors, and persistence.
    """
    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    target = make_target("speak-resize")

    def event(
        event_type: QEvent.Type,
        local: QPoint,
        global_position: QPoint,
        button: Qt.MouseButton,
        buttons: Qt.MouseButton,
    ) -> QMouseEvent:
        """Build one deterministic mouse event for the resize interaction.

        Args:
            event_type: Qt event type to synthesize.
            local: Pointer position in composer coordinates.
            global_position: Pointer position in screen coordinates.
            button: Button responsible for the event.
            buttons: Buttons held while the event is dispatched.

        Returns:
            QMouseEvent: Synthetic pointer event for the geometry mixin.
        """
        return QMouseEvent(
            event_type,
            QPointF(local),
            QPointF(global_position),
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )

    try:
        window.open_for(target, QRect(100, 100, 430, 280))
        corners = {
            "nw": (
                QPoint(1, 1),
                QPoint(-25, -20),
                Qt.CursorShape.SizeFDiagCursor,
            ),
            "ne": (
                QPoint(window.width() - 2, 1),
                QPoint(25, -20),
                Qt.CursorShape.SizeBDiagCursor,
            ),
            "sw": (
                QPoint(1, window.height() - 2),
                QPoint(-25, 20),
                Qt.CursorShape.SizeBDiagCursor,
            ),
            "se": (
                QPoint(window.width() - 2, window.height() - 2),
                QPoint(25, 20),
                Qt.CursorShape.SizeFDiagCursor,
            ),
        }

        for corner, (local, delta, cursor) in corners.items():
            window.reset_geometry(QRect(100, 100, 430, 280))
            origin = QRect(window.geometry())
            assert window._resize_corner(QPointF(local)) == corner
            assert window._resize_cursor(corner) == cursor
            global_start = origin.topLeft() + local
            window.mousePressEvent(
                event(
                    QEvent.Type.MouseButtonPress,
                    local,
                    global_start,
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                )
            )
            global_end = global_start + delta
            window.mouseMoveEvent(
                event(
                    QEvent.Type.MouseMove,
                    local,
                    global_end,
                    Qt.MouseButton.NoButton,
                    Qt.MouseButton.LeftButton,
                )
            )
            window.mouseReleaseEvent(
                event(
                    QEvent.Type.MouseButtonRelease,
                    local,
                    global_end,
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.NoButton,
                )
            )

            screen = window._available_screen_geometry(window.geometry())
            assert screen is not None
            safe_area = window._safe_screen_rect(screen)
            minimum = window.safe_minimum_size(screen)
            assert safe_area.contains(window.geometry())
            assert window.width() >= minimum.width()
            assert window.height() >= minimum.height()
            assert window._manual_geometry == window.geometry()

    finally:
        window.close()


def test_qt_composer_reopen_retains_manual_rectangle_until_reset() -> None:
    """Retain manual composer geometry until an explicit geometry reset.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions validate reopen persistence and reset behavior.
    """
    QApplication.instance() or QApplication([])
    controller = ReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    target = make_target("speak-geometry")

    try:
        automatic = QRect(100, 100, 420, 260)
        window.open_for(target, automatic)
        window.setGeometry(QRect(140, 130, 400, 240))
        retained = QRect(window.geometry())
        assert window._manual_geometry == retained

        window.hide()
        window.open_for(target, QRect(280, 280, 360, 220))
        assert window.geometry() == retained

        window.reset_geometry(automatic)
        assert window._manual_geometry is None
        window.hide()
        automatic_after_reset = QRect(280, 280, 360, 220)
        window.open_for(target, automatic_after_reset)
        assert window.geometry() == window._bounded_geometry(automatic_after_reset)

    finally:
        window.close()
