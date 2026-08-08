"""Feature-local native metadata and document widgets for task details."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QResizeEvent, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from brain.presentation.avatar.qt.backlog.contracts.models import BacklogThemeTokens, TaskView, backlog_theme
from brain.presentation.avatar.qt.backlog.presentation.icons import STATUS_ICON_NAMES, svg_icon
from brain.presentation.avatar.qt.markdown.document import AvatarTextBrowser


class TaskMetadataBadge(QWidget):
    """One compact native badge for a single accessible task metadata field."""

    HEIGHT = 30

    def __init__(self, field_name: str, *, elides_text: bool, parent: QWidget | None = None) -> None:
        """Initialize an icon-and-text metadata badge.

        Args:
            field_name: Human-readable field name used for accessibility.
            elides_text: Whether available width should elide the visible value.
            parent: Optional owning widget.
        """
        super().__init__(parent)
        self._field_name = field_name
        self._elides_text = elides_text
        self._value = ""
        self._icon_name = "document"
        self._icon_color = "#21171e"
        self.setObjectName("taskMetadataBadge")
        self.setFixedHeight(self.HEIGHT)
        self.icon_label = QLabel(self)
        self.icon_label.setObjectName("taskMetadataIcon")
        self.icon_label.setFixedSize(14, 14)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label = QLabel(self)
        self.text_label.setObjectName("taskMetadataText")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.text_label.setWordWrap(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(5)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label, 1)

    def set_content(self, value: str, icon_name: str) -> None:
        """Update the visible and accessible metadata identity.

        Args:
            value: Field value to display.
            icon_name: Existing SVG registry key for this field.
        """
        self._value = value
        self._icon_name = icon_name
        identity = f"{self._field_name}: {value}"
        self.setToolTip(identity)
        self.setAccessibleName(identity)
        self.setAccessibleDescription(identity)
        self.text_label.setToolTip(identity)
        self._sync_text()
        self._sync_icon()

    def natural_width(self) -> int:
        """Return the compact width required for this badge's full value.

        Returns:
            int: Icon, spacing, margins, and unelided text width in pixels.
        """
        layout = self.layout()
        margins = layout.contentsMargins() if layout is not None else None
        horizontal_margins = margins.left() + margins.right() if margins is not None else 16
        spacing = layout.spacing() if layout is not None else 5
        text_width = self.text_label.fontMetrics().horizontalAdvance(self._value)

        return horizontal_margins + self.icon_label.width() + spacing + text_width
    def set_theme(self, theme: BacklogThemeTokens) -> None:
        """Apply active palette tokens to the badge.

        Args:
            theme: Complete active backlog theme token set.
        """
        self._icon_color = theme.text
        self.setStyleSheet(
            f"QWidget#taskMetadataBadge {{ color: {theme.text}; background: {theme.surface_alt}; "
            f"border: 1px solid {theme.border}; border-radius: 7px; }} "
            "QLabel#taskMetadataText, QLabel#taskMetadataIcon { background: transparent; border: 0; }",
        )
        self._sync_icon()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Refresh the optional domain-value elision after a resize.

        Args:
            event: Qt resize event supplying the new available geometry.
        """
        super().resizeEvent(event)
        self._sync_text()

    def _sync_icon(self) -> None:
        """Render the current existing SVG icon using the active theme foreground."""
        icon = svg_icon(self._icon_name, self._icon_color, 14)
        self.icon_label.setPixmap(icon.pixmap(QSize(14, 14)))

    def _sync_text(self) -> None:
        """Render a fixed field fully or the flexible domain field elided."""
        if not self._elides_text:
            self.text_label.setText(self._value)
            return
        self.text_label.setText(
            self.text_label.fontMetrics().elidedText(
                self._value,
                Qt.TextElideMode.ElideRight,
                max(1, self.text_label.width()),
            ),
        )


