# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Pure geometry and color values for Qt avatar control zones."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor


def playback_geometry(width: int, height: int) -> tuple[QPointF, int]:
    """Calculate playback-control center and hit radius.

    Args:
        width (int): Overlay width in pixels.
        height (int): Overlay height in pixels.

    Returns:
        tuple[QPointF, int]: Control center and circular hit radius.
    """
    radius = max(21, min(44, round(width * .13)))
    return QPointF(width / 2, height - radius - max(6, round(height * .02))), radius

def quota_geometry(width: int, height: int) -> tuple[QPointF, QPointF, int]:
    """Calculate both quota-control centers and their shared radius.

    Args:
        width (int): Overlay width in pixels.
        height (int): Overlay height in pixels.

    Returns:
        tuple[QPointF, QPointF, int]: Left center, right center, and radius.
    """
    play_center, play_radius = playback_geometry(width, height)
    former_radius = max(16, min(34, round(width * .10)))
    radius = max(13, round(former_radius * .78))
    reset_height = max(9, round(radius * .50))
    center_y = play_center.y() + play_radius - radius - reset_height
    offset = play_radius + radius + max(4, round(width * .025))
    return QPointF(width / 2 - offset, center_y), QPointF(width / 2 + offset, center_y), radius

def mute_geometry(width: int, height: int) -> tuple[QPointF, int]:
    """Calculate mute-control center and hit radius.

    Args:
        width (int): Overlay width in pixels.
        height (int): Overlay height in pixels.

    Returns:
        tuple[QPointF, int]: Control center and circular hit radius.
    """
    radius = max(10, min(16, round(width * .048)))
    padding = max(5, round(width * .025))
    return QPointF(padding + radius, height - padding - radius), radius

def chrome_geometry(width: int, height: int) -> tuple[QRectF, QRectF, QRectF]:
    """Calculate pin, message, and resize-chrome bounds.

    Args:
        width (int): Overlay width in pixels.
        height (int): Overlay height in pixels.

    Returns:
        tuple[QRectF, QRectF, QRectF]: Pin, message, and resize rectangles.
    """
    size = max(32, min(46, round(width * .16)))
    message_size = round(size * 1.05)
    grip_size = max(22, min(38, round(width * .12)))
    pad = max(4, round(width * .025))
    return (
        QRectF(pad, pad, size, size),
        QRectF(width - pad - message_size, pad - 3, message_size, message_size),
        QRectF(width - grip_size, height - grip_size, grip_size, grip_size),
    )

def backlog_geometry(width: int, height: int) -> QRectF:
    """Place the backlog clock directly below the message control.

    Args:
        width (int): Overlay width in pixels.
        height (int): Overlay height in pixels.

    Returns:
        QRectF: Calculated bounding rectangle for the backlog action control.
    """
    _pin, message, _grip = chrome_geometry(width, height)
    size = max(24, round(message.width() * 0.68))
    return QRectF(
        message.center().x() - size / 2,
        message.bottom() + 6,
        size,
        size,
    )


def capture_geometry(width: int, height: int) -> QRectF:
    """Place the screenshot capture control directly below the pin.

    Args:
        width (int): Overlay width in pixels.
        height (int): Overlay height in pixels.

    Returns:
        QRectF: Calculated bounding rectangle for the capture action control.
    """
    pin, _message, _grip = chrome_geometry(width, height)
    size = max(24, round(pin.width() * 0.68))
    return QRectF(pin.center().x() - size / 2, pin.bottom() + 6, size, size)


def quota_color(used_percent: int) -> QColor:
    """Resolve a quota color from consumed percentage.

    Args:
        used_percent (int): Consumed quota percentage.

    Returns:
        QColor: Semantic usage color.
    """
    if used_percent >= 75:
        return QColor("#ff4f64")
    if used_percent >= 50:
        return QColor("#ff982f")
    if used_percent >= 25:
        return QColor("#f1d447")
    return QColor("#36c978")

def pin_fill_color(pinned: bool) -> QColor:
    """Resolve the pin icon fill color.

    Args:
        pinned (bool): Whether the avatar window is pinned.

    Returns:
        QColor: Pin fill color for the current state.
    """
    return QColor("#3b8cff") if pinned else QColor("#f8fbff")
