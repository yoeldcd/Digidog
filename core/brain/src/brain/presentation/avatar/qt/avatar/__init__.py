"""Qt avatar rendering and geometry package."""

from brain.presentation.avatar.qt.avatar.geometry import (
    QtWindowGeometryMixin,
    bubble_position,
    bubble_vertical_lane,
    clamp_bubble_position,
    reply_composer_geometry,
)
from brain.presentation.avatar.qt.avatar.renderer import QtAvatarRendererMixin, fit_avatar_frame

__all__ = [
    "QtAvatarRendererMixin",
    "QtWindowGeometryMixin",
    "bubble_position",
    "bubble_vertical_lane",
    "clamp_bubble_position",
    "fit_avatar_frame",
    "reply_composer_geometry",
]
