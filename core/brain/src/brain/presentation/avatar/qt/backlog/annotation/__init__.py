"""Compatibility facade for the native Qt backlog annotation editor."""

from brain.presentation.avatar.qt.backlog.annotation.canvas import AnnotationCanvas
from brain.presentation.avatar.qt.backlog.annotation.sidebar import AnnotationSidebar
from brain.presentation.avatar.qt.backlog.annotation.dialog import AnnotationDialog
from brain.presentation.avatar.qt.backlog.annotation.models import (
    ANNOTATION_PALETTE,
    ANNOTATION_TOOLS,
    AnnotationMark,
)

__all__ = [
    "ANNOTATION_PALETTE",
    "ANNOTATION_TOOLS",
    "AnnotationCanvas",
    "AnnotationSidebar",
    "AnnotationDialog",
    "AnnotationMark",
]
