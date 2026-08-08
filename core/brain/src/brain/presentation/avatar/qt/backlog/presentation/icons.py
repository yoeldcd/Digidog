"""Explorer-aligned SVG icons for the native Qt backlog."""
from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QAbstractButton, QPushButton

from brain.presentation.avatar.qt.backlog.contracts.models import (
    BacklogThemeTokens,
    TaskPriority,
    TaskStatus,
)

SVG_PATHS: dict[str, str] = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v6h-6"/>',
    "pulse": '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
    "enrich": (
        '<path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z"/>'
        '<path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>'
        '<path d="M5 14l.7 1.8 1.8.7-1.8.7L5 19l-.7-1.8-1.8-.7 1.8-.7z"/>'
    ),
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "checkSquare": '<path d="M9 11l2 2 4-5"/><rect x="4" y="4" width="16" height="16" rx="3"/>',
    "chevronRight": '<path d="m9 6 6 6-6 6"/>',
    "chevronLeft": '<path d="m15 18-6-6 6-6"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "camera": (
        '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2 2V8a2 0 0 1 2-2'
        'h4l2-3h6l2 3h4a2 0 0 1 2 2z"/>'
        '<circle cx="12" cy="13" r="4"/>'
    ),
    "search": '<circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/>',
    "messageCircle": (
        '<path d="M21 11.5a8.5 8.5 0 0 1-9 8.5 9.5 9.5 0 0 1-4-.9'
        'L3 21l1.7-4.5A8.5 8.5 0 1 1 21 11.5Z"/>'
    ),
    "copy": (
        '<rect x="8" y="8" width="11" height="11" rx="2"/>'
        '<rect x="5" y="5" width="11" height="11" rx="2"/>'
    ),
    "document": (
        '<path d="M7 3h7l4 4v14H7z"/>'
        '<path d="M14 3v5h5"/>'
        '<path d="M9 13h6M9 17h6"/>'
    ),
    "sliders": (
        '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/>'
        '<circle cx="16" cy="7" r="2"/>'
        '<circle cx="8" cy="17" r="2"/>'
    ),
    "edit": '<path d="M4 20h4l11-11-4-4L4 16z"/><path d="M13 6l4 4"/>',
    "play": '<path d="m8 5 11 7-11 7z"/>',
    "trash": (
        '<path d="M4 7h16"/><path d="M9 7V4h6v3"/>'
        '<path d="M6 7l1 14h10l1-14"/><path d="M10 11v6M14 11v6"/>'
    ),
    "save": '<path d="M5 3h12l2 2v16H5z"/><path d="M8 3v6h8"/><path d="M8 21v-7h8v7"/>',
}
"""Exact semantic paths reused from Brain Explorer's immutable icon registry."""

STATUS_ICON_NAMES = {
    "TODO": "clock",
    "WORKING": "pulse",
    "DONE": "checkSquare",
}


def _svg_pixmap(name: str, color: str, size: int) -> QPixmap:
    """Render one Explorer stroke path into a reusable pixmap.

    Args:
        name (str): SVG icon key name.
        color (str): Hex color code for stroke.
        size (int): Dimension size in pixels.

    Returns:
        QPixmap: Rendered QPixmap instance.
    """
    paths = SVG_PATHS.get(name, SVG_PATHS["checkSquare"])
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="{size}" height="{size}" fill="none" stroke="{color}" '
        'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
        f"{paths}</svg>"
    )
    pixmap = QPixmap()
    pixmap.loadFromData(svg.encode("utf-8"), "SVG")
    return pixmap


def svg_icon(
    name: str,
    color: str,
    size: int = 18,
    *,
    checked_color: str | None = None,
    disabled_color: str | None = None,
) -> QIcon:
    """Render an Explorer icon with contrast-safe checked and disabled states.

    Args:
        name (str): SVG icon key name.
        color (str): Base color string.
        size (int): Icon dimension size in pixels. Defaults to 18.
        checked_color (str | None): Color for checked state.
        disabled_color (str | None): Color for disabled state.

    Returns:
        QIcon: Configured QIcon instance.
    """
    icon = QIcon()
    icon.addPixmap(_svg_pixmap(name, color, size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(
        _svg_pixmap(name, checked_color or color, size),
        QIcon.Mode.Normal,
        QIcon.State.On,
    )
    if disabled_color is not None:
        disabled = _svg_pixmap(name, disabled_color, size)
        icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.Off)
        icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.On)
    return icon


