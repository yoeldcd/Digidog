"""Full-view Markdown detail and edit presentation for the Qt backlog."""

from __future__ import annotations

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPalette, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from brain.presentation.avatar.interactivity.markdown_document import (
    AVATAR_BASE_FONT_POINTS,
    avatar_document_css,
)
from brain.presentation.avatar.qt.backlog.contracts.models import (
    BacklogThemeTokens,
    TaskStatus,
    TaskView,
)
from brain.presentation.avatar.qt.backlog.presentation.detail_components import (
    TaskDetailDocumentView,
    TaskMetadataBar,
)
from brain.presentation.avatar.qt.backlog.presentation.icons import configure_button
from brain.presentation.avatar.qt.markdown.rendering import render_avatar_markdown
from brain.presentation.avatar.qt.markdown.styling import QtDocumentStylingMixin


class TaskDetailPanel(QtDocumentStylingMixin, QWidget):
    """Render one task read-only and expose contextual actions."""

    dismissed = Signal()
    start_requested = Signal(object)
    done_requested = Signal(object)
    delete_requested = Signal(object)
    edit_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the task detail panel and its action controls.

        Args:
            parent: Optional parent container widget.

        Returns:
            None.
        """
        super().__init__(parent)

        self.setObjectName("taskDetailPanel")
        self.setMinimumWidth(360)
        self._theme_mode = "light"
        self._zoom_step = 0
        self._heading_identity = "Task details"

        self.current_task: TaskView | None = None
        self._rendered_image_dimensions: dict[str, tuple[int | None, int | None]] = {}
        self._has_rendered_images = False
        self._last_applied_image_viewport: QSize | None = None
        self._image_reflow_pending = False

        self.back_button = QPushButton(self)
        self.back_button.setObjectName("detailBack")
        self.back_button.clicked.connect(self.dismissed.emit)
        self.close_button = self.back_button

        self.heading = QLabel(self._heading_identity, self)
        self.heading.setObjectName("detailHeading")
        self.heading.setWordWrap(False)

        self.edit_button = QPushButton(self)
        self.start_button = QPushButton(self)
        self.done_button = QPushButton(self)
        self.delete_button = QPushButton(self)
        self.delete_button.setProperty("destructiveAction", True)

        self.action_bar = QWidget(self)
        self.action_bar.setObjectName("detailActions")
        action_layout = QHBoxLayout(self.action_bar)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)

        self._action_buttons = (
            self.edit_button,
            self.start_button,
            self.done_button,
            self.delete_button,
        )
        for button in self._action_buttons:
            action_layout.addWidget(button)
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self.back_button)
        header.addWidget(self.heading, 1)
        header.addWidget(self.action_bar)

        self.metadata_bar = TaskMetadataBar(self)
        self.metadata_bar.setObjectName("taskDetailMetadata")

        self.document_view = TaskDetailDocumentView(self)
        self.document_view.setObjectName("taskDetailDocument")
        self.document_view.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.document_view.setOpenExternalLinks(False)
        self.document_view.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse,
        )
        self.document_view.reader_viewport_resized.connect(self._schedule_image_reflow)

        font = QFont("Arial")
        font.setPointSizeF(AVATAR_BASE_FONT_POINTS)
        self.document_view.document().setDefaultFont(font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(self.metadata_bar)
        layout.addWidget(self.document_view, 1)

        self.edit_button.clicked.connect(self._emit_edit)
        self.start_button.clicked.connect(self._emit_start)
        self.done_button.clicked.connect(self._emit_done)
        self.delete_button.clicked.connect(self._emit_delete)

    def set_task(self, task: TaskView) -> None:
        """Render a selected task and refresh its action state.

        Args:
            task: Selected immutable task view model.
        """
        self.current_task = task
        self._set_heading_identity(f"{task.task_id} - {task.title}")
        self.metadata_bar.set_task(task)
        self.start_button.setEnabled(task.status == TaskStatus.TODO)
        self.done_button.setEnabled(task.status in {TaskStatus.TODO, TaskStatus.WORKING})
        self.edit_button.setEnabled(True)
        self.delete_button.setVisible(True)
        rendered = render_avatar_markdown(self, self._description_markdown(task), task.project)
        self._rendered_image_dimensions = dict(rendered.image_dimensions)
        self._has_rendered_images = self._document_has_images()
        self._last_applied_image_viewport = None

        if self.isVisible():
            self._schedule_image_reflow()
        self._update_heading_elision()

    def set_theme(self, theme: BacklogThemeTokens) -> None:
        """Apply theme tokens while retaining avatar Markdown rendering.

        Args:
            theme: Theme token configuration object.

        Returns:
            None.
        """
        self._theme_mode = theme.mode
        self.metadata_bar.set_theme(theme)
        self.document_view.set_theme(theme)

        configure_button(
            self.back_button,
            icon_name="chevronLeft",
            label="Back to tasks",
            tooltip="Back to task list",
            color=theme.text,
            icon_only=True,
            size=18,
        )

        identities = (
            (
                self.edit_button,
                "edit",
                "Edit",
                "Edit task fields",
                theme.text,
            ),
            (
                self.start_button,
                "play",
                "Start work",
                "Move task to Working",
                theme.text,
            ),
            (
                self.done_button,
                "checkSquare",
                "Mark done",
                "Complete this task",
                theme.text,
            ),
            (
                self.delete_button,
                "trash",
                "Delete",
                "Delete this task",
                "#ffffff",
            ),
        )
        for button, icon_name, label, tooltip, color in identities:
            configure_button(
                button,
                icon_name=icon_name,
                label=label,
                tooltip=tooltip,
                color=color,
                disabled_color=theme.muted,
                size=16,
            )

        self._normalize_action_widths()

        palette = self.document_view.palette()
        for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText):
            palette.setColor(role, QColor(theme.text))

        palette.setColor(QPalette.ColorRole.Base, QColor(theme.surface))
        self.document_view.setPalette(palette)
        self.document_view.document().setDefaultStyleSheet(
            avatar_document_css(theme.mode),
        )
        self.setStyleSheet(self._panel_stylesheet(theme))

        if self.current_task is not None:
            self.set_task(self.current_task)

    def showEvent(self, event: QShowEvent) -> None:
        """Queue image sizing after the stacked detail page becomes visible.

        Args:
            event: Qt show event dispatched after the page receives visibility.

        Returns:
            None.
        """
        super().showEvent(event)
        QTimer.singleShot(0, self._schedule_image_reflow)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recompute heading and embedded image geometry after a panel resize.

        Args:
            event: Qt resize event carrying the updated geometry.

        Returns:
            None.
        """
        super().resizeEvent(event)
        self._update_heading_elision()

        if event.size() != event.oldSize() and self.isVisible():
            self._schedule_image_reflow()

    def _schedule_image_reflow(self) -> None:
        """Queue one post-layout image reflow for the latest rendered document.

        Multiple layout events are coalesced so hidden stacked-page rendering
        cannot create redundant image-format updates.

        Returns:
            None.
        """
        if not self._has_rendered_images:
            return

        if self._image_reflow_pending:
            return

        self._image_reflow_pending = True
        QTimer.singleShot(0, self._reapply_image_dimensions_after_layout)

    def _reapply_image_dimensions_after_layout(self) -> None:
        """Apply task-detail image sizing once its visible viewport is current.

        The queued invocation runs after QStackedWidget visibility and layout
        activation, avoiding dimensions captured from the hidden detail page.

        Returns:
            None.
        """
        self._image_reflow_pending = False

        if not self.isVisible():
            return

        if not self._has_rendered_images:
            return

        layout = self.layout()
        if layout is not None:
            layout.activate()

        reader_viewport = self.document_view.viewport().size()
        if reader_viewport.isEmpty():
            return

        if reader_viewport == self._last_applied_image_viewport:
            return

        self._apply_image_dimensions(self._rendered_image_dimensions)
        self._last_applied_image_viewport = reader_viewport

    def _document_has_images(self) -> bool:
        """Return whether the current document contains an embedded image.

        Returns:
            bool: True when the rendered document has at least one image format.
        """
        block = self.document_view.document().begin()

        while block.isValid():
            iterator = block.begin()

            while not iterator.atEnd():
                image_format = iterator.fragment().charFormat().toImageFormat()
                if image_format.isValid():
                    return True

                iterator += 1

            block = block.next()

        return False

    def _requested_image_dimensions(
        self,
        resolved: tuple[int | None, int | None],
        viewport: QSize,
    ) -> tuple[int | None, int | None]:
        """Expand only unrequested task-reference images to reader bounds.

        Explicit author width or height requests remain unchanged and continue
        through the shared aspect-fit calculation. This presentation-local hook
        never changes shared avatar bubble sizing behavior.

        Args:
            resolved: Width and height explicitly requested by Markdown, if any.
            viewport: Maximum usable task-reader image bounds.

        Returns:
            tuple[int | None, int | None]: Original explicit dimensions, or the
            full reader viewport for an unrequested task-detail image.
        """
        if resolved != (None, None):
            return resolved

        return viewport.width(), viewport.height()

    @staticmethod
    def _description_markdown(task: TaskView) -> str:
        """Return only selected task description Markdown and its empty fallback.

        Args:
            task: Immutable task projection supplying the source description.

        Returns:
            str: Trimmed description or the existing fallback text.
        """
        return task.description.strip() or "_No description provided._"

    def _set_heading_identity(self, identity: str) -> None:
        """Store full task identity for heading tooltip and accessibility.

        Args:
            identity: Complete ``task_id - title`` identity string.
        """
        self._heading_identity = identity
        self.heading.setToolTip(identity)
        self.heading.setAccessibleName(identity)
        self.heading.setAccessibleDescription(identity)

    def _update_heading_elision(self) -> None:
        """Fit the visible heading to its current single-line label width."""
        metrics = QFontMetrics(self.heading.font())
        self.heading.setText(
            metrics.elidedText(
                self._heading_identity,
                Qt.TextElideMode.ElideRight,
                max(1, self.heading.width()),
            ),
        )

    def _normalize_action_widths(self) -> None:
        """Set each action to the largest configured action size hint width."""
        action_width = max(button.sizeHint().width() for button in self._action_buttons)
        for button in self._action_buttons:
            button.setFixedWidth(action_width)

    @staticmethod
    def _panel_stylesheet(theme: BacklogThemeTokens) -> str:
        """Generate the panel stylesheet from theme tokens.

        Args:
            theme: Active theme token specification.

        Returns:
            str: Stylesheet definition string.
        """
        danger = "#a71935" if theme.mode == "light" else "#d93f5e"
        danger_hover = "#c92749" if theme.mode == "light" else "#f15d79"

        return f"""
            QWidget#taskDetailPanel {{
                background: {theme.surface}; border: 2px solid {theme.border}; border-radius: 10px;
            }}
            QLabel#detailHeading {{
                color: {theme.text}; background: transparent; border: 0; font: 700 11pt 'Segoe UI';
            }}
            QWidget#detailActions {{ background: transparent; border: 0; }}
            QWidget#detailActions QPushButton {{
                color: {theme.text}; background: {theme.surface_alt};
                border: 2px solid {theme.border}; border-radius: 7px; padding: 5px 8px;
                font: 700 8pt 'Segoe UI';
            }}
            QWidget#detailActions QPushButton:hover {{
                background: {theme.selected}; border-color: {theme.accent};
            }}
            QWidget#detailActions QPushButton:disabled {{
                color: {theme.muted}; background: {theme.surface}; border-color: {theme.border};
            }}
            QWidget#detailActions QPushButton[destructiveAction="true"] {{
                color: #ffffff; background: {danger}; border-color: {danger};
            }}
            QWidget#detailActions QPushButton[destructiveAction="true"]:hover {{
                background: {danger_hover}; border-color: {danger_hover};
            }}
            QPushButton#detailBack {{
                background: {theme.surface_alt};
                border: 2px solid {theme.border};
                border-radius: 7px;
                min-width: 30px; max-width: 30px; min-height: 28px; max-height: 28px; padding: 0;
            }}
            QPushButton#detailBack:hover {{
                background: {theme.selected};
                border-color: {theme.accent};
            }}
            QTextBrowser#taskDetailDocument {{
                color: {theme.text}; background: {theme.surface}; border: 1px solid {theme.border};
                border-radius: 7px; padding: 10px;
            }}
        """

    def _emit_start(self) -> None:
        """Emit start_requested for the current task.

        Returns:
            None.

        Notes:
            The method is a no-op when no task is currently selected.
        """
        if self.current_task is not None:
            self.start_requested.emit(self.current_task)

    def _emit_done(self) -> None:
        """Emit done_requested for the current task.

        Returns:
            None.

        Notes:
            The method is a no-op when no task is currently selected.
        """
        if self.current_task is not None:
            self.done_requested.emit(self.current_task)

    def _emit_delete(self) -> None:
        """Emit delete_requested for the current task.

        Returns:
            None.

        Notes:
            The method is a no-op when no task is currently selected.
        """
        if self.current_task is not None:
            self.delete_requested.emit(self.current_task)

    def _emit_edit(self) -> None:
        """Emit edit_requested for the current task.

        Returns:
            None.

        Notes:
            The method is a no-op when no task is currently selected.
        """
        if self.current_task is not None:
            self.edit_requested.emit(self.current_task)

    def _image_viewport_size(self) -> QSize:
        """Compute bounds for inline Markdown images.

        Returns:
            QSize: Maximum width and height available to an inline image.
        """
        viewport = self.document_view.viewport().size()
        width = max(48, viewport.width() - 24)
        height = max(48, viewport.height() - 24)

        return QSize(width, height)
