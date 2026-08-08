# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Pure geometry and text-block helpers for the Tk message bubble."""

from __future__ import annotations

import re

BUBBLE_FONT = ("Segoe UI", 12)
BUBBLE_META_FONT = ("Segoe UI", 11, "italic")
BUBBLE_BORDER = 3
BUBBLE_OUTER_PAD = 6
BUBBLE_TEXT_PAD_X = 18
BUBBLE_TEXT_PAD_Y = 12
BUBBLE_CLOSE_SIZE = 32
BUBBLE_HISTORY_HEIGHT = 28
BUBBLE_RIGHT_PAD = BUBBLE_CLOSE_SIZE + 18
BUBBLE_SCREEN_MARGIN = 18
BUBBLE_AVATAR_GAP = 18
BUBBLE_MIN_WIDTH = 520
BUBBLE_RESIZE_MIN_WIDTH = 320
BUBBLE_RESIZE_MIN_HEIGHT = 72
BUBBLE_RESIZE_HANDLE = 10


def dialogue_markdown_blocks(text: str) -> list[tuple[str, str]]:
    """Split bracket-delimited narrative metatext from spoken dialogue.

    Args:
        text (str): Rich avatar text containing dialogue and narratives.

    Returns:
        list[tuple[str, str]]: Ordered ``meta`` and ``dialogue`` text blocks.
    """
    blocks: list[tuple[str, str]] = []
    cursor = 0

    for match in re.finditer(r"\[([^\[\]]+)\]", text, flags=re.DOTALL):
        prefix = text[cursor:match.start()].strip()
        meta = " ".join(match.group(1).split())

        if prefix and not blocks and len(prefix) <= 4:
            meta = f"{prefix} {meta}"
        elif prefix:
            blocks.append(("dialogue", prefix))

        if meta:
            blocks.append(("meta", meta))

        cursor = match.end()

    remainder = text[cursor:].strip()

    if remainder:
        blocks.append(("dialogue", remainder))

    return blocks or ([("dialogue", text.strip())] if text.strip() else [])


def bubble_tail_height(width: int) -> int:
    """Calculate a bounded tail height from bubble width.

    Args:
        width (int): Bubble width in pixels.

    Returns:
        int: Tail height in pixels.
    """
    return max(14, min(28, round(width * .08)))


def bubble_required_height(width: int, text_height: int) -> int:
    """Calculate height required to contain bubble text and tail.

    Args:
        width (int): Bubble width in pixels.
        text_height (int): Measured content height in pixels.

    Returns:
        int: Required total bubble height in pixels.
    """
    return max(
        72,
        text_height
        + BUBBLE_HISTORY_HEIGHT
        + (BUBBLE_TEXT_PAD_Y * 2)
        + (bubble_tail_height(width) * 2)
        + (BUBBLE_BORDER * 2),
    )


def detached_bubble_width(screen_width: int, avatar_width: int) -> int:
    """Choose a readable detached-bubble width.

    Args:
        screen_width (int): Available screen width in pixels.
        avatar_width (int): Current avatar viewport width in pixels.

    Returns:
        int: Bounded readable bubble width.
    """
    available = max(240, screen_width - (BUBBLE_SCREEN_MARGIN * 2))
    preferred = max(BUBBLE_MIN_WIDTH, avatar_width * 3)

    return min(available, preferred, max(240, round(screen_width * .58)))


