"""Standalone modeless Qt task form dialog."""
from __future__ import annotations

from functools import partial
from typing import Literal

from PySide6.QtCore import (
    QAbstractAnimation,
    QByteArray,
    QBuffer,
    QIODevice,
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QCloseEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from brain.presentation.avatar.qt.backlog.annotation import AnnotationDialog
from brain.presentation.avatar.qt.backlog.contracts.models import (
    BacklogThemeTokens,
    EditTaskDraft,
    NewTaskDraft,
    TaskEditSource,
    TaskEnrichmentDraft,
    TaskEnrichmentResult,
    TaskPriority,
    backlog_theme,
)
from brain.presentation.avatar.qt.backlog.contracts.ports import (
    CapturePort,
    TaskDraftEnrichmentPort,
)
from brain.presentation.avatar.qt.backlog.presentation.enrichment import EnrichmentRunner
from brain.presentation.avatar.qt.backlog.presentation.icons import configure_button
from brain.presentation.avatar.qt.backlog.presentation.widgets import (
    SuggestionComboBox,
    popup_stylesheet,
)


FormMode = Literal["add", "edit"]


class TaskFormDialog(QDialog):
    """Own one independent, modeless add/edit form and capture lifecycle."""

    create_requested = Signal(object)
    edit_requested = Signal(object)
    cancelled = Signal()

    def __init__(
        self,
        project: str | None = None,
        edit_source: TaskEditSource | None = None,
        capture: CapturePort | None = None,
        parent: QWidget | None = None,
        theme: BacklogThemeTokens | str = "light",
        mode: FormMode | None = None,
        enricher: TaskDraftEnrichmentPort | None = None,
    ) -> None:
        """Initialize the form and optionally prepopulate it from RAW task data.

        Args:
            project: Workspace key used by a new task.
            edit_source: Persisted RAW task fields and reference bytes for edit mode.
            capture: Optional screenshot provider for adding or replacing a reference.
            parent: Optional Qt owner of this top-level dialog.
            theme: Theme tokens or a supported avatar theme name.
            mode: Optional explicit mode that must match edit-source presence.
            enricher: Optional presentation port that generates unsaved descriptions.

        Returns:
            None.

        Raises:
            ValueError: If add mode has no project or mode disagrees with edit source presence.
        """
        super().__init__(parent)

        inferred_mode: FormMode = "edit" if edit_source is not None else "add"
        if mode is not None and mode != inferred_mode:
            raise ValueError("mode must match whether edit source is provided")

        if edit_source is None and not project:
            raise ValueError("project is required for add mode")

        self.project: str = project or (
            edit_source.project if edit_source is not None else ""
        )
        self.edit_source: TaskEditSource | None = edit_source
        self.mode: FormMode = inferred_mode
        self.capture: CapturePort | None = capture
        self.enricher: TaskDraftEnrichmentPort | None = enricher
        self.theme_tokens: BacklogThemeTokens = backlog_theme("light")
        self._capture_pixmap = self._pixmap_from_png(
            None if edit_source is None else edit_source.reference_png,
        )
        self._annotation_editor: AnnotationDialog | None = None
        self._error_message: QMessageBox | None = None
        self._cancel_emitted = False
        self._owner_accepting = False
        self._enrichment_runner: EnrichmentRunner | None = None
        self._enrichment_generation = 0
        self._enrichment_slots: dict[EnrichmentRunner, tuple[object | None, ...]] = {}
        self._retired_enrichment_runners: list[EnrichmentRunner] = []
        self._enrichment_active = False
        self._description_opacity_effect: QGraphicsOpacityEffect | None = None
        self._description_fade_animation: QPropertyAnimation | None = None

        self.setObjectName("taskFormDialog")
        self.setWindowTitle("Edit task" if self.mode == "edit" else "Create task")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint,
        )
        self.setModal(False)
        self.setMinimumSize(560, 520)

        self._build_form()
        self._populate_task(edit_source)
        self._connect_events()
        self.set_theme(theme)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def _build_form(self) -> None:
        """Create the fields and actions owned by the form."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 18, 22, 20)
        root_layout.setSpacing(8)

        heading_layout = QHBoxLayout()
        heading_layout.setSpacing(8)

        heading = QLabel(self.windowTitle(), self)
        heading.setObjectName("formHeading")
        heading_layout.addWidget(heading, 1)

        self.enrich_button = QPushButton("Enrich", self)
        self.enrich_button.setObjectName("enrichButton")
        heading_layout.addWidget(self.enrich_button)
        root_layout.addLayout(heading_layout)

        domain_priority_layout = QHBoxLayout()
        domain_layout = QVBoxLayout()
        domain_layout.addWidget(QLabel("Domain", self))

        self.domain_input = SuggestionComboBox(self)
        self.domain_input.setObjectName("domainInput")
        self.domain_input.setAccessibleName("Task domain")
        self.domain_input.setToolTip("Type domain levels separated by dots")
        self.domain_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        domain_layout.addWidget(self.domain_input)

        priority_layout = QVBoxLayout()
        priority_layout.addWidget(QLabel("Priority", self))

        self.priority_selector = QComboBox(self)
        self.priority_selector.setObjectName("prioritySelector")
        self.priority_selector.setAccessibleName("Task priority")
        self.priority_selector.setToolTip("Choose task priority")
        self.priority_selector.addItems(
            [priority.value for priority in TaskPriority],
        )
        self.priority_selector.setFixedWidth(132)
        priority_layout.addWidget(self.priority_selector)

        domain_priority_layout.addLayout(domain_layout, 1)
        domain_priority_layout.addLayout(priority_layout)
        root_layout.addLayout(domain_priority_layout)

        root_layout.addWidget(QLabel("Title", self))
        self.title_input = QLineEdit(self)
        self.title_input.setObjectName("titleInput")
        self.title_input.setAccessibleName("Task title")
        root_layout.addWidget(self.title_input)

        root_layout.addWidget(QLabel("Description", self))
        self.description_input = QTextEdit(self)
        self.description_input.setObjectName("descriptionInput")
        self.description_input.setAccessibleName("Task description")
        self.description_input.setPlaceholderText(
            "Markdown is supported in task details",
        )
        root_layout.addWidget(self.description_input, 1)
        self._setup_description_fade_animation()

        self.capture_heading = QLabel("Screenshot", self)
        root_layout.addWidget(self.capture_heading)

        capture_layout = QHBoxLayout()
        self.capture_button = QPushButton("Capture", self)
        self.capture_button.setObjectName("captureButton")
        self.capture_label = QLabel("No capture", self)
        self.capture_label.setObjectName("captureState")
        capture_layout.addWidget(self.capture_button)
        capture_layout.addWidget(self.capture_label, 1)
        root_layout.addLayout(capture_layout)

        actions_layout = QHBoxLayout()
        actions_layout.addStretch(1)

        self.cancel_button = QPushButton("Cancel", self)
        self.submit_button = QPushButton(
            "Save" if self.mode == "edit" else "Create",
            self,
        )
        self.submit_button.setProperty("primaryAction", True)
        actions_layout.addWidget(self.cancel_button)
        actions_layout.addWidget(self.submit_button)
        root_layout.addLayout(actions_layout)

    def _connect_events(self) -> None:
        """Connect controls to local form actions."""
        self.capture_button.clicked.connect(self.capture_screenshot)
        self.cancel_button.clicked.connect(self.reject)
        self.enrich_button.clicked.connect(self.toggle_enrichment)
        self.submit_button.clicked.connect(self.submit_task)

    def _populate_task(self, source: TaskEditSource | None) -> None:
        """Populate controls from RAW edit data or establish add-mode defaults."""
        if source is None:
            self.priority_selector.setCurrentText(TaskPriority.MEDIUM.value)
            return

        self.domain_input.setText(source.domain)
        self.title_input.setText(source.title)
        self.description_input.setPlainText(source.raw_description)
        self.priority_selector.setCurrentText(str(source.priority).upper())
        self._sync_capture_state()

    def set_domain_suggestions(
        self,
        suggestions: tuple[str, ...],
    ) -> None:
        """Replace domain completion candidates without changing typed text.

        Args:
            suggestions: Project-local hierarchical domain candidates.

        Returns:
            None.
        """
        self.domain_input.set_suggestions(suggestions)

    def set_theme(
        self,
        theme: BacklogThemeTokens | str,
    ) -> None:
        """Apply theme tokens to the form and its popup controls.

        Args:
            theme: Theme tokens or a supported avatar theme name.

        Returns:
            None.
        """
        tokens = backlog_theme(theme) if isinstance(theme, str) else theme
        self.theme_tokens = tokens
        self.setProperty("avatarTheme", tokens.mode)
        self.setStyleSheet(self._form_stylesheet(tokens))
        self._apply_combo_popup_theme(tokens)
        self._sync_capture_state()
        self._sync_enrich_button()
        self._set_description_fade_active(self._enrichment_active)

    @staticmethod
    def _form_stylesheet(
        tokens: BacklogThemeTokens,
    ) -> str:
        """Build the local stylesheet from shared theme tokens.

        Args:
            tokens: Colors inherited from the avatar theme.

        Returns:
            str: Stylesheet scoped to this dialog.
        """
        return f"""
            QDialog#taskFormDialog {{
                background: {tokens.background};
                color: {tokens.text};
            }}
            QDialog#taskFormDialog QLabel {{
                color: {tokens.text};
            }}
            QLabel#formHeading {{
                color: {tokens.accent};
                background: {tokens.surface_alt};
                border-left: 5px solid {tokens.accent};
                border-radius: 7px;
                padding: 9px 12px;
                font: 700 14pt 'Segoe UI';
            }}
            QDialog#taskFormDialog QLineEdit,
            QDialog#taskFormDialog QTextEdit,
            QDialog#taskFormDialog QComboBox {{
                color: {tokens.text};
                background: {tokens.surface};
                border: 1px solid {tokens.border};
                border-radius: 6px;
                padding: 5px;
            }}
            QDialog#taskFormDialog QPushButton {{
                color: {tokens.text};
                background: {tokens.surface_alt};
                border: 1px solid {tokens.border};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QDialog#taskFormDialog QPushButton[primaryAction="true"] {{
                color: #ffffff;
                background: {tokens.accent};
                border-color: {tokens.accent};
            }}
            QDialog#taskFormDialog QPushButton#enrichButton {{
                color: {tokens.accent_text};
                background: {tokens.accent};
                border-color: {tokens.accent};
            }}
            QDialog#taskFormDialog QPushButton#enrichButton:hover {{
                color: {tokens.accent_text};
                background: {tokens.accent_hover};
                border-color: {tokens.accent_hover};
            }}
            QDialog#taskFormDialog QPushButton#enrichButton[enrichmentActive="true"] {{
                color: {tokens.accent_text};
                background: {tokens.accent};
                border-color: {tokens.accent};
            }}
            QLabel#captureState {{
                color: {tokens.muted};
            }}
        """

    def _apply_combo_popup_theme(
        self,
        tokens: BacklogThemeTokens,
    ) -> None:
        """Apply the shared high-contrast style to combo popups.

        Args:
            tokens: Colors inherited from the avatar theme.

        Returns:
            None.
        """
        popup_style = popup_stylesheet(tokens)
        self.priority_selector.view().setStyleSheet(popup_style)
        self.domain_input.view().setStyleSheet(popup_style)

        completer = self.domain_input.completer()
        if completer is not None:
            completer.popup().setStyleSheet(popup_style)

    def show_error(
        self,
        error: ValueError,
    ) -> None:
        """Show validation feedback while retaining the open form.

        Args:
            error: Validation failure to present to the user.

        Returns:
            None.
        """
        current_message = self._error_message
        if current_message is not None:
            self._error_message = None
            current_message.close()
            current_message.deleteLater()

        message = QMessageBox(self)
        message.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("Cannot save task")
        message.setText(str(error))
        message.setStandardButtons(QMessageBox.StandardButton.Ok)
        message.finished.connect(
            partial(self._release_error_message, message),
        )

        self._error_message = message
        message.show()

    def _release_error_message(
        self,
        message: QMessageBox,
        _result: int,
    ) -> None:
        """Clear the retained validation message after it finishes."""
        if self._error_message is message:
            self._error_message = None

    def submit_task(self) -> None:
        """Validate and emit the mode-specific DTO without closing the dialog.

        Returns:
            None.
        """
        try:
            draft = self._build_draft()
        except ValueError as error:
            self.show_error(error)
            return

        if self.mode == "edit":
            self.edit_requested.emit(draft)
            return

        self.create_requested.emit(draft)

    def toggle_enrichment(self) -> None:
        """Start enrichment or cooperatively cancel the active request."""
        if self._enrichment_active:
            self._cancel_enrichment()
            return

        self._start_enrichment()

    def enrich_task(self) -> None:
        """Public alias for :meth:`toggle_enrichment` used by integrations."""
        self.toggle_enrichment()

    def cancel_enrichment(self) -> None:
        """Cancel the active request and restore controls immediately."""
        self._cancel_enrichment()

    def _start_enrichment(self) -> None:
        """Capture current fields and run the blocking port off the GUI thread."""
        enricher = self.enricher
        if enricher is None:
            return

        try:
            draft = self._build_enrichment_draft()
        except ValueError as error:
            self.show_error(error)
            return

        self._enrichment_generation += 1
        generation = self._enrichment_generation
        runner = EnrichmentRunner(enricher)
        result_slot = partial(self._on_enrichment_result, generation, runner)
        error_slot = partial(self._on_enrichment_error, generation, runner)
        finished_slot = partial(self._on_enrichment_finished, runner)
        runner.succeeded.connect(result_slot)
        runner.failed.connect(error_slot)
        runner.finished.connect(finished_slot)
        self._enrichment_slots[runner] = (
            result_slot,
            error_slot,
            finished_slot,
        )
        self._enrichment_runner = runner
        self._set_enrichment_active(True)

        try:
            runner.start(draft)
        except Exception as error:  # noqa: BLE001 - restore UI for port startup failures.
            self._disconnect_enrichment_runner(runner)
            self._enrichment_runner = None
            self._set_enrichment_active(False)
            self.show_error(ValueError(str(error) or error.__class__.__name__))

    def _cancel_enrichment(self, *, disconnect_finished: bool = False) -> None:
        """Request cancellation, invalidate callbacks, and restore the form now.

        Args:
            disconnect_finished: Whether to remove the final cleanup callback,
                used when the form itself is closing.
        """
        runner = self._enrichment_runner
        self._enrichment_generation += 1
        self._enrichment_runner = None

        if runner is not None:
            runner.cancel()
            if runner not in self._retired_enrichment_runners:
                self._retired_enrichment_runners.append(runner)
            self._disconnect_enrichment_runner(runner, include_finished=disconnect_finished)

        self._set_enrichment_active(False)

    def _build_enrichment_draft(self) -> TaskEnrichmentDraft:
        """Map current controls into the immutable enrichment request DTO.

        Returns:
            TaskEnrichmentDraft: Current fields and optional in-memory PNG bytes.

        Raises:
            ValueError: If a required task identity field is empty.
        """
        domain = self.domain_input.text().strip()
        title = self.title_input.text().strip()
        priority = self.priority_selector.currentText().strip()
        description = self.description_input.toPlainText().strip()

        if not domain:
            raise ValueError("Task domain is required")

        if not title:
            raise ValueError("Task title is required")

        if not priority:
            raise ValueError("Task priority is required")

        return TaskEnrichmentDraft(
            domain=domain,
            title=title,
            priority=priority,
            description=description,
            reference_png=self._pixmap_png(self._capture_pixmap),
        )

    def _on_enrichment_result(
        self,
        generation: int,
        runner: EnrichmentRunner,
        result: object,
    ) -> None:
        """Apply only the current request's description proposal."""
        if generation != self._enrichment_generation:
            return

        if runner is not self._enrichment_runner:
            return

        description = (
            result.description
            if isinstance(result, TaskEnrichmentResult)
            else getattr(result, "description", None)
        )
        if not isinstance(description, str) or not description.strip():
            self._on_enrichment_error(
                generation,
                runner,
                ValueError("Task enrichment returned an empty description"),
            )
            return

        self.description_input.setPlainText(description)
        self._complete_enrichment(runner)

    def _on_enrichment_error(
        self,
        generation: int,
        runner: EnrichmentRunner,
        error: object,
    ) -> None:
        """Restore controls and surface a current request's failure."""
        if generation != self._enrichment_generation:
            return

        if runner is not self._enrichment_runner:
            return

        message = str(error).strip() or error.__class__.__name__
        self._complete_enrichment(runner)
        self.show_error(ValueError(message))

    def _complete_enrichment(self, runner: EnrichmentRunner) -> None:
        """Restore controls after success or failure while keeping thread cleanup natural."""
        if runner is not self._enrichment_runner:
            return

        self._enrichment_generation += 1
        self._enrichment_runner = None
        self._disconnect_enrichment_runner(runner, include_finished=False)
        if runner not in self._retired_enrichment_runners:
            self._retired_enrichment_runners.append(runner)
        self._set_enrichment_active(False)

    def _on_enrichment_finished(self, runner: EnrichmentRunner) -> None:
        """Release callbacks and retained runner references after thread shutdown."""
        self._disconnect_enrichment_runner(runner)
        if runner in self._retired_enrichment_runners:
            self._retired_enrichment_runners.remove(runner)

    def _disconnect_enrichment_runner(
        self,
        runner: EnrichmentRunner,
        *,
        include_finished: bool = True,
    ) -> None:
        """Disconnect runner callbacks idempotently across close and cancel paths."""
        slots = self._enrichment_slots.get(runner)
        if slots is None:
            return

        signals = (runner.succeeded, runner.failed, runner.finished)
        last_index = 3 if include_finished else 2
        for signal, slot in zip(signals[:last_index], slots[:last_index]):
            if slot is None:
                continue
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

        if include_finished:
            self._enrichment_slots.pop(runner, None)
            return

        self._enrichment_slots[runner] = (None, None, slots[2])

    def _set_enrichment_active(self, active: bool) -> None:
        """Enable or disable controls and synchronize enrichment presentation state.

        Args:
            active: Whether a worker request currently owns the form controls.

        Returns:
            None.
        """
        self._enrichment_active = active
        enabled = not active
        for control in (
            self.domain_input,
            self.title_input,
            self.priority_selector,
            self.description_input,
            self.cancel_button,
            self.submit_button,
        ):
            control.setEnabled(enabled)

        self._sync_capture_state()
        self._sync_enrich_button()
        self._set_description_fade_active(active)

    def _setup_description_fade_animation(self) -> None:
        """Install the repeating opacity animation on the complete description field.

        Returns:
            None.
        """
        effect = QGraphicsOpacityEffect(self.description_input)
        effect.setOpacity(1.0)
        self.description_input.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(900)
        animation.setStartValue(1.0)
        animation.setKeyValueAt(0.5, 0.42)
        animation.setEndValue(1.0)
        animation.setLoopCount(-1)
        animation.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._description_opacity_effect = effect
        self._description_fade_animation = animation

    def _set_description_fade_active(self, active: bool) -> None:
        """Start or stop the whole-field fade and restore full opacity when idle.

        Args:
            active: Whether enrichment is running and the field should fade.

        Returns:
            None.
        """
        effect = self._description_opacity_effect
        animation = self._description_fade_animation
        if effect is None or animation is None:
            return

        if active:
            if animation.state() != QAbstractAnimation.State.Running:
                effect.setOpacity(1.0)
                animation.start()
            return

        animation.stop()
        effect.setOpacity(1.0)

    def _sync_enrich_button(self) -> None:
        """Apply the Explorer icon and label for idle, active, and unavailable states."""
        active = self._enrichment_active
        configure_button(
            self.enrich_button,
            icon_name="pause" if active else "enrich",
            label="Cancel" if active else "Enrich",
            tooltip=(
                "Cancel description enrichment"
                if active
                else "Generate an unsaved task description proposal"
            ),
            color=self.theme_tokens.accent_text,
            disabled_color=self.theme_tokens.muted,
        )
        self.enrich_button.setProperty("enrichmentActive", active)
        self.enrich_button.setEnabled(active or self.enricher is not None)
        style = self.enrich_button.style()
        if style is not None:
            style.unpolish(self.enrich_button)
            style.polish(self.enrich_button)

    def _build_draft(
        self,
    ) -> NewTaskDraft | EditTaskDraft:
        """Map current controls into one validated immutable DTO.

        Returns:
            NewTaskDraft or EditTaskDraft: DTO matching the current form mode.

        Raises:
            ValueError: If domain, title, or priority is empty.
        """
        domain = self.domain_input.text().strip()
        title = self.title_input.text().strip()
        description = self.description_input.toPlainText().strip()
        priority = self.priority_selector.currentText().strip()

        if not domain:
            raise ValueError("Task domain is required")

        if not title:
            raise ValueError("Task title is required")

        if not priority:
            raise ValueError("Task priority is required")

        screenshot_png = self._pixmap_png(self._capture_pixmap)
        if self.mode == "edit":
            source = self.edit_source
            assert source is not None
            return EditTaskDraft(
                project=self.project,
                task_id=source.task_id,
                domain=domain,
                title=title,
                description=description,
                priority=priority,
                screenshot_png=screenshot_png,
            )

        return NewTaskDraft(
            project=self.project,
            domain=domain,
            title=title,
            description=description,
            priority=priority,
            screenshot_png=screenshot_png,
        )

    @staticmethod
    def _pixmap_from_png(content: bytes | None) -> QPixmap:
        """Decode optional persisted PNG bytes into an isolated pixmap.

        Args:
            content: Canonical reference bytes loaded by the composition boundary.

        Returns:
            QPixmap: Decoded image, or a null pixmap when no reference exists.
        """
        pixmap = QPixmap()
        if content is not None:
            pixmap.loadFromData(content, "PNG")

        return pixmap

    def capture_screenshot(self) -> None:
        """Capture a source image or reveal the current annotation editor.

        Returns:
            None.
        """
        editor = self._annotation_editor

        if editor is not None:
            editor.show()
            editor.raise_()
            editor.activateWindow()
            return

        pixmap = self._capture_pixmap
        if pixmap.isNull():
            capture_port = self.capture
            if capture_port is None:
                return

            pixmap = capture_port.capture()

        if pixmap.isNull():
            self.capture_label.setText("Capture unavailable")
            return

        self._open_annotation_editor(pixmap)

    def _open_annotation_editor(
        self,
        pixmap: QPixmap,
    ) -> None:
        """Create and display the modeless annotation editor.

        Args:
            pixmap: Source-resolution image to annotate.

        Returns:
            None.
        """
        editor = AnnotationDialog(
            pixmap,
            self,
            theme=self.theme_tokens,
        )
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        editor.accepted.connect(
            partial(self._accept_annotations, editor),
        )
        editor.finished.connect(
            partial(self._release_annotation_editor, editor),
        )
        editor.destroyed.connect(
            partial(self._release_annotation_editor, editor),
        )
        self._annotation_editor = editor
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _accept_annotations(
        self,
        editor: AnnotationDialog,
    ) -> None:
        """Store the accepted annotated image belonging to this form.

        Args:
            editor: Annotation editor that produced the result.

        Returns:
            None.
        """
        if editor is not self._annotation_editor:
            return

        self._capture_pixmap = editor.result_pixmap()
        self._sync_capture_state()

    def _release_annotation_editor(
        self,
        editor: AnnotationDialog,
        _result: object | None = None,
    ) -> None:
        """Clear a finished annotation editor reference safely.

        Args:
            editor: Annotation editor whose lifecycle event fired.
            _result: Finished or destroyed signal payload.

        Returns:
            None.
        """
        if editor is self._annotation_editor:
            self._annotation_editor = None

    def _close_annotation_editor(self) -> None:
        """Close and release the annotation editor idempotently."""
        editor = self._annotation_editor
        self._annotation_editor = None

        if editor is None:
            return

        editor.close()
        editor.deleteLater()

    def _sync_capture_state(self) -> None:
        """Update capture controls and attachment status for the active mode."""
        has_capture = not self._capture_pixmap.isNull()
        can_open_annotations = has_capture or self.capture is not None

        self.capture_heading.setVisible(True)
        self.capture_button.setVisible(True)
        self.capture_label.setVisible(True)
        self.capture_button.setEnabled(can_open_annotations and not self._enrichment_active)

        label = "Edit annotations" if has_capture else "Capture"
        tooltip = (
            "Edit screenshot annotations"
            if has_capture
            else "Capture a screenshot"
        )
        configure_button(
            self.capture_button,
            icon_name="camera",
            label=label,
            tooltip=tooltip,
            color=self.theme_tokens.text,
            disabled_color=self.theme_tokens.muted,
        )
        self.capture_label.setText(
            "Capture attached" if has_capture else "No capture",
        )

    def accept(self) -> None:
        """Close after the owner confirms a successful controller operation.

        Returns:
            None.
        """
        self._owner_accepting = True
        self._cancel_enrichment(disconnect_finished=True)
        self._close_annotation_editor()
        super().accept()

    def reject(self) -> None:
        """Cancel safely and emit cancelled once.

        Returns:
            None.
        """
        self._cancel_enrichment(disconnect_finished=True)
        self._close_annotation_editor()
        self._emit_cancelled()
        super().reject()

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """Treat native close as cancellation unless owner-approved.

        Args:
            event: Qt close event delivered to this dialog.

        Returns:
            None.
        """
        self._cancel_enrichment(disconnect_finished=True)
        self._close_annotation_editor()

        if not self._owner_accepting:
            self._emit_cancelled()

        super().closeEvent(event)

    def _emit_cancelled(self) -> None:
        """Emit the cancellation signal at most once."""
        if self._cancel_emitted:
            return

        self._cancel_emitted = True
        self.cancelled.emit()

    @staticmethod
    def _pixmap_png(
        pixmap: QPixmap,
    ) -> bytes | None:
        """Encode a pixmap as PNG bytes, or return None for a null pixmap.

        Args:
            pixmap: Image to encode.

        Returns:
            bytes or None: PNG bytes for a non-null image.
        """
        if pixmap.isNull():
            return None

        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        buffer.close()
        return bytes(data)
