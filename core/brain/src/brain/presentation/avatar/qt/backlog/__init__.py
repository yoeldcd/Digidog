"""Standalone native Qt backlog task-manager component."""

from brain.presentation.avatar.qt.backlog.presentation.capture import QtScreenCapture
from brain.presentation.avatar.qt.backlog.application.controller import BacklogController
from brain.presentation.avatar.qt.backlog.contracts.models import NewTaskDraft, ProjectView, TaskStatus, TaskView
from brain.presentation.avatar.qt.backlog.presentation.window import BacklogWindow

__all__ = ["BacklogController", "BacklogWindow", "NewTaskDraft", "ProjectView", "QtScreenCapture", "TaskStatus", "TaskView"]
