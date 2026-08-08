"""Tk detached-message bubble geometry and view."""

from .geometry import (
    BUBBLE_FONT,
    bubble_required_height,
    bubble_tail_geometry,
    bubble_tail_height,
    bubble_tail_side,
    detached_bubble_position,
    detached_bubble_width,
    dialogue_markdown_blocks,
)
from .view import TkBubbleViewMixin

__all__ = [
    "BUBBLE_FONT",
    "TkBubbleViewMixin",
    "bubble_required_height",
    "bubble_tail_geometry",
    "bubble_tail_height",
    "bubble_tail_side",
    "detached_bubble_position",
    "detached_bubble_width",
    "dialogue_markdown_blocks",
]