class TaskMetadataBar(QWidget):
    """Arrange compact native status, priority, and expansive domain metadata badges.

    The task identifier remains solely in the detail heading to avoid duplicated
    visual identity. Status and priority share the largest compact width their
    current content requires; domain consumes remaining bar space and uses its
    accessible elision behavior only when that space is insufficient.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the three native metadata badges.

        Args:
            parent: Optional owning widget.
        """
        super().__init__(parent)
        self.setObjectName("taskMetadataBar")
        self.status_badge = TaskMetadataBadge("Status", elides_text=False, parent=self)
        self.priority_badge = TaskMetadataBadge("Priority", elides_text=False, parent=self)
        self.domain_badge = TaskMetadataBadge("Domain", elides_text=True, parent=self)
        self.badges = (self.status_badge, self.priority_badge, self.domain_badge)
        for badge in self.badges[:2]:
            badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.domain_badge.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for badge in self.badges[:2]:
            layout.addWidget(badge)
        layout.addWidget(self.domain_badge, 1)
        self.set_theme(backlog_theme("light"))

    def set_task(self, task: TaskView) -> None:
        """Project immutable task status, priority, and domain metadata.

        Args:
            task: Selected immutable task projection.
        """
        self.status_badge.set_content(
            task.status.value,
            STATUS_ICON_NAMES.get(task.status.value, "checkSquare"),
        )
        self.priority_badge.set_content(task.priority, "pulse")
        self.domain_badge.set_content(task.domain, "sliders")
        self._synchronize_badge_widths()

    def set_theme(self, theme: BacklogThemeTokens) -> None:
        """Apply a shared active theme to every badge.

        Args:
            theme: Complete active backlog theme token set.
        """
        for badge in self.badges:
            badge.set_theme(theme)
        self._synchronize_badge_widths()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Refresh compact badge widths when the metadata bar is resized.

        Args:
            event: Qt resize event carrying the current available bar width.
        """
        super().resizeEvent(event)
        self._synchronize_badge_widths()

    def _synchronize_badge_widths(self) -> None:
        """Size status and priority equally while leaving domain layout-expanded."""
        shared_width = max(
            self.status_badge.natural_width(),
            self.priority_badge.natural_width(),
        )
        self.status_badge.setFixedWidth(shared_width)
        self.priority_badge.setFixedWidth(shared_width)


class TaskDetailDocumentView(AvatarTextBrowser):
    """Avatar Markdown view that decorates only task-detail image resources."""

    reader_viewport_resized = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the detail-local image decorator.

        Args:
            parent: Optional owning widget.
        """
        super().__init__(parent)
        self._image_border_color = QColor(backlog_theme("light").accent)

    def showEvent(self, event: QShowEvent) -> None:
        """Notify the owning panel once the task reader becomes visible.

        Args:
            event: Qt show event dispatched after the reader receives visibility.

        Returns:
            None.
        """
        super().showEvent(event)
        self.reader_viewport_resized.emit()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Notify the owning detail panel after the reader viewport resizes.

        Args:
            event: Qt resize event carrying the updated document-view geometry.

        Returns:
            None.
        """
        super().resizeEvent(event)
        self.reader_viewport_resized.emit()

    def set_theme(self, theme: BacklogThemeTokens) -> None:
        """Store the accent border color for the task document's next render.

        Args:
            theme: Active task-detail theme tokens.
        """
        self._image_border_color = QColor(theme.accent)

    def loadResource(self, resource_type: int, name: QUrl) -> object:  # noqa: N802 - Qt API
        """Keep inherited loading while drawing a two-pixel in-place accent border.

        Args:
            resource_type: Requested Qt resource type.
            name: Requested resource locator.

        Returns:
            object: Original resource type, with any image's dimensions unchanged.
        """
        resource = super().loadResource(resource_type, name)
        if not isinstance(resource, QImage) or resource.isNull():
            return resource

        bordered = resource.convertToFormat(QImage.Format.Format_ARGB32)
        painter = QPainter(bordered)
        border_pen = QPen(self._image_border_color)
        border_pen.setWidth(2)
        painter.setPen(border_pen)
        inner_border_rect = bordered.rect().adjusted(1, 1, -2, -2)
        painter.drawRect(inner_border_rect)
        painter.end()

        return bordered