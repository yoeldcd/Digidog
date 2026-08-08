# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Detached Tk message-bubble view and pointer interactions."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from brain.presentation.avatar.interactivity.emotions import emotion_emoji
from brain.presentation.avatar.tk.bubble.geometry import (
    BUBBLE_BORDER, BUBBLE_FONT, BUBBLE_HISTORY_HEIGHT, BUBBLE_META_FONT, BUBBLE_RESIZE_HANDLE,
    BUBBLE_RESIZE_MIN_HEIGHT, BUBBLE_RESIZE_MIN_WIDTH, BUBBLE_RIGHT_PAD,
    BUBBLE_SCREEN_MARGIN, BUBBLE_TEXT_PAD_X, BUBBLE_TEXT_PAD_Y,
    bubble_required_height, bubble_tail_geometry, bubble_tail_height, bubble_tail_side,
    detached_bubble_position, detached_bubble_width, dialogue_markdown_blocks,
)


class TkBubbleViewMixin:
    """Own detached bubble drawing, sizing, dragging, and dismissal.

    Attributes:
        bubble (tk.Canvas): Canvas rendering message bubble and controls.
        bubble_root (tk.Toplevel): Detached rich-message window.
        root (tk.Tk): Main transparent avatar window.
        speech_text (str): Current speech text rendered in bubble.
        message_controller (Any): History and replay controller collaborator.
        bubble_resize_active (bool): Whether bubble resize gesture is active.
        bubble_resize_origin (tuple): Parameters captured at resize start.
        bubble_manual_size (tuple[int, int] | None): Manually resized bubble dimensions.
        bubble_has_position (bool): Whether bubble has a valid position.
        bubble_drag_origin (tuple[int, int, int, int]): Coordinates captured at drag start.
        pin (tk.Button): Top-left pin button widget.
    """

    def _draw_bubble(self, _event: tk.Event | None = None) -> None:
        """Render the detached message bubble, its metadata, and its tail.

        Args:
            _event (tk.Event | None): Optional Tk event that triggered the geometry refresh.

        Returns:
            None.
        """
        width, height = self.bubble.winfo_width(), self.bubble.winfo_height()
        self.bubble.delete("all")

        if width <= 2 or height <= 2:
            return

        bubble_bounds = (self.bubble_root.winfo_x(), self.bubble_root.winfo_y(), width, height)
        avatar_bounds = (
            self.root.winfo_x(),
            self.root.winfo_y(),
            self.root.winfo_width(),
            self.root.winfo_height(),
        )

        side = bubble_tail_side(bubble_bounds, avatar_bounds)
        avatar_center = (
            avatar_bounds[0] + avatar_bounds[2] / 2 - bubble_bounds[0],
            avatar_bounds[1] + avatar_bounds[3] / 2 - bubble_bounds[1],
        )

        body, tail_points = bubble_tail_geometry(side, width, height, avatar_center)
        left, top, right, bottom = body
        radius = min(18, max(10, round(min(right - left, bottom - top) * .08)))

        self.bubble.create_polygon(tail_points, fill="#fff8fd", outline="#f062b7", width=BUBBLE_BORDER)

        points = (
            left + radius, top, right - radius, top, right, top,
            right, bottom - radius, right, bottom, left, bottom,
            left, bottom - radius, left, top + radius, left, top,
        )
        self.bubble.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill="#fff8fd",
            outline="#f062b7",
            width=3,
        )

        self._render_bubble_text(
            left + BUBBLE_TEXT_PAD_X,
            top + BUBBLE_TEXT_PAD_Y + BUBBLE_BORDER,
            max(20, right - left - BUBBLE_TEXT_PAD_X - BUBBLE_RIGHT_PAD),
        )

        self.bubble.create_oval(
            right - 28,
            top + 3,
            right - 4,
            top + 27,
            fill="#fff8fd",
            outline="",
            tags=("bubble-close", "bubble-close-hit"),
        )
        self.bubble.create_text(
            right - 16,
            top + 15,
            anchor="center",
            text="\u2715",
            fill="#111111",
            font=("Segoe UI Symbol", 13, "bold"),
            tags=("bubble-close", "bubble-close-icon"),
        )

        self.bubble.tag_bind("bubble-close", "<Enter>", lambda _event: self._bubble_close_hover(True))
        self.bubble.tag_bind("bubble-close", "<Leave>", lambda _event: self._bubble_close_hover(False))
        self.bubble.tag_bind("bubble-close", "<ButtonPress-1>", lambda _event: self._dismiss_bubble() or "break")

        if self.message_controller.history_count > 1:
            history_y = bottom - BUBBLE_HISTORY_HEIGHT / 2
            history_x = (left + right) / 2

            self.bubble.create_text(
                history_x, history_y,
                text=f"{self.message_controller.chronological_index}/{self.message_controller.history_count}",
                fill="#765f72", font=("Segoe UI", 10, "bold"), tags="history-count",
            )
            self.bubble.create_text(
                history_x - 48, history_y, text="‹", fill="#d62885",
                font=("Segoe UI", 18, "bold"), tags="history-older",
            )
            self.bubble.create_text(
                history_x + 48, history_y, text="›", fill="#d62885",
                font=("Segoe UI", 18, "bold"), tags="history-newer",
            )

            self.bubble.tag_bind(
                "history-older", "<ButtonPress-1>",
                lambda _event: self._navigate_message(-1) or "break",
            )
            self.bubble.tag_bind(
                "history-newer", "<ButtonPress-1>",
                lambda _event: self._navigate_message(1) or "break",
            )

    def _bubble_close_hover(self, active: bool) -> None:
        """Update close affordance styling while the pointer crosses the bubble control.

        Args:
            active (bool): Whether pointer is hovering over the close button.

        Returns:
            None.
        """
        self.bubble.configure(cursor="hand2" if active else "")
        self.bubble.itemconfigure("bubble-close-icon", fill="#d62839" if active else "#111111")

    def _bubble_corner_at(self, x: int, y: int) -> str:
        """Resolve which resize corner contains the supplied pointer coordinate.

        Args:
            x (int): Pointer or drawing x-coordinate in the current surface.
            y (int): Pointer or drawing y-coordinate in the current surface.

        Returns:
            str: Resize corner name ("nw", "ne", "sw", "se"), or an empty string outside the resize handles.
        """
        width, height = self.bubble.winfo_width(), self.bubble.winfo_height()
        tail = bubble_tail_height(width)

        corners = {
            "nw": (tail, tail),
            "ne": (width - tail, tail),
            "sw": (tail, height - tail),
            "se": (width - tail, height - tail),
        }

        corner, distance = min(
            (
                (
                    name,
                    ((x - point_x) ** 2 + (y - point_y) ** 2) ** .5,
                )
                for name, (point_x, point_y) in corners.items()
            ),
            key=lambda item: item[1],
        )

        return corner if distance <= BUBBLE_RESIZE_HANDLE else ""

    def _bubble_pointer_motion(self, event: tk.Event) -> None:
        """Update bubble hover and resize affordances for pointer motion.

        Args:
            event (tk.Event): Tk pointer event carrying screen coordinates for the gesture.

        Returns:
            None.
        """
        current = self.bubble.find_withtag("current")
        close_items = self.bubble.find_withtag("bubble-close")

        if self.bubble_resize_active or (current and current[0] in close_items):
            return

        self.bubble.delete("resize-indicator")
        corner = self._bubble_corner_at(event.x, event.y)

        if not corner:
            self.bubble.configure(cursor="")
            return

        cursor = "size_nw_se" if corner in {"nw", "se"} else "size_ne_sw"
        self.bubble.configure(cursor=cursor)

        tail = bubble_tail_height(self.bubble.winfo_width())
        x = tail if "w" in corner else self.bubble.winfo_width() - tail
        y = tail if "n" in corner else self.bubble.winfo_height() - tail
        radius = 4

        self.bubble.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill="#d62885", outline="", tags="resize-indicator",
        )

    def _bubble_pointer_leave(self, _event: tk.Event | None = None) -> None:
        """Clear bubble hover state when the pointer leaves the bubble.

        Args:
            _event (tk.Event | None): Optional Tk event that triggered the geometry refresh.

        Returns:
            None.
        """
        if not self.bubble_resize_active:
            self.bubble.delete("resize-indicator")
            self.bubble.configure(cursor="")

    def _bubble_pointer_press(self, event: tk.Event) -> str | None:
        """Start close, drag, or resize behavior from a bubble pointer press.

        Args:
            event (tk.Event): Tk pointer event carrying screen coordinates for the gesture.

        Returns:
            str | None: Tk event result when the press must stop propagation.
        """
        corner = self._bubble_corner_at(event.x, event.y)

        if corner:
            return self._bubble_resize_start(event, corner)

        self._bubble_drag_start(event)
        return None

    def _bubble_resize_start(self, event: tk.Event, corner: str) -> str:
        """Capture bubble geometry before resizing from the selected corner.

        Args:
            event (tk.Event): Tk pointer event carrying screen coordinates for the gesture.
            corner (str): Bubble corner currently being resized.

        Returns:
            str: Tk event result that stops default event propagation.
        """
        self.bubble_resize_active = True
        self.bubble_resize_origin = (
            corner,
            event.x_root,
            event.y_root,
            self.bubble_root.winfo_x(),
            self.bubble_root.winfo_y(),
            self.bubble_root.winfo_width(),
            self.bubble_root.winfo_height(),
        )
        return "break"

    def _bubble_resize_end(self, _event: tk.Event | None = None) -> None:
        """Finish bubble resizing and persist the resulting geometry.

        Args:
            _event (tk.Event | None): Optional Tk event that triggered the geometry refresh.

        Returns:
            None.
        """
        self.bubble_resize_active = False

    def _bubble_resize_move(self, event: tk.Event) -> str:
        """Apply pointer displacement to the active bubble resize operation.

        Args:
            event (tk.Event): Tk pointer event carrying screen coordinates for the gesture.

        Returns:
            str: Tk event result that stops default event propagation.
        """
        corner, pointer_x, pointer_y, x, y, width, height = self.bubble_resize_origin
        dx, dy = event.x_root - pointer_x, event.y_root - pointer_y
        right, bottom = x + width, y + height

        if "w" in corner:
            x = min(right - BUBBLE_RESIZE_MIN_WIDTH, x + dx)
            width = right - x
        else:
            width = max(BUBBLE_RESIZE_MIN_WIDTH, width + dx)

        if "n" in corner:
            y = min(bottom - BUBBLE_RESIZE_MIN_HEIGHT, y + dy)
            height = bottom - y
        else:
            height = max(BUBBLE_RESIZE_MIN_HEIGHT, height + dy)

        self.bubble_has_position = True
        self.bubble_manual_size = (width, height)
        self.bubble_root.geometry(f"{width}x{height}+{x}+{y}")
        self.bubble.after_idle(self._draw_bubble)
        return "break"

    def _redraw_bubble_tail(self, _event: tk.Event | None = None) -> None:
        """Repaint the bubble tail after its body or target geometry changes.

        Args:
            _event (tk.Event | None): Optional Tk event that triggered the geometry refresh.

        Returns:
            None.
        """
        if self.speech_text and self.bubble_root.state() != "withdrawn":
            self.bubble.after_idle(self._draw_bubble)

    def _set_text(self, text: str, emotion: str = "") -> None:
        """Store the next Markdown message and emotion before measuring the bubble.

        Args:
            text (str): Markdown-capable message text to render in the bubble.
            emotion (str): Emotion key used to choose the processing glyph or animation.

        Returns:
            None.
        """
        decorated = f"{emotion_emoji(emotion)} {text}" if text else ""

        if decorated == self.speech_text:
            return

        bubble_was_present = bool(self.speech_text) and self.bubble_root.state() != "withdrawn"
        self.speech_text = decorated

        if text:
            if not bubble_was_present:
                self.bubble_has_position = False

            if self.bubble_manual_size:
                bubble_width, required_header = self.bubble_manual_size
            else:
                bubble_width = detached_bubble_width(self.root.winfo_screenwidth(), self.root.winfo_width())
                required_header = self._required_bubble_height(bubble_width)

            self.pin.place_forget()
            self._position_bubble(bubble_width, required_header)
            self.bubble_root.deiconify()
            self.bubble_root.lift()
            self.root.update_idletasks()
            self._draw_bubble()
        else:
            self.bubble_root.withdraw()
            self.bubble_has_position = False
            self._layout_controls()

    def _required_bubble_height(self, bubble_width: int) -> int:
        """Measure the bubble height needed for its current text and width.

        Args:
            bubble_width (int): Available bubble width used for text measurement.

        Returns:
            int: Total height required to render the current bubble content.
        """
        tail_space = bubble_tail_height(bubble_width) * 2
        text_width = max(20, bubble_width - tail_space - BUBBLE_TEXT_PAD_X - BUBBLE_RIGHT_PAD)
        text_height = self._render_bubble_text(0, 0, text_width, probe=True)

        return bubble_required_height(width=bubble_width, text_height=text_height)

    def _render_bubble_text(self, x: int, y: int, width: int, probe: bool = False) -> int:
        """Render Markdown-like narrative blocks and return their combined height.

        Args:
            x (int): Pointer or drawing x-coordinate in the current surface.
            y (int): Pointer or drawing y-coordinate in the current surface.
            width (int): Current presentation width in pixels.
            probe (bool): Whether to measure text without drawing it.

        Returns:
            int: Rendered or measured text height in pixels.
        """
        origin_y = y
        item_ids: list[int] = []
        blocks = dialogue_markdown_blocks(self.speech_text)

        for index, (kind, content) in enumerate(blocks):
            item = self.bubble.create_text(
                x,
                y,
                anchor="nw",
                text=content,
                width=width,
                fill="#765f72" if kind == "meta" else "#251a28",
                font=BUBBLE_META_FONT if kind == "meta" else BUBBLE_FONT,
                justify="left",
                tags=("speech", f"speech-{kind}"),
            )
            item_ids.append(item)
            bounds = self.bubble.bbox(item)
            y += (18 if not bounds else bounds[3] - bounds[1])

            if index < len(blocks) - 1:
                y += 7

        if probe:
            for item in item_ids:
                self.bubble.delete(item)

        return max(18, y - origin_y)

    def _position_bubble(self, width: int, height: int) -> None:
        """Place the bubble beside the avatar while preserving its selected lane.

        Args:
            width (int): Current presentation width in pixels.
            height (int): Current presentation height in pixels.

        Returns:
            None.
        """
        screen_width, screen_height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        height = min(height, max(100, screen_height - (BUBBLE_SCREEN_MARGIN * 2)))

        if self.bubble_has_position:
            x = max(BUBBLE_SCREEN_MARGIN, min(self.bubble_root.winfo_x(), screen_width - width - BUBBLE_SCREEN_MARGIN))
            y = max(
                BUBBLE_SCREEN_MARGIN,
                min(self.bubble_root.winfo_y(), screen_height - height - BUBBLE_SCREEN_MARGIN),
            )
        else:
            x, y = detached_bubble_position(
                (screen_width, screen_height),
                (self.root.winfo_x(), self.root.winfo_y(), self.root.winfo_width(), self.root.winfo_height()),
                (width, height),
            )
            self.bubble_has_position = True

        self.bubble_root.geometry(f"{width}x{height}+{x}+{y}")

    def _dismiss_bubble(self) -> None:
        """Dismiss only the current visual message; voice and avatar keep running.

        Returns:
            None.
        """
        self.bubble_root.withdraw()

    def _bubble_drag_start(self, event: tk.Event) -> None:
        """Capture pointer and window origins for dragging the detached bubble.

        Args:
            event (tk.Event): Tk pointer event carrying screen coordinates for the gesture.

        Returns:
            None.
        """
        self.bubble_drag_origin = event.x_root, event.y_root, self.bubble_root.winfo_x(), self.bubble_root.winfo_y()

    def _bubble_drag_move(self, event: tk.Event) -> str:
        """Move the detached bubble by the active drag displacement.

        Args:
            event (tk.Event): Tk pointer event carrying screen coordinates for the gesture.

        Returns:
            str: Tk event result that stops default event propagation.
        """
        if self.bubble_resize_active:
            return self._bubble_resize_move(event)

        x, y, window_x, window_y = self.bubble_drag_origin
        next_x, next_y = window_x + event.x_root - x, window_y + event.y_root - y

        self.bubble_root.geometry(f"+{next_x}+{next_y}")
        self.bubble.after_idle(self._draw_bubble)
        return "break"
