"""Coordinate screenshot capture and annotation for the Qt reply composer."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from brain.presentation.avatar.communication.contracts.models import CodexThreadTargetDTO

from .actions import CLIPBOARD_INSTRUCTION, append_clipboard_instruction
from .window import QtReplyWindow




class ScreenCapturePort(Protocol):
    """Describe the narrow desktop-capture boundary used by the coordinator."""

    def capture(self) -> QPixmap:
        """Return one source-resolution desktop pixmap.

        Args:
            No external arguments are accepted; the port owns the capture source.

        Returns:
            QPixmap: Source-resolution desktop pixmap captured from the desktop.
        """


AnnotationFactory = Callable[[QPixmap, QWidget | None], QDialog]
ClipboardWriter = Callable[[QPixmap], None]


@dataclass
class _ScreenshotSession:
    """Preserve one composer state while its modeless editor is open.

    Attributes:
        target: Immutable reply target captured when SCREENSHOT was pressed.
        composer_text: Original composer text used when canceling or failing.
        composer_status: Original status text restored when canceling.
        editor: Modeless editor associated with this session, when created.
        resolved: Whether the editor outcome has already been applied.
    """

    target: CodexThreadTargetDTO
    composer_text: str
    composer_status: str
    editor: QDialog | None = None
    resolved: bool = False


class QtReplyScreenshotCoordinator:
    """Orchestrate one reply screenshot capture without owning reply delivery.

    The coordinator receives a capture port and an annotation-editor factory so
    the reply composer never imports backlog application, task, or storage
    responsibilities. It owns only the temporary editor lifecycle and the
    clipboard/text transaction after Save.

    Attributes:
        _reply_window: Composer whose SCREENSHOT signal is being consumed.
        _capture: Injected clean-desktop capture port.
        _annotation_factory: Factory for the reused annotation dialog.
        _clipboard_writer: Clipboard boundary, injectable for deterministic tests.
        _editor: Current modeless annotation editor, if one exists.
        _session: State snapshot associated with the current editor.
        _closed: Whether the coordinator has been disposed.
    """

    def __init__(
        self,
        reply_window: QtReplyWindow,
        capture: ScreenCapturePort,
        annotation_factory: AnnotationFactory,
        clipboard_writer: ClipboardWriter | None = None,
    ) -> None:
        """Connect the composer signal to one injected screenshot workflow.

        Args:
            reply_window: Composer whose target, text, and lifecycle are preserved.
            capture: Clean desktop capture port reused from the Qt backlog view.
            annotation_factory: Factory receiving the captured pixmap and parent.
            clipboard_writer: Optional clipboard callable used after Save.

        Returns:
            None: The coordinator is connected and ready for SCREENSHOT actions.
        """
        self._reply_window = reply_window
        self._capture = capture
        self._annotation_factory = annotation_factory
        self._clipboard_writer = clipboard_writer or self._write_to_clipboard
        self._editor: QDialog | None = None
        self._session: _ScreenshotSession | None = None
        self._closed = False
        self._reply_window.screenshotRequested.connect(self._on_screenshot_requested)

    def close(self) -> None:
        """Dispose the current editor and disconnect the composer signal.

        Args:
            No external arguments are accepted; the coordinator owns its lifecycle.

        Returns:
            None: Future screenshot requests and stale editor callbacks are ignored.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self._closed:

            return

        self._closed = True
        session = self._session
        editor = self._editor
        self._editor = None
        self._session = None

        # Guard clause: verify required active entity presence
        if session is not None:
            self._reply_window._clear_clipboard_attachment(session.target)

        # Guard clause: verify required active entity presence
        if editor is not None:
            editor.close()

        # Exception safety: execute operation within protected error boundary
        try:
            self._reply_window.screenshotRequested.disconnect(
                self._on_screenshot_requested,
            )

        # Failure recovery: handle execution or transport exception
        except (RuntimeError, TypeError):
            pass

    def _on_screenshot_requested(self) -> None:
        """Capture the desktop and open one annotation editor for the target.

        Args:
            No external arguments are accepted; Qt invokes this signal handler.

        Returns:
            None: Capture failures remain visible in the composer status label.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self._closed:

            return

        # Guard clause: verify required active entity presence
        if self._editor is not None:
            self._focus_editor()

            return

        target = self._reply_window.target

        # Guard clause: verify required active entity presence
        if target is None or not self._reply_window.is_target_active(target):

            return

        session = _ScreenshotSession(
            target=target,
            composer_text=self._reply_window.editor.toPlainText(),
            composer_status=self._reply_window.status_label.text(),
        )
        self._session = session

        # Exception safety: execute operation within protected error boundary
        try:
            pixmap = self._capture.capture()

        # Failure recovery: handle execution or transport exception
        except Exception as error:  # noqa: BLE001 - surface adapter failures in Qt.
            self._fail_without_editor(session, f"Screenshot capture failed: {error}")

            return

        # Conditional check: evaluate domain preconditions and invariants
        if pixmap.isNull():
            self._fail_without_editor(session, "Capture unavailable.")

            return

        # Guard clause: verify required active entity presence
        if not self._reply_window.is_target_active(target):
            self._reply_window._clear_clipboard_attachment(session.target)
            self._clear_session(session)

            return

        self._reply_window.hide()

        # Exception safety: execute operation within protected error boundary
        try:
            editor = self._annotation_factory(pixmap, self._reply_window)
            session.editor = editor
            self._editor = editor
            editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            editor.accepted.connect(
                lambda: self._editor_accepted(editor, session),
            )
            editor.finished.connect(
                lambda result: self._editor_finished(editor, session, result),
            )
            editor.destroyed.connect(
                lambda _object=None: self._editor_destroyed(editor, session),
            )
            editor.show()
            editor.raise_()
            editor.activateWindow()

        # Failure recovery: handle execution or transport exception
        except Exception as error:  # noqa: BLE001 - keep the composer recoverable.
            self._fail_with_editor(session, f"Annotation editor failed: {error}")

    def _focus_editor(self) -> None:
        """Raise the existing modeless editor instead of capturing again.

        Args:
            No external arguments are accepted; the coordinator owns the editor.

        Returns:
            None: The one active annotation editor receives focus.
        """

        editor = self._editor

        # Conditional check: evaluate domain preconditions and invariants
        if editor is None:

            return

        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _editor_accepted(
        self,
        editor: QDialog,
        session: _ScreenshotSession,
    ) -> None:
        """Copy a current annotation result and mark a hidden attachment.

        Args:
            editor: Editor that emitted the accepted signal.
            session: State snapshot captured before the editor was opened.

        Returns:
            None: A valid Save updates the clipboard and preserves visible editor text.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self._is_current_editor(editor, session) or session.resolved:

            return

        # Guard clause: verify required active entity presence
        if not self._reply_window.is_target_active(session.target):
            session.resolved = True
            self._reply_window._clear_clipboard_attachment(session.target)

            return

        result_method = getattr(editor, "result_pixmap", None)

        # Guard clause: verify required active entity presence
        if not callable(result_method):
            self._fail_with_editor(session, "Annotation result unavailable.")

            return

        # Exception safety: execute operation within protected error boundary
        try:
            result_pixmap = result_method()

        # Failure recovery: handle execution or transport exception
        except Exception as error:  # noqa: BLE001 - surface editor failures in Qt.
            self._fail_with_editor(session, f"Annotation export failed: {error}")

            return

        # Conditional check: evaluate domain preconditions and invariants
        if result_pixmap.isNull():
            self._fail_with_editor(session, "Annotation result unavailable.")

            return

        # Exception safety: execute operation within protected error boundary
        try:
            self._clipboard_writer(result_pixmap)

        # Failure recovery: handle execution or transport exception
        except Exception as error:  # noqa: BLE001 - keep text unchanged on failure.
            self._fail_with_editor(session, f"Clipboard copy failed: {error}")

            return

        # Guard clause: verify required active entity presence
        if not self._reply_window._mark_clipboard_attachment(session.target):
            session.resolved = True
            self._reply_window._clear_clipboard_attachment(session.target)

            return

        session.resolved = True
        restored = self._restore_composer(
            session,
            session.composer_text,
            "✓ Screenshot copied to Clipboard.",
        )

        # Conditional check: evaluate domain preconditions and invariants
        if not restored:
            self._reply_window._clear_clipboard_attachment(session.target)

    def _editor_finished(
        self,
        editor: QDialog,
        session: _ScreenshotSession,
        result: int,
    ) -> None:
        """Restore the composer after Save or Cancel and retire the editor.

        Args:
            editor: Editor whose finished signal fired.
            session: State snapshot captured before the editor was opened.
            result: Qt dialog result code.

        Returns:
            None: Stale editor callbacks cannot clear a newer editor session.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self._is_current_editor(editor, session):

            return

        # Guard clause: verify required active entity presence
        if result == int(QDialog.DialogCode.Accepted) and not session.resolved:
            self._editor_accepted(editor, session)

        # Conditional check: evaluate domain preconditions and invariants
        if not session.resolved:
            session.resolved = True
            self._reply_window._clear_clipboard_attachment(session.target)
            self._restore_composer(
                session,
                session.composer_text,
                session.composer_status,
            )

        self._clear_session(session)

    def _editor_destroyed(
        self,
        editor: QDialog,
        session: _ScreenshotSession,
    ) -> None:
        """Discard a destroyed editor without touching a newer active session.

        Args:
            editor: Editor whose destroyed signal fired.
            session: State snapshot associated with the editor.

        Returns:
            None: The composer is restored only for the still-current session.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self._is_current_editor(editor, session):

            return

        # Conditional check: evaluate domain preconditions and invariants
        if not session.resolved:
            session.resolved = True
            self._reply_window._clear_clipboard_attachment(session.target)
            self._restore_composer(
                session,
                session.composer_text,
                session.composer_status,
            )

        self._clear_session(session)

    def _fail_without_editor(
        self,
        session: _ScreenshotSession,
        status: str,
    ) -> None:
        """Show a capture/factory failure and restore the original composer.

        Args:
            session: State snapshot created for the failed capture.
            status: User-visible failure text.

        Returns:
            None: The composer remains editable and no terminal reply is sent.
        """
        session.resolved = True
        self._reply_window._clear_clipboard_attachment(session.target)
        self._restore_composer(session, session.composer_text, status)
        self._clear_session(session)

    def _fail_with_editor(self, session: _ScreenshotSession, status: str) -> None:
        """Restore the composer after an editor-side failure.

        Args:
            session: State snapshot associated with the current editor.
            status: User-visible failure text.

        Returns:
            None: The finished editor callback can retire the failed session.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if session.resolved:

            return

        session.resolved = True
        self._reply_window._clear_clipboard_attachment(session.target)
        self._restore_composer(session, session.composer_text, status)

        editor = session.editor

        # Guard clause: verify required active entity presence
        if editor is not None:
            editor.close()

    def _restore_composer(
        self,
        session: _ScreenshotSession,
        text: str,
        status: str,
    ) -> bool:
        """Restore text, status, and focus when the captured target is still live.

        Args:
            session: State snapshot whose target must still own the composer.
            text: Text to place in the composer.
            status: Status text to display after restoration.

        Returns:
            bool: True when the same live instance was restored, otherwise False.
        """

        # Guard clause: verify required active entity presence
        if self._closed or not self._reply_window.is_target_active(session.target):

            return False

        self._reply_window.editor.setPlainText(text)
        self._reply_window.status_label.setText(status)
        self._reply_window.show()
        self._reply_window.raise_()
        self._reply_window.activateWindow()
        self._reply_window.editor.setFocus()

        return True

    def _is_current_editor(
        self,
        editor: QDialog,
        session: _ScreenshotSession,
    ) -> bool:
        """Return whether an editor callback belongs to the active session.

        Args:
            editor: Editor object supplied by the callback.
            session: Session object supplied by the callback.

        Returns:
            bool: True only for the current editor and live coordinator.
        """

        return (
            not self._closed
            and self._editor is editor
            and self._session is session
        )

    def _clear_session(self, session: _ScreenshotSession) -> None:
        """Clear one session only when it still owns the coordinator slot.

        Args:
            session: Session candidate that may have completed or become stale.

        Returns:
            None: A newer editor session is left untouched.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self._session is not session:

            return

        self._editor = None
        self._session = None

    @staticmethod
    def _write_to_clipboard(pixmap: QPixmap) -> None:
        """Copy one source-resolution pixmap to the native Qt clipboard.

        Args:
            pixmap: Marked screenshot returned by the annotation editor.

        Returns:
            None: The current QApplication clipboard owns the copied pixmap.
        """
        QApplication.clipboard().setPixmap(pixmap)
