# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Pure geometry for Tk bottom-zone controls and meters."""

from __future__ import annotations


def playback_button_geometry(width: int, height: int) -> tuple[tuple[int, int], int]:
    """Return playback button center and radius for a canvas size.

    Args:
        width (int): Canvas width in pixels.
        height (int): Canvas height in pixels.

    Returns:
        tuple[tuple[int, int], int]: Button center coordinates and radius.
    """
    radius = max(21, min(44, round(width * .13)))
    padding = max(6, round(height * .02))

    return (width // 2, height - radius - padding), radius


def quota_ring_geometry(width: int, height: int) -> tuple[tuple[int, int], tuple[int, int], int]:
    """Return quota ring bounds and line width for a canvas size.

    Args:
        width (int): Canvas width in pixels.
        height (int): Canvas height in pixels.

    Returns:
        tuple[tuple[int, int], tuple[int, int], int]: Ring bounding box, inner bounds, and line width.
    """
    (_, play_y), play_radius = playback_button_geometry(width, height)
    former_radius = max(16, min(34, round(width * .10)))
    radius = max(13, round(former_radius * .78))
    reset_height = max(9, round(radius * .50))
    center_y = play_y + play_radius - radius - reset_height
    offset = play_radius + radius + max(4, round(width * .025))
    center_x = width // 2

    return (center_x - offset, center_y), (center_x + offset, center_y), radius


def mute_button_geometry(width: int, height: int) -> tuple[tuple[int, int], int]:
    """Return mute button center and radius for a canvas size.

    Args:
        width (int): Canvas width in pixels.
        height (int): Canvas height in pixels.

    Returns:
        tuple[tuple[int, int], int]: Button center coordinates and radius.
    """
    radius = max(10, min(16, round(width * .048)))
    padding = max(5, round(width * .025))

    return (padding + radius, height - padding - radius), radius