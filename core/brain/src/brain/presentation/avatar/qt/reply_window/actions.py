"""Reply target binding and asynchronous lifecycle actions for the composer."""
from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QCloseEvent

from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    DeliveryMode,
    ReplyResultDTO,
    ReplyTerminalState,
)


CLIPBOARD_INSTRUCTION = "See the image on the Clipboard"


def append_clipboard_instruction(text: str) -> str:
    """Append the exact clipboard instruction once with clean separation.

    Args:
        text: Current composer content before the instruction is applied.

    Returns:
        str: Original content plus one instruction line, or unchanged content
        when an exact instruction line is already present.
    """

    # Payload validation: check input payload parameters
    if any(line.strip() == CLIPBOARD_INSTRUCTION for line in text.splitlines()):

        return text

    content = text.rstrip()
    separator = "\n\n" if content else ""

    return f"{content}{separator}{CLIPBOARD_INSTRUCTION}"


class QtReplyWindowActionsMixin:
    """Manage target capture, delivery actions, and terminal lifecycle state.

    Attributes:
        _TERMINAL_STATES: Reply states that permanently finish one captured instance.
    """

    _TERMINAL_STATES: frozenset[str] = frozenset(
        {
            ReplyTerminalState.CANCELED.value,
            ReplyTerminalState.SPEAKED.value,
            ReplyTerminalState.RESPONSED.value,
        }
    )

    @property
    def target(self) -> CodexThreadTargetDTO | None:
        """Return the conversation target currently bound to the composer.

        Args:

        Returns:
            CodexThreadTargetDTO | None: Bound target, or None when idle.
        """

        return self._target

    def _mark_clipboard_attachment(self, target: CodexThreadTargetDTO) -> bool:
        """Mark one saved clipboard image for the exact active target.

        Args:
            target: Target associated with the saved screenshot.

        Returns:
            bool: True when the target still owns a live composer hold.
        """

        # Guard clause: verify required active entity presence
        if not self.is_target_active(target):

            return False

        self._clipboard_attachment_instance_id = target.instance_id

        return True

    def _clear_clipboard_attachment(
        self, target: CodexThreadTargetDTO | None = None
    ) -> None:
        """Clear the hidden clipboard marker globally or for one target.

        Args:
            target: Optional target whose marker may be cleared.

        Returns:
            None: The marker is cleared only when it belongs to the requested target.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if (
            target is not None
            and self._clipboard_attachment_instance_id != target.instance_id
        ):

            return

        self._clipboard_attachment_instance_id = None

    def _has_clipboard_attachment(self) -> bool:
        """Return whether the current target owns a saved clipboard image.

        Args:
            No external arguments are accepted; the composer owns the target state.

        Returns:
            bool: True when the hidden marker matches the current target instance.
        """

        return (
            self._target is not None
            and self._clipboard_attachment_instance_id == self._target.instance_id
        )

    def _submission_text(self, text: str) -> str:
        """Build ENVIAR text with one hidden clipboard attachment instruction.

        Args:
            text: Editor text captured for the regular ENVIAR action.

        Returns:
            str: Editor text plus the exact instruction when an attachment is marked.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self._has_clipboard_attachment():

            return text

        return append_clipboard_instruction(text)

    def open_for(
        self, target: CodexThreadTargetDTO, geometry: QRect | None = None
    ) -> None:
        """Bind composer to one message target and reveal the window.

        Args:
            target: Target inherited from one message.
            geometry: Optional initial composer geometry.

        Returns:
            None: The target is bound and the composer is activated.
        """

        # Guard clause: verify required active entity presence
        if self.isVisible() and self._target is not None:
            self.raise_()
            self.activateWindow()

            return

        target_changed = (
            self._target is None or self._target.instance_id != target.instance_id
        )
        reopen_same_target = self._can_reopen_same_target(target_changed)
        fresh_session = target_changed or reopen_same_target

        # Conditional check: evaluate domain preconditions and invariants
        if fresh_session:
            self._clear_clipboard_attachment()

            # Conditional check: evaluate domain preconditions and invariants
            if target_changed:
                self._target = target
            self._hold_pending = False
            self._hold_live = True
            self._terminal_action_pending = False
            self._terminal_action = ""
            self._terminal_state = ""
            self.editor.clear()
            self.target_label.setText(f"🧵 Task {target.thread_id}")
            self.target_label.setToolTip(target.thread_id)
            self.status_label.clear()
            self.status_label.setStyleSheet(
                "color: #765568; background: transparent; padding: 0 3px;"
            )

            # Conditional check: evaluate domain preconditions and invariants
            if hasattr(self._controller, "open"):
                self._hold_pending = True
                self._hold_live = False

                # Exception safety: execute operation within protected error boundary
                try:
                    self._controller.open(target)

                # Failure recovery: handle execution or transport exception
                except Exception as exc:  # noqa: BLE001 - opening remains UI-visible.
                    self._hold_pending = False
                    self._hold_live = True
                    self.status_label.setText(str(exc))

        self._set_actions_enabled(
            True,
            allow_pending=self._hold_pending,
        )

        requested_geometry = (
            QRect(self._manual_geometry)

            # Guard clause: verify required active entity presence
            if self._manual_geometry is not None
            else geometry
        )

        # Guard clause: verify required active entity presence
        if requested_geometry is not None:
            actual_geometry = self._apply_geometry(requested_geometry)

            # Guard clause: verify required active entity presence
            if self._manual_geometry is not None:
                self._manual_geometry = QRect(actual_geometry)

        self._applying_geometry = True

        # Exception safety: execute operation within protected error boundary
        try:
            self.show()

        finally:
            self._applying_geometry = False
        self.raise_()
        self.activateWindow()
        self.editor.setFocus()

    def _can_reopen_same_target(self, target_changed: bool) -> bool:
        """Return whether the released target can be reopened for editing.

        Args:
            target_changed: Whether the incoming target is a different instance.

        Returns:
            bool: Whether the same non-terminal instance may be reopened.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if target_changed:
            return False

        return not (
            self._hold_live
            or self._hold_pending
            or self._terminal_action_pending
        )

    def _composer_opened(self, result: ReplyResultDTO) -> None:
        """Record whether the exact captured instance remains open for editing.

        Args:
            result: Hold acknowledgement or failure for one exact instance.

        Returns:
            None: The composer controls reflect the hold lifecycle.
        """

        # Identity validation: check canonical message or instance identifier
        if self._target is None or result.instance_id != self._target.instance_id:
            return

        # Conditional check: evaluate domain preconditions and invariants
        if not self._hold_pending:
            return

        # State guard: verify component lifecycle state preconditions
        if self._terminal_state or (
            self._terminal_action_pending and self._terminal_action == "close"
        ):
            return

        self._hold_pending = False

        is_terminal = result.state in self._TERMINAL_STATES

        # Guard clause: verify required active entity presence
        if result.accepted and not is_terminal:
            self._hold_live = True
            self._set_actions_enabled(True)
            self.status_label.clear()

            return

        self._hold_live = False
        self._terminal_state = result.state or "OPEN_FAILED"
        self._clear_clipboard_attachment()
        self._set_actions_enabled(False)
        self.editor.clear()
        self.close()

    def _submit_steer(self) -> None:
        """Submit the editor text through the existing STEER action.

        Args:
            No external arguments are accepted; the ENVIAR action supplies the request.

        Returns:
            None: The editor submission follows the shared reply lifecycle.
        """

        self._submit(DeliveryMode.STEER)

    def _submit_yes(self) -> None:
        """Submit the fixed affirmative fast response through STEER.

        Args:
            No external arguments are accepted; the YES action supplies the response.

        Returns:
            None: A literal Yes request follows the shared reply lifecycle.
        """

        self._submit_fast_response("Yes")

    def _submit_not(self) -> None:
        """Submit the fixed negative fast response through STEER.

        Args:
            No external arguments are accepted; the NOT action supplies the response.

        Returns:
            None: A literal No request follows the shared reply lifecycle.
        """

        self._submit_fast_response("No")

    def _submit_fast_response(self, text: str) -> None:
        """Submit one fixed response without reading or changing editor input.

        Args:
            text: Literal fast-response content selected by a reply action.

        Returns:
            None: The response is delegated to the shared typed submit helper.
        """

        self._submit_text(text, DeliveryMode.STEER)

    def _screenshot_requested(self) -> None:
        """Emit the screenshot request entry point without capture logic.

        Args:
            No external arguments are accepted; the SCREENSHOT action supplies the request.

        Returns:
            None: A dedicated signal is emitted only while the composer can act.
        """

        target = self._target

        # Conditional check: evaluate domain preconditions and invariants
        if (
            not self.screenshot_button.isEnabled()
            or target is None
            or not self.is_target_active(target)
        ):
            return

        self.screenshotRequested.emit()

    def _submit(self, mode: DeliveryMode) -> None:
        """Submit the current editor text through the shared typed helper.

        Args:
            mode: Delivery strategy requested by the action.

        Returns:
            None: Editor submission is scheduled or its validation error is displayed.
        """

        text = self._submission_text(self.editor.toPlainText())
        self._submit_text(text, mode)

    def _submit_text(self, text: str, mode: DeliveryMode) -> None:
        """Validate and submit one reply text asynchronously.

        Args:
            text: Reply content supplied by the editor or a fast-response action.
            mode: Delivery strategy requested by the action.

        Returns:
            None: Submission is scheduled or its validation error is displayed.
        """

        target = self._target

        # Conditional check: evaluate domain preconditions and invariants
        if target is None:
            self.status_label.setText("Escribe un mensaje antes de enviarlo.")

            return

        # Payload validation: check input payload parameters
        if not text.strip():
            self.status_label.setText("Escribe un mensaje antes de enviarlo.")

            return

        # Conditional check: evaluate domain preconditions and invariants
        if (
            not self._hold_live
            or self._hold_pending
            or self._terminal_action_pending
            or self._terminal_state
        ):

            return

        # Exception safety: execute operation within protected error boundary
        try:
            self._terminal_action_pending = True
            self._terminal_action = "send"
            self._set_actions_enabled(False)
            self.status_label.setText("Enviando…")
            self._controller.submit(target, text, mode)

        # Validation handling: handle invalid input domain error
        except ValueError as exc:
            self._terminal_action_pending = False
            self._terminal_action = ""
            self._set_actions_enabled(True)
            self.status_label.setText(str(exc))

    def _close_requested(self) -> None:
        """Close the captured composer once, then hide the window.

        Args:

        Returns:
            None: The close action is either scheduled or already terminal.
        """
        self._clear_clipboard_attachment()
        self.editor.clear()
        self._close()
        self.hide()

    def _close(self) -> None:
        """Schedule exact composer close/release once.

        Args:

        Returns:
            None: Cancellation is delegated asynchronously when possible.
        """
        self._clear_clipboard_attachment()
        target = self._target

        # State guard: verify component lifecycle state preconditions
        if target is None or self._terminal_state or self._terminal_action_pending:

            return

        self._terminal_action_pending = True
        self._terminal_action = "close"
        self._hold_pending = False
        self._set_actions_enabled(False)
        self.status_label.setText("Cerrando…")

        # Exception safety: execute operation within protected error boundary
        try:
            close_operation = getattr(self._controller, "close", None)

            # Conditional check: evaluate domain preconditions and invariants
            if not callable(close_operation):
                close_operation = self._controller.cancel
            close_operation(target)

        # Failure recovery: handle execution or transport exception
        except Exception as exc:  # noqa: BLE001 - close must remain idempotent.
            self._terminal_action_pending = False
            self._terminal_action = ""
            self._hold_live = False
            self._terminal_state = "CANCEL_FAILED"
            self._set_actions_enabled(False)
            self.status_label.setText(str(exc))

    def _cancel(self) -> None:
        """Preserve the legacy private cancellation hook.

        Args:

        Returns:
            None: The close/release action is delegated to _close.
        """
        self._close()

    def _delivery_finished(self, result: ReplyResultDTO) -> None:
        """Render the completed delivery outcome in the composer.

        Args:
            result: Accepted or rejected delivery outcome.

        Returns:
            None: Editor state and status text reflect the result.
        """

        # Identity validation: check canonical message or instance identifier
        if self._target is None or result.instance_id != self._target.instance_id:

            return

        action = self._terminal_action

        # Conditional check: evaluate domain preconditions and invariants
        if self._hold_pending and action not in {"cancel", "close"}:

            return

        self._terminal_action_pending = False
        self._terminal_action = ""

        # Conditional check: evaluate domain preconditions and invariants
        if action == "close":
            self._clear_clipboard_attachment()
            terminal_state = result.state

            # State guard: verify component lifecycle state preconditions
            if result.accepted and terminal_state == ReplyTerminalState.RELEASED.value:
                self._hold_live = False
                self._terminal_state = ""
                self.editor.clear()
                self._set_actions_enabled(False)
                self.status_label.setText("Compositor cerrado; puedes reabrirlo.")
                self.hide()

                return

            # State guard: verify component lifecycle state preconditions
            if terminal_state in self._TERMINAL_STATES:
                self._hold_live = False
                self._terminal_state = terminal_state
                self.editor.clear()
                self._set_actions_enabled(False)

                # State guard: verify component lifecycle state preconditions
                if terminal_state == ReplyTerminalState.CANCELED.value:
                    self.status_label.setText("✓ Respuesta cancelada.")

                # State guard: verify component lifecycle state preconditions
                elif terminal_state == ReplyTerminalState.SPEAKED.value:
                    self.status_label.setText("La instancia ya había terminado.")

                else:
                    self.status_label.setText("✓ Respuesta enviada.")
                self.close()

                return

            self._hold_live = True
            self._set_actions_enabled(True)
            self.status_label.setText(f"No se pudo cerrar: {result.error}")

            return

        # Conditional check: evaluate domain preconditions and invariants
        if action == "cancel":
            self._clear_clipboard_attachment()
            self._hold_live = False
            terminal_state = result.state or ReplyTerminalState.CANCELED.value
            self._terminal_state = terminal_state
            self.editor.clear()
            self._set_actions_enabled(False)
            self.status_label.setText("✓ Respuesta cancelada.")
            self.close()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if action != "send" and not self._hold_live:

            return

        is_terminal = result.state in self._TERMINAL_STATES

        # Conditional check: evaluate domain preconditions and invariants
        if is_terminal:
            self._clear_clipboard_attachment()

        # Conditional check: evaluate domain preconditions and invariants
        if result.accepted:

            # Conditional check: evaluate domain preconditions and invariants
            if is_terminal:
                self._terminal_state = result.state
                self._hold_live = False
                self._set_actions_enabled(False)
                self.editor.clear()

                # State guard: verify component lifecycle state preconditions
                if result.state == ReplyTerminalState.CANCELED.value:
                    self.status_label.setText("✓ Respuesta cancelada.")

                # State guard: verify component lifecycle state preconditions
                elif result.state == ReplyTerminalState.SPEAKED.value:
                    self.status_label.setText("La instancia ya había terminado.")

                else:
                    self.status_label.setText("✓ Respuesta enviada.")

                self.close()
                self.status_label.setStyleSheet(
                    "color: #248a62; background: transparent; padding: 0 3px;"
                )

                return

            self._set_actions_enabled(True)
            self._hold_live = True
            self.editor.clear()
            self.status_label.setText("✓ Referencia encolada para entrega nativa.")
            self.status_label.setStyleSheet(
                "color: #248a62; background: transparent; padding: 0 3px;"
            )

            return

        # Conditional check: evaluate domain preconditions and invariants
        if is_terminal:
            self._terminal_state = result.state
            self._hold_live = False
            self._set_actions_enabled(False)
            self.editor.clear()
            self.close()

        else:
            self._hold_live = True
            self._set_actions_enabled(True)
        self.status_label.setText(f"No se pudo entregar: {result.error}")
        self.status_label.setStyleSheet(
            "color: #a33161; background: transparent; padding: 0 3px;"
        )

    def _set_actions_enabled(self, enabled: bool, *, allow_pending: bool = False) -> None:
        """Enable or disable reply actions during asynchronous delivery.

        Args:
            enabled: Whether the send action should accept input.
            allow_pending: Whether buttons stay visually enabled while opening.

        Returns:
            None: The action button state is updated in place.
        """
        actions_enabled = enabled and self._target is not None and (
            self._hold_live or (allow_pending and self._hold_pending)
        )

        # Conditional check: evaluate domain preconditions and invariants
        if (
            self._terminal_action_pending
            or self._terminal_state
            or (self._hold_pending and not allow_pending)
        ):
            actions_enabled = False

        # Loop execution: iterate over items
        for button in self._action_buttons:
            button.setEnabled(actions_enabled)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cancel the captured instance when Qt closes the composer.

        Args:
            event: Qt close event that must be accepted.

        Returns:
            None: The close event is accepted after idempotent cancellation.
        """
        self._clear_clipboard_attachment()
        self.editor.clear()

        # State guard: verify component lifecycle state preconditions
        if not self._terminal_state:
            self._close()
        event.accept()
