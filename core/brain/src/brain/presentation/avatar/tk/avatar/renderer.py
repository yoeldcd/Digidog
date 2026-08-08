# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Memory-conscious animated GIF player for Tk."""

from __future__ import annotations

import time
import tkinter as tk
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk

from brain.presentation.avatar.tk.controls.view import (
    TkBottomControlsPainterMixin, mute_button_geometry, playback_button_geometry,
)
from brain.presentation.avatar.tk.quota.view import (
    TkQuotaPainterMixin, quota_bar_color, quota_ring_geometry,
)


class AnimatedGif(TkBottomControlsPainterMixin, TkQuotaPainterMixin):
    """Decode a single frame at a time instead of retaining a large GIF atlas.

    Attributes:
        label (tk.Label): Tk label receiving rendered frames.
        image (Image.Image | None): Open GIF image currently being rendered.
        photo (ImageTk.PhotoImage | None): Current PhotoImage displayed on the label.
        frame (int): Current frame index.
        job (str | None): Scheduled callback ID for next frame.
        playing (bool): Whether audio playback is currently active.
        framebuffer (OrderedDict): Bounded cache of composed frame images.
        framebuffer_size (tuple[int, int]): Dimensions of current framebuffer cache.
        current_path (str): File path of currently loaded GIF asset.
        displayed_path (str): File path of rendered frame.
        crop_box (tuple[int, int, int, int] | None): Cropping bounding box for avatar frame.
        quotas (tuple[int, int] | None): Consumed quota percentages (five_hour, weekly).
        quota_resets (tuple[str, str] | None): Reset display labels (five_hour, weekly).
        quota_refreshing (bool): Whether quota update is in flight.
        quota_visible (bool): Whether quota indicators are drawn.
        quota_blink_job (str | None): Scheduled callback ID for quota blink animation.
        avatar_visible (bool): Whether character layer is rendered.
        muted (bool): Whether audio output is muted.
        controls_visible (bool): Whether bottom-zone controls are rendered.
    """

    def __init__(self, label: tk.Label) -> None:
        """Initialize the component with its required Tk collaborators.

        Args:
            label (tk.Label): Tk label that retains the current rendered PhotoImage.

        Returns:
            None.
        """
        self.label = label
        self.image: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.frame = 0
        self.job: str | None = None
        self.playing = False
        self.framebuffer: OrderedDict[tuple[str, int, int, int, bool, tuple[int, int] | None, tuple[str, str] | None, bool, bool, bool, bool], ImageTk.PhotoImage] = OrderedDict()
        self.framebuffer_size = (0, 0)
        self.current_path = ""
        self.displayed_path = ""
        self.crop_box: tuple[int, int, int, int] | None = None
        self.quotas: tuple[int, int] | None = None
        self.quota_resets: tuple[str, str] | None = None
        self.quota_refreshing = False
        self.quota_visible = True
        self.quota_blink_job: str | None = None
        self.avatar_visible = True
        self.muted = False
        self.controls_visible = True

    def set_playing(self, playing: bool) -> None:
        """Update the playback-control glyph state.

        Args:
            playing (bool): Whether audio playback is currently active.

        Returns:
            None.
        """
        self.playing = playing

    def set_avatar_visible(self, visible: bool) -> None:
        """Show or suppress only the character layer, preserving controls.

        Args:
            visible (bool): Whether avatar pixels should be composed.

        Returns:
            None.
        """
        if visible == self.avatar_visible:
            return

        self.avatar_visible = visible
        self.framebuffer.clear()

    def set_muted(self, muted: bool) -> None:
        """Update mute affordance without changing message visibility.

        Args:
            muted (bool): Whether mute styling should be shown.

        Returns:
            None.
        """
        if muted == self.muted:
            return

        self.muted = muted
        self.framebuffer.clear()

    def set_controls_visible(self, visible: bool) -> None:
        """Toggle raster controls without affecting avatar or message layers.

        Args:
            visible (bool): Whether control pixels should be composed.

        Returns:
            None.
        """
        if visible == self.controls_visible:
            return

        self.controls_visible = visible
        self.framebuffer.clear()

    def set_quotas(
        self,
        five_hour_percent: int,
        weekly_percent: int,
        five_hour_reset: str = "",
        weekly_reset: str = "",
    ) -> None:
        """Update quota overlays and invalidate cached frames only on change.

        Args:
            five_hour_percent (int): Consumed five-hour quota percentage.
            weekly_percent (int): Consumed weekly quota percentage.
            five_hour_reset (str): Display label for five-hour reset.
            weekly_reset (str): Display label for weekly reset.

        Returns:
            None.
        """
        quotas = (five_hour_percent, weekly_percent)
        resets = (five_hour_reset, weekly_reset)

        if quotas == self.quotas and resets == self.quota_resets:
            return

        self.quotas = quotas
        self.quota_resets = resets
        self.framebuffer.clear()

    def set_quota_refreshing(self, refreshing: bool) -> None:
        """Blink quota rings while App Server resolves a fresh snapshot.

        Args:
            refreshing (bool): Whether quota refresh is in flight.

        Returns:
            None.
        """
        if refreshing == self.quota_refreshing:
            return

        self.quota_refreshing = refreshing

        if not refreshing:
            if self.quota_blink_job:
                self.label.after_cancel(self.quota_blink_job)
                self.quota_blink_job = None

            self.quota_visible = True
            self.framebuffer.clear()
            return

        self._toggle_quota_blink()

    def _toggle_quota_blink(self) -> None:
        """Flip ring visibility at a calm, readable cadence.

        Returns:
            None.
        """
        if not self.quota_refreshing:
            return

        self.quota_visible = not self.quota_visible
        self.framebuffer.clear()
        self.quota_blink_job = self.label.after(320, self._toggle_quota_blink)

    def load(self, path: Path) -> None:
        """Load a GIF, calculate its visible crop, and start drawing.

        Args:
            path (Path): GIF asset to display.

        Returns:
            None.
        """
        self.stop()

        if self.image:
            self.image.close()

        self.image = Image.open(path)
        self.current_path = str(path)
        first_bounds = self.image.convert("RGBA").getchannel("A").getbbox()

        if first_bounds:
            pad_x = int(self.image.width * .05)
            pad_y = int(self.image.height * .05)
            self.crop_box = (
                max(0, first_bounds[0] - pad_x),
                max(0, first_bounds[1] - pad_y),
                min(self.image.width, first_bounds[2] + pad_x),
                min(self.image.height, first_bounds[3] + pad_y),
            )
        else:
            self.crop_box = None

        self.image.seek(0)
        self.frame = 0
        self._draw()

    def stop(self) -> None:
        """Cancel the scheduled GIF frame callback, if any.

        Returns:
            None.
        """
        if self.job:
            self.label.after_cancel(self.job)
            self.job = None

    def _draw(self) -> None:
        """Compose one visible GIF frame, update the label, and schedule the next frame.

        Returns:
            None.
        """
        if not self.image:
            return

        draw_started = time.perf_counter()

        if self.avatar_visible:
            try:
                self.image.seek(self.frame)
            except EOFError:
                self.frame = 0
                self.image.seek(0)

        width = max(1, self.label.winfo_width())
        height = max(1, self.label.winfo_height())

        if width <= 1 or height <= 1:
            self.job = self.label.after(16, self._draw)
            return

        if self.framebuffer_size != (width, height):
            self.framebuffer.clear()
            self.framebuffer_size = (width, height)

        render_frame = self.frame if self.avatar_visible else 0
        cache_key = (
            self.current_path,
            render_frame,
            width,
            height,
            self.playing,
            self.quotas,
            self.quota_resets,
            self.quota_visible,
            self.avatar_visible,
            self.muted,
            self.controls_visible,
        )
        cached = self.framebuffer.get(cache_key)

        if cached is not None:
            self.framebuffer.move_to_end(cache_key)
            self.photo = cached
            self.label.configure(image=self.photo, text="")
            self.displayed_path = self.current_path
            delay = max(20, int(self.image.info.get("duration", 100)))
            self.frame += 1
            self.job = self.label.after(delay, self._draw)
            return

        content_top = 0
        content_bottom = min(52, max(0, height // 4))
        content_height = max(1, height - content_top - content_bottom)
        composed = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        if self.avatar_visible:
            frame = self.image.copy()
            if self.crop_box:
                frame = frame.crop(self.crop_box)
            frame.thumbnail((width, content_height), Image.Resampling.LANCZOS, reducing_gap=3.0)
            frame = frame.convert("RGBA")
            alpha = frame.getchannel("A").point(lambda value: 255 if value else 0)
            opaque_frame = frame.copy()
            opaque_frame.putalpha(alpha)
            content_y = content_top + (content_height - frame.height) // 2
            composed.alpha_composite(opaque_frame, ((width - frame.width) // 2, content_y))

        draw = ImageDraw.Draw(composed)

        if self.controls_visible:
            self._draw_quota_indicators(draw=draw, width=width, height=height)
            self._draw_mute_button(draw=draw, width=width, height=height)

            (cx, cy), radius = playback_button_geometry(width=width, height=height)
            draw.ellipse(
                (cx - radius, cy - radius, cx + radius, cy + radius),
                fill="#123b78",
                outline="#3b8cff",
                width=3,
            )

            if self.playing:
                bar_width = max(4, round(radius * .22))
                bar_height = round(radius * .9)
                bar_top = cy - bar_height // 2
                bar_bottom = cy + bar_height // 2
                left_pause_x = cx - round(radius * .38)
                right_pause_x = cx + round(radius * .18)
                draw.rectangle(
                    (left_pause_x, bar_top, left_pause_x + bar_width, bar_bottom),
                    fill="white",
                )
                draw.rectangle(
                    (right_pause_x, bar_top, right_pause_x + bar_width, bar_bottom),
                    fill="white",
                )
            else:
                draw.polygon(
                    (
                        (cx - round(radius * .28), cy - round(radius * .55)),
                        (cx - round(radius * .28), cy + round(radius * .55)),
                        (cx + round(radius * .48), cy),
                    ),
                    fill="white",
                )

        self.photo = ImageTk.PhotoImage(composed)
        self.framebuffer[cache_key] = self.photo
        max_frames = max(12, (24 * 1024 * 1024) // max(1, width * height * 4))

        while len(self.framebuffer) > max_frames:
            self.framebuffer.popitem(last=False)

        self.label.configure(image=self.photo, text="")
        self.displayed_path = self.current_path
        frame_duration = max(20, int(self.image.info.get("duration", 100)))
        elapsed_ms = int((time.perf_counter() - draw_started) * 1000)
        delay = max(1, frame_duration - elapsed_ms)
        self.frame += 1
        self.job = self.label.after(delay, self._draw)
