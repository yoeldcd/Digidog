"""Native Qt backlog presentation exports."""

from importlib import import_module

__all__ = [
    "BacklogFilterBar",
    "BacklogTaskList",
    "BacklogWindow",
    "DomainHeader",
    "QtScreenCapture",
    "STATUS_ICON_NAMES",
    "SVG_PATHS",
    "SuggestionComboBox",
    "TaskCard",
    "TaskDetailDocumentView",
    "TaskDetailPanel",
    "TaskFormDialog",
    "TaskMetadataBadge",
    "TaskMetadataBar",
    "backlog_stylesheet",
    "configure_button",
    "configure_shell_actions",
    "matches_task_search",
    "popup_stylesheet",
    "svg_icon",
    "task_date_key",
]
_EXPORTS = {
    "BacklogFilterBar": (
        "brain.presentation.avatar.qt.backlog.presentation.filters",
        "BacklogFilterBar",
    ),
    "BacklogTaskList": (
        "brain.presentation.avatar.qt.backlog.presentation.task_list",
        "BacklogTaskList",
    ),
    "BacklogWindow": (
        "brain.presentation.avatar.qt.backlog.presentation.window",
        "BacklogWindow",
    ),
    "DomainHeader": (
        "brain.presentation.avatar.qt.backlog.presentation.widgets",
        "DomainHeader",
    ),
    "QtScreenCapture": (
        "brain.presentation.avatar.qt.backlog.presentation.capture",
        "QtScreenCapture",
    ),
    "STATUS_ICON_NAMES": (
        "brain.presentation.avatar.qt.backlog.presentation.icons",
        "STATUS_ICON_NAMES",
    ),
    "SVG_PATHS": (
        "brain.presentation.avatar.qt.backlog.presentation.icons",
        "SVG_PATHS",
    ),
    "SuggestionComboBox": (
        "brain.presentation.avatar.qt.backlog.presentation.widgets",
        "SuggestionComboBox",
    ),
    "TaskCard": (
        "brain.presentation.avatar.qt.backlog.presentation.widgets",
        "TaskCard",
    ),
    "TaskDetailDocumentView": (
        "brain.presentation.avatar.qt.backlog.presentation.detail_components",
        "TaskDetailDocumentView",
    ),
    "TaskDetailPanel": (
        "brain.presentation.avatar.qt.backlog.presentation.detail",
        "TaskDetailPanel",
    ),
    "TaskMetadataBadge": (
        "brain.presentation.avatar.qt.backlog.presentation.detail_components",
        "TaskMetadataBadge",
    ),
    "TaskMetadataBar": (
        "brain.presentation.avatar.qt.backlog.presentation.detail_components",
        "TaskMetadataBar",
    ),
    "TaskFormDialog": (
        "brain.presentation.avatar.qt.backlog.presentation.form",
        "TaskFormDialog",
    ),
    "backlog_stylesheet": (
        "brain.presentation.avatar.qt.backlog.presentation.widgets",
        "backlog_stylesheet",
    ),
    "configure_button": (
        "brain.presentation.avatar.qt.backlog.presentation.icons",
        "configure_button",
    ),
    "configure_shell_actions": (
        "brain.presentation.avatar.qt.backlog.presentation.icons",
        "configure_shell_actions",
    ),
    "matches_task_search": (
        "brain.presentation.avatar.qt.backlog.presentation.filters",
        "matches_task_search",
    ),
    "popup_stylesheet": (
        "brain.presentation.avatar.qt.backlog.presentation.widgets",
        "popup_stylesheet",
    ),
    "svg_icon": (
        "brain.presentation.avatar.qt.backlog.presentation.icons",
        "svg_icon",
    ),
    "task_date_key": (
        "brain.presentation.avatar.qt.backlog.presentation.filters",
        "task_date_key",
    ),
}


def __getattr__(name: str) -> object:
    """Resolve presentation exports lazily to keep module imports acyclic."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value