def detached_bubble_position(
    screen_size: tuple[int, int],
    avatar_bounds: tuple[int, int, int, int],
    bubble_size: tuple[int, int],
) -> tuple[int, int]:
    """Position a bubble above or below the avatar without covering it.

    Args:
        screen_size (tuple[int, int]): Screen width and height.
        avatar_bounds (tuple[int, int, int, int]): Avatar x, y, width, height.
        bubble_size (tuple[int, int]): Bubble width and height.

    Returns:
        tuple[tuple[int, int]]: Bounded bubble x and y coordinates.
    """
    screen_width, screen_height = screen_size
    avatar_x, avatar_y, avatar_width, avatar_height = avatar_bounds
    bubble_width, bubble_height = bubble_size

    x_limit = max(BUBBLE_SCREEN_MARGIN, screen_width - BUBBLE_SCREEN_MARGIN - bubble_width)
    x = max(BUBBLE_SCREEN_MARGIN, min(x_limit, avatar_x + (avatar_width - bubble_width) // 2))

    above_y = avatar_y - BUBBLE_AVATAR_GAP - bubble_height
    below_y = avatar_y + avatar_height + BUBBLE_AVATAR_GAP

    if above_y >= BUBBLE_SCREEN_MARGIN:
        y = above_y
    elif below_y + bubble_height <= screen_height - BUBBLE_SCREEN_MARGIN:
        y = below_y
    else:
        space_above = avatar_y - BUBBLE_SCREEN_MARGIN
        space_below = screen_height - BUBBLE_SCREEN_MARGIN - (avatar_y + avatar_height)
        y = (
            BUBBLE_SCREEN_MARGIN
            if space_above >= space_below
            else screen_height - BUBBLE_SCREEN_MARGIN - bubble_height
        )

    return x, max(BUBBLE_SCREEN_MARGIN, y)


def bubble_tail_side(
    bubble_bounds: tuple[int, int, int, int],
    avatar_bounds: tuple[int, int, int, int],
) -> str:
    """Resolve the bubble edge facing the avatar after either window moves.

    Args:
        bubble_bounds (tuple[int, int, int, int]): Bubble x, y, width, height.
        avatar_bounds (tuple[int, int, int, int]): Avatar x, y, width, height.

    Returns:
        str: ``top``, ``bottom``, ``left``, or ``right`` tail side.
    """
    bubble_x, bubble_y, bubble_width, bubble_height = bubble_bounds
    avatar_x, avatar_y, avatar_width, avatar_height = avatar_bounds

    delta_x = avatar_x + avatar_width / 2 - (bubble_x + bubble_width / 2)
    delta_y = avatar_y + avatar_height / 2 - (bubble_y + bubble_height / 2)

    normalized_x = delta_x / max(1, bubble_width / 2)
    normalized_y = delta_y / max(1, bubble_height / 2)

    if abs(normalized_x) > abs(normalized_y):
        return "right" if delta_x >= 0 else "left"

    return "bottom" if delta_y >= 0 else "top"


def bubble_tail_geometry(
    side: str,
    width: int,
    height: int,
    target: tuple[float, float],
) -> tuple[tuple[int, int, int, int], tuple[int, ...]]:
    """Calculate a stable body and tail pointing toward a target.

    Args:
        side (str): Resolved tail side.
        width (int): Bubble width in pixels.
        height (int): Bubble height in pixels.
        target (tuple[float, float]): Tail target coordinates in bubble space.

    Returns:
        tuple[tuple[int, int, int, int], tuple[int, ...]]: Body bounds and polygon coordinates for the tail.
    """
    tail = bubble_tail_height(width)
    body = (tail, tail, width - tail, height - tail)
    left, top, right, bottom = body

    target_x, target_y = target
    half_base = max(9, round(tail * .48))
    skew = max(7, round(tail * .55))
    pad = BUBBLE_OUTER_PAD

    if side in {"top", "bottom"}:
        tip_x = max(pad, min(width - pad, round(target_x)))
        direction = 1 if target_x >= width / 2 else -1
        base_center = max(left + half_base, min(right - half_base, tip_x - (direction * skew)))
        edge_y = top + 1 if side == "top" else bottom - 1
        tip_y = pad if side == "top" else height - pad
        points = (base_center - half_base, edge_y, base_center + half_base, edge_y, tip_x, tip_y)
    else:
        tip_y = max(pad, min(height - pad, round(target_y)))
        direction = 1 if target_y >= height / 2 else -1
        base_center = max(top + half_base, min(bottom - half_base, tip_y - (direction * skew)))
        edge_x = left + 1 if side == "left" else right - 1
        tip_x = pad if side == "left" else width - pad
        points = (edge_x, base_center - half_base, edge_x, base_center + half_base, tip_x, tip_y)

    return body, points
