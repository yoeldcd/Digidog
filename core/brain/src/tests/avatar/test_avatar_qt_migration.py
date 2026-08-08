# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Compatibility test module; Qt cases live in responsibility-focused packages."""
import json
import os
from types import SimpleNamespace
from unittest.mock import call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPixmap
from PySide6.QtTest import QTest

from brain.presentation.avatar.window.backend import requested_avatar_backend, resolve_avatar_window_class
from brain.presentation.avatar.interactivity.markdown_document import (
    avatar_markdown_source,
    expand_avatar_images,
    normalize_avatar_markdown,
    render_embedded_file_blocks,
)
from brain.presentation.avatar.interactivity.reactions import AvatarReactionDTO, ReactionPhraseBag
from brain.presentation.avatar.qt.bubble import (
    QtMarkdownBubble,
    normalized_image_size,
    semantic_token_ranges,
    table_column_percentages,
)
from brain.presentation.avatar.qt.runtime import (
    QtAvatarWindow,
    bubble_position,
    bubble_vertical_lane,
    fit_avatar_frame,
    quota_reset_label,
    reply_composer_geometry,
)
from brain.presentation.avatar.tk.avatar import AvatarWindow