def configure_button(
    button: QAbstractButton,
    *,
    icon_name: str,
    label: str,
    tooltip: str,
    color: str,
    icon_only: bool = False,
    size: int = 18,
    checked_color: str | None = None,
    disabled_color: str | None = None,
) -> None:
    """Apply one semantic icon plus complete visible/accessibility identity.

    Args:
        button (QAbstractButton): Target Qt button instance.
        icon_name (str): Name of SVG icon to apply.
        label (str): Text label for button.
        tooltip (str): Tooltip text string.
        color (str): Icon color string.
        icon_only (bool): If True, clear button text label. Defaults to False.
        size (int): Icon size in pixels. Defaults to 18.
        checked_color (str | None): Color for checked state.
        disabled_color (str | None): Color for disabled state.

    Returns:
        None
    """
    button.setText("" if icon_only else label)
    button.setIcon(
        svg_icon(
            icon_name,
            color,
            size,
            checked_color=checked_color,
            disabled_color=disabled_color,
        ),
    )
    button.setIconSize(QSize(size, size))
    button.setToolTip(tooltip)
    button.setAccessibleName(label)


def configure_shell_actions(
    *,
    refresh_button: QPushButton,
    add_button: QPushButton,
    capture_button: QPushButton | None,
    cancel_button: QPushButton | None,
    submit_button: QPushButton | None,
    status_buttons: Mapping[TaskStatus, QPushButton],
    priority_buttons: Mapping[TaskPriority, QPushButton],
    sort_buttons: Mapping[bool, QPushButton],
    tokens: BacklogThemeTokens,
) -> None:
    """Apply the native shell's complete icon and accessibility identities.

    Args:
        refresh_button: Button for refreshing tasks.
        add_button: Button for adding tasks.
        capture_button: Optional button for screen capture.
        cancel_button: Optional button for canceling the current operation.
        submit_button: Optional button for submitting the task form.
        status_buttons: Status filter button mapping.
        priority_buttons: Priority filter button mapping.
        sort_buttons: Sort toggle button mapping.
        tokens: Current theme token palette.

    Returns:
        None.
    """
    configure_button(
        refresh_button,
        icon_name="refresh",
        label="Refresh tasks",
        tooltip="Refresh projects and tasks",
        color=tokens.text,
        icon_only=True,
        disabled_color=tokens.muted,
    )
    configure_button(
        add_button,
        icon_name="plus",
        label="Add task",
        tooltip="Create a task in the selected project",
        color=tokens.accent_text,
        disabled_color=tokens.muted,
    )

    if capture_button is not None:
        capture_label = capture_button.text() or "Capture"
        configure_button(
            capture_button,
            icon_name="camera",
            label=capture_label,
            tooltip="Capture the screen or edit attached annotations",
            color=tokens.text,
            disabled_color=tokens.muted,
        )

    if cancel_button is not None:
        configure_button(
            cancel_button,
            icon_name="close",
            label="Cancel",
            tooltip="Discard this task draft and return to the list",
            color=tokens.text,
            disabled_color=tokens.muted,
        )

    if submit_button is not None:
        configure_button(
            submit_button,
            icon_name="checkSquare",
            label="Create",
            tooltip="Create this task",
            color=tokens.accent_text,
            disabled_color=tokens.muted,
        )

    status_labels = {
        TaskStatus.TODO: ("Todo", "Show pending tasks"),
        TaskStatus.WORKING: ("Working", "Show tasks in progress"),
        TaskStatus.DONE: ("Done", "Show completed tasks"),
    }
    status_colors = {
        TaskStatus.TODO: tokens.text,
        TaskStatus.WORKING: "#075d75" if tokens.mode == "light" else "#85e7ff",
        TaskStatus.DONE: "#195f37" if tokens.mode == "light" else "#8cebb4",
    }

    for status, button in status_buttons.items():
        label, tooltip = status_labels[status]
        icon_name = STATUS_ICON_NAMES[status.value]
        color = status_colors[status]
        configure_button(
            button,
            icon_name=icon_name,
            label=label,
            tooltip=tooltip,
            color=color,
            size=14,
            checked_color=tokens.accent_text,
            disabled_color=tokens.muted,
        )

    priority_colors = {
        TaskPriority.HIGH: "#8f1427" if tokens.mode == "light" else "#ff9ca6",
        TaskPriority.MEDIUM: "#654500" if tokens.mode == "light" else "#ffda87",
        TaskPriority.LOW: tokens.text,
    }

    for priority, button in priority_buttons.items():
        label = priority.value.title()
        tooltip = f"Show {priority.value.lower()} priority tasks"
        color = priority_colors[priority]
        configure_button(
            button,
            icon_name="pulse",
            label=label,
            tooltip=tooltip,
            color=color,
            size=14,
            checked_color=tokens.accent_text,
            disabled_color=tokens.muted,
        )

    for newest, button in sort_buttons.items():
        label = "Recientes" if newest else "Antiguos"
        tooltip = "Show newest tasks first" if newest else "Show oldest tasks first"
        configure_button(
            button,
            icon_name="clock",
            label=label,
            tooltip=tooltip,
            color=tokens.text,
            size=14,
            checked_color=tokens.accent_text,
            disabled_color=tokens.muted,
        )
