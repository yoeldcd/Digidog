"""Qt avatar message bubble package."""

from brain.presentation.avatar.qt.bubble.chrome import QtBubbleChromeMixin
from brain.presentation.avatar.qt.bubble.facade import QtMarkdownBubble
from brain.presentation.avatar.qt.bubble.geometry import QtBubbleGeometryMixin, UNBOUNDED_WIDGET_HEIGHT
from brain.presentation.avatar.qt.markdown.document import (
    AvatarTextBrowser,
    normalized_image_size,
    semantic_token_ranges,
    table_column_percentages,
)
from brain.presentation.avatar.qt.markdown.rendering import render_avatar_markdown

__all__ = [
    "AvatarTextBrowser",
    "QtBubbleChromeMixin",
    "QtBubbleGeometryMixin",
    "QtMarkdownBubble",
    "UNBOUNDED_WIDGET_HEIGHT",
    "normalized_image_size",
    "render_avatar_markdown",
    "semantic_token_ranges",
    "table_column_percentages",
]
