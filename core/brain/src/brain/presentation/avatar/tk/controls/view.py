# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Bottom-zone Tk control geometry and raster painting."""

from __future__ import annotations

import math
import tkinter as tk
from typing import Any, Mapping

from PIL import ImageDraw

from brain.presentation.avatar.interactivity.emotions import emotion_emoji
from brain.presentation.avatar.interactivity.interaction_controller import (
    InteractionController, ReactionIntent,
)
from brain.presentation.avatar.tk.controls.geometry import (
    mute_button_geometry, playback_button_geometry, quota_ring_geometry,
)
from brain.presentation.avatar.window.config import MIN_HEIGHT, MIN_WIDTH
from brain.presentation.avatar.window.native import NativeWindowPriority


class TkBottomControlsPainterMixin:
    """Paint bottom PLAY/STOP and mute chrome; owns no interaction policy.

    Attributes:
        muted (bool): Whether mute styling should be shown.
    """

    def _draw_mute_button(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        """Paint the speaker glyph and its muted slash on the composed frame.

        Args:
            draw (ImageDraw.ImageDraw): Pillow drawing context for the composed avatar frame.
            width (int): Current presentation width in pixels.
            height (int): Current presentation height in pixels.

        Returns:
            None.
        """
        (center_x, center_y), radius = mute_button_geometry(width=width, height=height)
        ring_width = max(2, round(radius * .15))

        draw.ellipse(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            fill=(18, 59, 120, 150),
            outline="#3b8cff",
            width=ring_width,
        )

        icon_center_x = center_x - round(radius * .12)
        speaker_width = max(4, round(radius * .26))
        speaker_height = max(7, round(radius * .48))
        speaker_x = icon_center_x - round(radius * .38)

        draw.rectangle(
            (speaker_x, center_y - speaker_height // 2, speaker_x + speaker_width, center_y + speaker_height // 2),
            fill="white",
        )
        draw.polygon(
            (
                (speaker_x + speaker_width, center_y - speaker_height // 2),
                (icon_center_x + round(radius * .18), center_y - round(radius * .45)),
                (icon_center_x + round(radius * .18), center_y + round(radius * .45)),
                (speaker_x + speaker_width, center_y + speaker_height // 2),
            ),
            fill="white",
        )

        if self.muted:
            slash = max(2, round(radius * .16))
            draw.line(
                (
                    center_x - round(radius * .55), center_y - round(radius * .55),
                    center_x + round(radius * .55), center_y + round(radius * .55),
                ),
                fill="#ff6f91",
                width=slash,
            )
            return

        arc_bounds = (
            icon_center_x - round(radius * .05),
            center_y - round(radius * .55),
            icon_center_x + round(radius * .70),
            center_y + round(radius * .55),
        )
        draw.arc(arc_bounds, start=-55, end=55, fill="white", width=max(2, round(radius * .12)))


class TkControlsMixin:
    """Bind the bottom, center, and top layout zones to shared interaction policy.

    Attributes:
        pin (tk.Button): Top-left pin window button widget.
        message (tk.Button): Top-right message history button widget.
        processing (tk.Canvas): Top-center processing animation canvas widget.
        processing_frame (int): Frame index for rotating dot processing indicator.
        processing_job (str | None): Scheduled callback ID for processing animation.
        processing_emotion (str): Emotion key for processing indicator icon.
        grip (tk.Label): Bottom-right resize handle widget.
        controls_visible (bool): Whether control overlay is currently visible.
        presentation (Any): Current projected presentation state.
        root (tk.Tk): Main avatar window root widget.
        label (tk.Label): Main avatar window image label.
        player (Any): Animated GIF player collaborator.
        drag_origin (tuple[int, int, int, int]): Captured coordinates at drag gesture start.
        base_height (int): Baseline height for aspect-ratio window resizing.
        transport (Any): Daemon transport client adapter collaborator.
        is_pinned (bool): Whether avatar window stays always on top.
        bubble_root (tk.Toplevel): Detached message bubble window root.
        message_controller (Any): History and replay message controller collaborator.
        avatar_click_job (str | None): Scheduled callback ID for single-click confirmation.
        reaction_bag (Any): Random phrase reaction bag collaborator.
    """

    def _build_controls(self) -> None:
        """Create the pin, message, processing, and resize controls and bind their events.

        Returns:
            None.
        """
        style = {
            "bg": "#101820", "activebackground": "#172536", "fg": "white",
            "activeforeground": "white", "bd": 0, "highlightthickness": 0,
            "font": ("Segoe UI Symbol", 18, "bold"),
        }

        self.pin = tk.Button(self.root, text="📌", command=self._toggle_pin, cursor="hand2", **style)
        self.message = tk.Button(self.root, text="💬", command=self._toggle_last_message, cursor="hand2", **style)
        self.processing = tk.Canvas(self.root, bg="#101820", bd=0, highlightthickness=0, cursor="hand2")
        self.processing.bind("<ButtonRelease-1>", lambda _event: self._post("/cancel-processing"))
        self.processing_frame = 0
        self.processing_job = None
        self.processing_emotion = ""

        grip_style = {key: value for key, value in style.items() if not key.startswith("active")}
        self.grip = tk.Label(self.root, text="◢", cursor="size_nw_se", **grip_style)
        self.grip.bind("<ButtonPress-1>", lambda _event: "break")
        self.grip.bind("<B1-Motion>", self._resize_move)
        self._layout_controls()

    def _layout_controls(self, _event: tk.Event | None = None) -> None:
        """Place each control widget from the current window geometry and visibility state.

        Args:
            _event (tk.Event | None): Optional Tk event that triggered the geometry refresh.

        Returns:
            None.
        """
        width = max(1, self.root.winfo_width())
        size = max(32, min(58, round(width * .18)))
        grip_size = max(22, min(38, round(width * .12)))
        pad = max(4, round(width * .025))
        font_size = max(14, round(size * .45))

        for widget in (self.pin, self.message):
            widget.configure(font=("Segoe UI Symbol", font_size, "bold"))

        self.grip.configure(font=("Segoe UI Symbol", max(12, round(grip_size * .55)), "bold"))

        if self.controls_visible:
            self.pin.place(x=pad, y=pad, anchor="nw", width=size, height=size)
            self.message.place(x=width - pad, y=pad, anchor="ne", width=size, height=size)
            self.grip.place(relx=1, rely=1, anchor="se", width=grip_size, height=grip_size)
        else:
            self.pin.place_forget()
            self.grip.place_forget()
            if self.presentation.queue_depth > 0:
                self.message.place(x=width - pad, y=pad, anchor="ne", width=size, height=size)
            else:
                self.message.place_forget()

        if self.presentation.processing_indicator_active:
            self.processing.place(x=width // 2, y=pad, anchor="n", width=size, height=size)
        else:
            self.processing.place_forget()

    def _set_processing_indicator(self, active: bool, emotion: str = "") -> None:
        """Start or stop the processing animation and place its emotion glyph.

        Args:
            active (bool): Whether the processing indicator should be visible.
            emotion (str): Emotion key used to choose the processing glyph or animation.

        Returns:
            None.
        """
        self.processing_emotion = emotion if active else ""

        if active and self.processing_job is None:
            self._animate_processing()
        elif not active and self.processing_job is not None:
            self.root.after_cancel(self.processing_job)
            self.processing_job = None
            self.processing.delete("all")

        self._layout_controls()

    def _animate_processing(self) -> None:
        """Paint rotating dots with the current emotion at the top-zone center.

        Returns:
            None.
        """
        self.processing.delete("all")

        size = max(1, self.processing.winfo_width())
        center = size / 2
        orbit = size * .34
        colors = ("#00d4a8", "#2cb8ff", "#6f7cff", "#df65ff", "#ff6fae", "#ffc247")

        for index, color in enumerate(colors):
            angle = math.radians(self.processing_frame * 5 + index * 60)
            x = center + math.cos(angle) * orbit
            y = center + math.sin(angle) * orbit
            radius = max(2, round(size * .055))
            self.processing.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill=color, outline="",
            )

        self.processing.create_text(
            center, center,
            text=emotion_emoji(self.processing_emotion) if self.processing_emotion else "⚙",
            fill="white", font=("Segoe UI Symbol", max(11, round(size * .28)), "bold"),
        )
        self.processing_frame = (self.processing_frame + 1) % 360
        self.processing_job = self.root.after(50, self._animate_processing)

    def _set_queue_depth(self, depth: int) -> None:
        """Expose the number of pending messages on the message control.

        Args:
            depth (int): Number of pending messages that follow the visible message.

        Returns:
            None.
        """
        self.message.configure(text="💬" if depth <= 0 else f"💬\n{depth}")

    def _poll_control_hover(self) -> None:
        """Reconcile pointer location with the visibility of the control layer.

        Returns:
            None.
        """
        pointer_x, pointer_y = self.root.winfo_pointerxy()
        left, top = self.root.winfo_x(), self.root.winfo_y()

        inside = (
            left <= pointer_x < left + self.root.winfo_width()
            and top <= pointer_y < top + self.root.winfo_height()
        )

        self._set_controls_visible(inside and self.is_visible)
        self.root.after(100, self._poll_control_hover)

    def _set_controls_visible(self, visible: bool) -> None:
        """Update control visibility in both Tk widgets and the raster renderer.

        Args:
            visible (bool): Whether this presentation layer should be shown.

        Returns:
            None.
        """
        if visible == self.controls_visible:
            return

        self.controls_visible = visible
        self.player.set_controls_visible(visible)
        self._layout_controls()

    def _drag_start(self, event: tk.Event) -> None:
        """Capture the pointer and window origin used by a drag gesture.

        Args:
            event (tk.Event): Tk pointer event carrying screen coordinates for the gesture.

        Returns:
            None.
        """
        self.drag_origin = event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y()

    def _drag_move(self, event: tk.Event) -> None:
        """Move the avatar window by the displacement captured at drag start.

        Args:
            event (tk.Event): Tk pointer event carrying screen coordinates for the gesture.

        Returns:
            None.
        """
        x, y, window_x, window_y = self.drag_origin
        self.root.geometry(f"+{window_x + event.x_root - x}+{window_y + event.y_root - y}")

    def _resize_move(self, event: tk.Event) -> str:
        """Resize the avatar window while preserving its supported aspect ratio.

        Args:
            event (tk.Event): Tk pointer event carrying screen coordinates for the gesture.

        Returns:
            str: Tk event result that stops default event propagation.
        """
        width = max(MIN_WIDTH, event.x_root - self.root.winfo_x())
        height = max(MIN_HEIGHT, round(width * 4 / 3))
        width = round(height * 3 / 4)

        self.base_height = height
        self.root.geometry(f"{width}x{height}+{self.root.winfo_x()}+{self.root.winfo_y()}")
        return "break"

    def _post(self, path: str, payload: Mapping[str, Any] | None = None) -> None:
        """Send one semantic command or payload to the local avatar daemon.

        Args:
            path (str): Filesystem or daemon path used by this operation.
            payload (Mapping[str, Any] | None): Optional JSON mapping sent to the local daemon endpoint.

        Returns:
            None.
        """
        self.transport.post(path, payload)

    def _toggle_pin(self) -> None:
        """Toggle the pinned state and refresh native window priority.

        Returns:
            None.
        """
        self.is_pinned = not self.is_pinned
        self._apply_topmost()
        self.pin.configure(fg="#3b8cff" if self.is_pinned else "white")

        if self.is_pinned:
            self.root.lift()

    def _apply_topmost(self) -> None:
        """Apply the current pin state to the native Tk window.

        Returns:
            None.
        """
        playback_active = self.presentation.owns_active_presentation
        topmost = self.is_pinned or playback_active

        NativeWindowPriority.apply(self.root, topmost=topmost, show=playback_active)
        NativeWindowPriority.apply(self.bubble_root, topmost=topmost, show=False)

    def _execute_primary_control(self) -> None:
        """Dispatch the primary control to stop or start current playback.

        Returns:
            None.
        """
        command = InteractionController.primary_click(self.presentation, self.message_controller.replay_target())

        try:
            self.transport.execute(command)
        except OSError:
            return

        if command.intent.value == "stop":
            self._dismiss_bubble()

    def _toggle_playback(self) -> None:
        """Start or stop the message currently selected by the session.

        Returns:
            None.
        """
        self._execute_primary_control()

    def _toggle_mute(self) -> None:
        """Toggle mute mode and project it to the renderer and daemon.

        Returns:
            None.
        """
        try:
            self._post("/mute")
        except OSError:
            pass

    def _navigate_message(self, direction: int) -> None:
        """Move the visible history projection in the requested direction.

        Args:
            direction (int): Signed history offset: negative for previous and positive for next.

        Returns:
            None.
        """
        try:
            history = self.message_controller.retained_history(self.transport.messages())
        except OSError:
            return

        target = history.navigate(self.message_controller.replay_target().speak_id, direction)

        if target is not None:
            self.message_controller.select(target, self._set_text)

    def _toggle_last_message(self) -> None:
        """Show or dismiss the last retained message projection.

        Returns:
            None.
        """
        if self.bubble_root.state() != "withdrawn":
            self._dismiss_bubble()
            return

        message = self.message_controller.current or self.message_controller.last

        if message is not None:
            self._set_text(message.display_text, message.emotion)

    def _label_click(self, event: tk.Event) -> None:
        """Route a click on the avatar label into the playback gesture policy.

        Args:
            event (tk.Event): Tk pointer event carrying screen coordinates for the gesture.

        Returns:
            None.
        """
        if abs(event.x_root - self.drag_origin[0]) + abs(event.y_root - self.drag_origin[1]) > 4:
            return

        mute_center, mute_radius = mute_button_geometry(self.label.winfo_width(), self.label.winfo_height())

        if (event.x - mute_center[0]) ** 2 + (event.y - mute_center[1]) ** 2 <= mute_radius ** 2:
            self._toggle_mute()
            return

        left, right, radius = quota_ring_geometry(self.label.winfo_width(), self.label.winfo_height())

        if any((event.x - x) ** 2 + (event.y - y) ** 2 <= radius ** 2 for x, y in (left, right)):
            self._start_quota_refresh()
            return

        center, radius = playback_button_geometry(self.label.winfo_width(), self.label.winfo_height())

        if (event.x - center[0]) ** 2 + (event.y - center[1]) ** 2 <= radius ** 2:
            self._toggle_playback()
            return

        self._avatar_click(event)

    def _avatar_click(self, _event: tk.Event | None = None) -> None:
        """Collect a click on the avatar for single- or double-click resolution.

        Args:
            _event (tk.Event | None): Optional Tk event that triggered the gesture.

        Returns:
            None.
        """
        if self.avatar_click_job is not None:
            self.root.after_cancel(self.avatar_click_job)
            self.avatar_click_job = None
            self._speak_reaction()
            return
        self.avatar_click_job = self.root.after(400, self._commit_avatar_single_click)

    def _commit_avatar_single_click(self) -> None:
        """Commit the deferred single-click action after the double-click window.

        Returns:
            None.
        """
        self.avatar_click_job = None
        self._execute_primary_control()

    def _speak_reaction(self) -> None:
        """Request speech for the reaction selected by the interaction controller.

        Returns:
            None.
        """
        reaction = self.reaction_bag.draw_reaction()
        command = InteractionController.double_click(
            self.presentation, ReactionIntent(reaction.message, reaction.animation),
        )

        try:
            self.transport.execute(command)
        except OSError:
            pass

        if command.intent.value == "stop":
            self._dismiss_bubble()