"""Persistent offscreen tests for the Qt reply screenshot coordinator."""

from __future__ import annotations

import ast
import os
from collections.abc import Callable
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    DeliveryMode,
    ReplyResultDTO,
)
from brain.presentation.avatar.qt.reply_window import (
    CLIPBOARD_INSTRUCTION,
    QtReplyScreenshotCoordinator,
    QtReplyWindow,
    screenshot as screenshot_module,
)


THREAD_ID = "019f5dad-af67-7533-b394-8fb55258adb2"


class ScreenshotReplyControllerStub(QObject):
    """Expose the reply-window controller signals and record terminal requests."""

    deliveryFinished = Signal(object)
    composerOpened = Signal(object)

    def __init__(self) -> None:
        """Initialize the controller stub and its operation logs.

        Args:
            No external arguments are accepted; the stub owns its state.

        Returns:
            None: The stub is ready to acknowledge composer holds.
        """

        super().__init__()
        self.opens: list[CodexThreadTargetDTO] = []
        self.submissions: list[
            tuple[CodexThreadTargetDTO, str, DeliveryMode]
        ] = []
        self.cancellations: list[CodexThreadTargetDTO] = []

    def open(self, target: CodexThreadTargetDTO) -> None:
        """Acknowledge one exact target as an editable held composer.

        Args:
            target: Immutable reply target captured by the composer.

        Returns:
            None: The open acknowledgement is emitted synchronously.
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
        self,
        target: CodexThreadTargetDTO,
        text: str,
        mode: DeliveryMode,
    ) -> None:
        """Record a reply submission without delivering it.

        Args:
            target: Immutable target supplied by the reply window.
            text: Reply text supplied by the composer.
            mode: Delivery mode selected by the composer.

        Returns:
            None: The request is retained for no-submit assertions.
        """

        self.submissions.append((target, text, mode))

    def cancel(self, target: CodexThreadTargetDTO) -> None:
        """Record a close request without changing the target lifecycle.

        Args:
            target: Immutable target supplied by the reply window.

        Returns:
            None: The request is retained for no-task assertions.
        """

        self.cancellations.append(target)


class FakeCapture:
    """Return a deterministic pixmap or raise an injected capture error."""

    def __init__(
        self,
        pixmap: QPixmap | None = None,
        error: Exception | None = None,
    ) -> None:
        """Initialize one deterministic capture adapter.

        Args:
            pixmap: Source pixmap returned by successful captures, or a null
                pixmap when omitted.
            error: Optional exception raised from the capture boundary.

        Returns:
            None: The adapter is ready for capture calls.
        """

        self._pixmap = QPixmap() if pixmap is None else QPixmap(pixmap)
        self._error = error
        self.calls = 0

    def capture(self) -> QPixmap:
        """Return a fresh source pixmap or surface the configured failure.

        Args:
            No external arguments are accepted; the adapter owns its source.

        Returns:
            QPixmap: A copy of the configured source pixmap.

        Raises:
            Exception: The exception stored in self._error when configured.
            capture._error: The configured exception raised by this capture adapter.
        """

        self.calls += 1

        if self._error is not None:
            raise self._error

        return QPixmap(self._pixmap)


class FakeAnnotationEditor(QDialog):
    """Provide the modeless dialog contract consumed by the coordinator."""

    def __init__(self, pixmap: QPixmap, parent: QWidget | None) -> None:
        """Initialize an editor holding an immutable result-pixmap copy.

        Args:
            pixmap: Captured source pixmap supplied by the coordinator.
            parent: Reply window parent supplied by the coordinator.

        Returns:
            None: The fake editor is ready to accept or reject.
        """

        super().__init__(parent, Qt.WindowType.Dialog)
        self.received_pixmap = QPixmap(pixmap)
        self._result = QPixmap(pixmap)
        self.result_calls = 0
        self.resize(240, 160)

    def result_pixmap(self) -> QPixmap:
        """Return the deterministic annotated result used by Save.

        Args:
            No external arguments are accepted; the editor owns its result.

        Returns:
            QPixmap: A copy of the source-sized result pixmap.
        """

        self.result_calls += 1

        return QPixmap(self._result)


class FakeAnnotationFactory:
    """Create and retain fake editors for lifecycle and duplicate assertions."""

    def __init__(self) -> None:
        """Initialize the editor creation log.

        Args:
            No external arguments are accepted; the factory owns its log.

        Returns:
            None: The factory is ready for injected coordinator calls.
        """

        self.editors: list[FakeAnnotationEditor] = []
        self.received_pixmaps: list[QPixmap] = []
        self.parents: list[QWidget | None] = []

    def __call__(
        self,
        pixmap: QPixmap,
        parent: QWidget | None,
    ) -> QDialog:
        """Create one fake annotation editor for the captured pixmap.

        Args:
            pixmap: Captured source pixmap supplied by the coordinator.
            parent: Reply window parent supplied by the coordinator.

        Returns:
            QDialog: The modeless fake editor instance.
        """

        editor = FakeAnnotationEditor(pixmap, parent)
        self.editors.append(editor)
        self.received_pixmaps.append(QPixmap(pixmap))
        self.parents.append(parent)

        return editor


def _app() -> QApplication:
    """Return the shared offscreen Qt application instance.

    Args:
        No external arguments are accepted; Qt owns the application boundary.

    Returns:
        QApplication: Existing application or a new test application.
    """

    return QApplication.instance() or QApplication([])


def _make_target(instance_id: str) -> CodexThreadTargetDTO:
    """Build one immutable target for a screenshot workflow test.

    Args:
        instance_id: Exact daemon instance identifier owned by the composer.

    Returns:
        CodexThreadTargetDTO: Target carrying stable test metadata.
    """

    return CodexThreadTargetDTO(
        instance_id=instance_id,
        thread_id=THREAD_ID,
        source_message_id="daemon-process-id",
        session_id="session-present",
    )


def _make_source_pixmap() -> QPixmap:
    """Build a small multi-color pixmap whose pixels are easy to compare.

    Args:
        No external arguments are accepted; the fixture owns its colors.

    Returns:
        QPixmap: Deterministic source-resolution capture fixture.
    """

    pixmap = QPixmap(17, 11)
    pixmap.fill(QColor("#17324d"))
    painter = QPainter(pixmap)
    painter.fillRect(QRect(0, 0, 5, 4), QColor("#e76f51"))
    painter.fillRect(QRect(8, 3, 7, 6), QColor("#2a9d8f"))
    painter.end()

    return pixmap


def _pixmap_fingerprint(
    pixmap: QPixmap,
) -> tuple[int, int, tuple[tuple[int, int, int, int], ...]]:
    """Return source size and every pixel color for exact image assertions.

    Args:
        pixmap: Qt pixmap whose size and pixels must be compared.

    Returns:
        tuple[int, int, tuple[tuple[int, int, int, int], ...]]: Width, height,
            and row-major RGBA pixels.
    """

    image = pixmap.toImage()
    pixels = tuple(
        image.pixelColor(x, y).getRgb()
        for y in range(image.height())
        for x in range(image.width())
    )

    return image.width(), image.height(), pixels


def _build_workflow(
    capture: FakeCapture,
    factory: FakeAnnotationFactory,
    clipboard_writer: Callable[[QPixmap], None] | None = None,
) -> tuple[
    ScreenshotReplyControllerStub,
    QtReplyWindow,
    QtReplyScreenshotCoordinator,
]:
    """Compose a real reply window with only injected screenshot boundaries.

    Args:
        capture: Deterministic desktop-capture adapter.
        factory: Deterministic annotation-dialog factory.
        clipboard_writer: Optional clipboard boundary used by Save.

    Returns:
        tuple[...]: Controller, reply window, and screenshot coordinator.
    """

    controller = ScreenshotReplyControllerStub()
    window = QtReplyWindow(controller)  # type: ignore[arg-type]
    coordinator = QtReplyScreenshotCoordinator(
        window,
        capture,
        factory,
        clipboard_writer,
    )

    return controller, window, coordinator


def _cleanup_workflow(
    coordinator: QtReplyScreenshotCoordinator,
    window: QtReplyWindow,
) -> None:
    """Dispose injected dialogs and the composer after one isolated scenario.

    Args:
        coordinator: Screenshot coordinator under test.
        window: Reply composer under test.

    Returns:
        None: Qt event processing completes the local cleanup.
    """

    coordinator.close()
    window.hide()
    window.close()
    QApplication.processEvents()
    QApplication.clipboard().clear()


def test_capture_opens_one_editor_and_duplicate_requests_focus_existing() -> None:
    """Open one injected editor and ignore duplicate capture requests.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions prove one capture, one editor, and no terminal submit.
    """

    app = _app()
    source = _make_source_pixmap()
    capture = FakeCapture(source)
    factory = FakeAnnotationFactory()
    controller, window, coordinator = _build_workflow(capture, factory)
    target = _make_target("screenshot-open")

    try:
        window.open_for(target)
        window.editor.setPlainText("Draft remains outside the editor")
        window.screenshot_button.click()

        assert capture.calls == 1
        assert len(factory.editors) == 1
        first_editor = factory.editors[0]
        assert _pixmap_fingerprint(factory.received_pixmaps[0]) == _pixmap_fingerprint(
            source
        )
        assert factory.parents == [window]
        assert first_editor.isVisible() is True
        assert window.isVisible() is False

        window.screenshot_button.click()
        app.processEvents()

        assert capture.calls == 1
        assert len(factory.editors) == 1
        assert coordinator._editor is first_editor
        assert controller.submissions == []
        assert window.target == target
        assert window._hold_live is True
        assert window._terminal_action_pending is False
        assert window._terminal_state == ""

    finally:
        _cleanup_workflow(coordinator, window)


@pytest.mark.parametrize(
    ("initial_text", "expected_submission"),
    (
        ("", CLIPBOARD_INSTRUCTION),
        (
            "Existing response",
            f"Existing response\n\n{CLIPBOARD_INSTRUCTION}",
        ),
        (
            f"Existing response\n\n{CLIPBOARD_INSTRUCTION}",
            f"Existing response\n\n{CLIPBOARD_INSTRUCTION}",
        ),
    ),
    ids=("empty", "existing", "already-suffixed"),
)
def test_save_copies_source_pixmap_and_appends_instruction_once(
    initial_text: str,
    expected_submission: str,
) -> None:
    """Save pixels without changing the editor and inject the instruction on ENVIAR.

    Args:
        initial_text: Composer text before the screenshot session.
         expected_submission: Exact outgoing text required after ENVIAR.

    Returns:
        None: Assertions prove pixels, hidden state, preserved text, and delivery.
    """

    app = _app()
    source = _make_source_pixmap()
    clipboard = app.clipboard()
    clipboard.setPixmap(_make_source_pixmap())
    capture = FakeCapture(source)
    factory = FakeAnnotationFactory()
    controller, window, coordinator = _build_workflow(capture, factory)
    target = _make_target("screenshot-save")

    try:
        window.open_for(target)
        window.editor.setPlainText(initial_text)
        window.status_label.setText("Keep this status until Save.")
        window.screenshot_button.click()

        editor = factory.editors[0]
        editor.accept()
        assert editor.result_calls == 1
        app.processEvents()

        copied = clipboard.pixmap()
        assert _pixmap_fingerprint(copied) == _pixmap_fingerprint(source)
        assert window.editor.toPlainText() == initial_text
        assert window._clipboard_attachment_instance_id == target.instance_id
        assert window.status_label.text() == "✓ Screenshot copied to Clipboard."
        assert window.target == target
        assert window._hold_live is True
        assert window._terminal_action_pending is False
        assert window._terminal_state == ""
        assert controller.submissions == []
        assert controller.cancellations == []
        assert coordinator._editor is None

        window.steer_button.click()

        assert controller.submissions == [
            (target, expected_submission, DeliveryMode.STEER)
        ]
        assert controller.submissions[0][1].count(CLIPBOARD_INSTRUCTION) == 1

    finally:
        _cleanup_workflow(coordinator, window)


def test_repeated_successful_saves_for_same_target_keep_one_submission_suffix() -> None:
    """Deduplicate the hidden clipboard instruction across repeated Saves.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions prove repeated same-target captures remain one suffix.
    """

    app = _app()
    source = _make_source_pixmap()
    capture = FakeCapture(source)
    factory = FakeAnnotationFactory()
    controller, window, coordinator = _build_workflow(capture, factory)
    target = _make_target("screenshot-repeat")
    original_text = "Keep this draft visible"

    try:
        window.open_for(target)
        window.editor.setPlainText(original_text)

        for _ in range(2):
            window.screenshot_button.click()
            factory.editors[-1].accept()
            app.processEvents()

            assert window.editor.toPlainText() == original_text
            assert window._clipboard_attachment_instance_id == target.instance_id

        window.steer_button.click()

        assert controller.submissions == [
            (
                target,
                f"{original_text}\n\n{CLIPBOARD_INSTRUCTION}",
                DeliveryMode.STEER,
            )
        ]
        assert controller.submissions[0][1].count(CLIPBOARD_INSTRUCTION) == 1

    finally:
        _cleanup_workflow(coordinator, window)


def test_cancel_restores_composer_without_touching_target_hold_or_clipboard() -> None:
    """Cancel without changing composer text, status, target, hold, or pixels.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions prove a local cancel has no response/task side effect.
    """

    app = _app()
    clipboard = app.clipboard()
    sentinel = _make_source_pixmap()
    clipboard.setPixmap(sentinel)
    before_clipboard = _pixmap_fingerprint(clipboard.pixmap())
    capture = FakeCapture(_make_source_pixmap())
    factory = FakeAnnotationFactory()
    controller, window, coordinator = _build_workflow(capture, factory)
    target = _make_target("screenshot-cancel")
    original_text = "Preserve this draft"
    original_status = "Original composer status"

    try:
        window.open_for(target)
        window.editor.setPlainText(original_text)
        window.status_label.setText(original_status)
        assert window._mark_clipboard_attachment(target) is True
        window.screenshot_button.click()
        factory.editors[0].reject()
        app.processEvents()

        assert window.isVisible() is True
        assert window.status_label.isVisible() is True
        assert window.editor.toPlainText() == original_text
        assert window.status_label.text() == original_status
        assert _pixmap_fingerprint(clipboard.pixmap()) == before_clipboard
        assert window.target == target
        assert window._hold_live is True
        assert window._clipboard_attachment_instance_id is None
        assert window._hold_pending is False
        assert window._terminal_action_pending is False
        assert window._terminal_state == ""
        assert controller.submissions == []
        assert controller.cancellations == []
        assert coordinator._editor is None

    finally:
        _cleanup_workflow(coordinator, window)


@pytest.mark.parametrize(
    ("capture_error", "expected_status"),
    (
        (None, "Capture unavailable."),
        (
            RuntimeError("display adapter unavailable"),
            "Screenshot capture failed: display adapter unavailable",
        ),
    ),
    ids=("null-capture", "capture-error"),
)
def test_null_or_error_capture_restores_safe_visible_state(
    capture_error: Exception | None,
    expected_status: str,
) -> None:
    """Show a visible failure without opening an editor or touching Clipboard.

    Args:
        capture_error: Optional injected exception; None produces a null pixmap.
        expected_status: Exact status label text required by the failure path.

    Returns:
        None: Assertions prove safe state and no terminal delivery.
    """

    app = _app()
    clipboard = app.clipboard()
    sentinel = _make_source_pixmap()
    clipboard.setPixmap(sentinel)
    before_clipboard = _pixmap_fingerprint(clipboard.pixmap())
    capture = FakeCapture(error=capture_error)
    factory = FakeAnnotationFactory()
    controller, window, coordinator = _build_workflow(capture, factory)
    target = _make_target("screenshot-failure")
    original_text = "Keep the composer editable"
    original_status = "Status before capture"

    try:
        window.open_for(target)
        window.editor.setPlainText(original_text)
        window.status_label.setText(original_status)
        assert window._mark_clipboard_attachment(target) is True
        window.screenshot_button.click()
        app.processEvents()

        assert window.isVisible() is True
        assert window.status_label.isVisible() is True
        assert window.status_label.text() == expected_status
        assert window.editor.toPlainText() == original_text
        assert factory.editors == []
        assert coordinator._editor is None
        assert coordinator._session is None
        assert _pixmap_fingerprint(clipboard.pixmap()) == before_clipboard
        assert window.target == target
        assert window._hold_live is True
        assert window._clipboard_attachment_instance_id is None
        assert window._terminal_action_pending is False
        assert window._terminal_state == ""
        assert controller.submissions == []

    finally:
        _cleanup_workflow(coordinator, window)


def test_stale_editor_accept_after_target_change_cannot_touch_current_editor() -> None:
    """Ignore an old Save callback after a newer target/editor owns the flow.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Assertions prove the current target/editor remain unchanged.
    """

    app = _app()
    clipboard = app.clipboard()
    sentinel = _make_source_pixmap()
    clipboard.setPixmap(sentinel)
    before_clipboard = _pixmap_fingerprint(clipboard.pixmap())
    capture = FakeCapture(_make_source_pixmap())
    factory = FakeAnnotationFactory()
    controller, window, coordinator = _build_workflow(capture, factory)
    first_target = _make_target("screenshot-old")
    current_target = _make_target("screenshot-current")

    try:
        window.open_for(first_target)
        window.editor.setPlainText("Old target draft")
        window.screenshot_button.click()
        old_editor = factory.editors[0]
        old_session = coordinator._session
        assert old_session is not None
        assert window._mark_clipboard_attachment(first_target) is True

        # Model a queued callback after the first session has been retired while
        # its modeless dialog is still alive.
        coordinator._clear_session(old_session)
        window.open_for(current_target)
        window.editor.setPlainText("Current target draft")
        window.status_label.setText("Current target status")
        window.screenshot_button.click()
        current_editor = factory.editors[1]

        old_editor.accept()
        app.processEvents()

        assert window.target == current_target
        assert window._clipboard_attachment_instance_id is None
        assert window.editor.toPlainText() == "Current target draft"
        assert window.status_label.text() == "Current target status"
        assert coordinator._editor is current_editor
        assert coordinator._session is not None
        assert coordinator._session.target == current_target
        assert current_editor.isVisible() is True
        assert _pixmap_fingerprint(clipboard.pixmap()) == before_clipboard
        assert window._hold_live is True
        assert window._terminal_action_pending is False
        assert window._terminal_state == ""
        assert controller.submissions == []

    finally:
        _cleanup_workflow(coordinator, window)


def test_coordinator_source_has_no_task_store_application_or_disk_dependencies() -> None:
    """Keep the coordinator limited to Qt, models, and injected boundaries.

    Args:
        No external arguments are accepted; pytest invokes the source scan.

    Returns:
        None: AST evidence proves direct imports and calls stay within scope.
    """

    source_path = Path(screenshot_module.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    imported_modules: list[str] = []

    for node in tree.body:

        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):
            relative_prefix = "." * node.level
            imported_modules.append(
                f"{relative_prefix}{node.module or ''}"
            )

    project_imports = [
        module for module in imported_modules if module.startswith("brain")
    ]
    forbidden_import_tokens = (
        "application",
        "controller",
        "store",
        "storage",
        "task",
    )
    forbidden_disk_modules = {
        "os",
        "pathlib",
        "shutil",
        "sqlite3",
        "tempfile",
    }

    assert project_imports == [
        "brain.presentation.avatar.communication.contracts.models"
    ]
    assert not any(
        any(token in module.casefold() for token in forbidden_import_tokens)
        for module in imported_modules
    )
    assert not any(
        module in forbidden_disk_modules for module in imported_modules
    )

    forbidden_write_names = {
        "copy",
        "makedirs",
        "mkdir",
        "move",
        "open",
        "remove",
        "rename",
        "replace",
        "rmdir",
        "unlink",
        "write",
        "write_bytes",
        "write_text",
    }
    write_calls: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue


        if isinstance(node.func, ast.Name) and node.func.id in forbidden_write_names:
            write_calls.append(node.func.id)

        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in forbidden_write_names
        ):
            write_calls.append(node.func.attr)

    assert write_calls == []
