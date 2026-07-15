"""Memory-conscious animated GIF player for Tk."""

from __future__ import annotations

import tkinter as tk
import time
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk


def quota_bar_color(percent: int) -> str:
    """Return green, yellow, orange, or red for the consumed quartile."""
    if percent >= 75:
        return "#ff4f64"
    if percent >= 50:
        return "#ff982f"
    if percent >= 25:
        return "#f1d447"
    return "#36c978"


def playback_button_geometry(width: int, height: int) -> tuple[tuple[int, int], int]:
    """Return the enlarged playback control center and circular hit radius."""
    radius = max(21, min(44, round(width * .13)))
    padding = max(6, round(height * .02))
    return (width // 2, height - radius - padding), radius


def quota_ring_geometry(width: int, height: int) -> tuple[tuple[int, int], tuple[int, int], int]:
    """Return left/right quota centers and their shared hit radius."""
    (_, play_center_y), play_radius = playback_button_geometry(width=width, height=height)
    former_play_radius = max(16, min(34, round(width * .10)))
    ring_radius = max(13, round(former_play_radius * .78))
    reset_line_height = max(9, round(ring_radius * .50))
    ring_center_y = play_center_y + play_radius - ring_radius - reset_line_height
    offset = play_radius + ring_radius + max(4, round(width * .025))
    center_x = width // 2
    return (center_x - offset, ring_center_y), (center_x + offset, ring_center_y), ring_radius


def mute_button_geometry(width: int, height: int) -> tuple[tuple[int, int], int]:
    """Return a proportional lower-left mute control and its circular hitbox."""
    radius = max(10, min(16, round(width * .048)))
    padding = max(5, round(width * .025))
    return (padding + radius, height - padding - radius), radius


class AnimatedGif:
    """Decode a single frame at a time instead of retaining a large GIF atlas."""

    def __init__(self, label: tk.Label) -> None:
        self.label = label
        self.image: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.frame = 0
        self.job: str | None = None
        self.playing = False
        self.framebuffer: OrderedDict[tuple[str, int, int, int, bool], ImageTk.PhotoImage] = OrderedDict()
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
        self.playing = playing

    def set_avatar_visible(self, visible: bool) -> None:
        """Show or suppress only the character layer, preserving controls."""
        if visible == self.avatar_visible:
            return
        self.avatar_visible = visible
        self.framebuffer.clear()

    def set_muted(self, muted: bool) -> None:
        """Update the mute affordance without changing message visibility."""
        if muted == self.muted:
            return
        self.muted = muted
        self.framebuffer.clear()

    def set_controls_visible(self, visible: bool) -> None:
        """Toggle raster controls without affecting avatar or message layers."""
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
        """Update quota overlays and invalidate viewport frames only on change."""
        quotas = (five_hour_percent, weekly_percent)
        resets = (five_hour_reset, weekly_reset)
        if quotas == self.quotas and resets == self.quota_resets:
            return
        self.quotas = quotas
        self.quota_resets = resets
        self.framebuffer.clear()

    def set_quota_refreshing(self, refreshing: bool) -> None:
        """Blink quota rings while App Server is resolving a fresh snapshot."""
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
        """Flip ring visibility at a calm, readable cadence."""
        if not self.quota_refreshing:
            return
        self.quota_visible = not self.quota_visible
        self.framebuffer.clear()
        self.quota_blink_job = self.label.after(320, self._toggle_quota_blink)

    def load(self, path: Path) -> None:
        self.stop()
        if self.image:
            self.image.close()
        self.image = Image.open(path)
        self.current_path = str(path)
        first_bounds = self.image.convert("RGBA").getchannel("A").getbbox()
        if first_bounds:
            pad_x, pad_y = int(self.image.width*.05), int(self.image.height*.05)
            self.crop_box = (
                max(0,first_bounds[0]-pad_x), max(0,first_bounds[1]-pad_y),
                min(self.image.width,first_bounds[2]+pad_x), min(self.image.height,first_bounds[3]+pad_y),
            )
        else:
            self.crop_box = None
        self.image.seek(0)
        self.frame = 0
        self._draw()

    def stop(self) -> None:
        if self.job:
            self.label.after_cancel(self.job)
            self.job = None

    def _draw(self) -> None:
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
            # Crop and shrink in the GIF's compact native mode before
            # allocating RGBA pixels for the visible character layer.
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
                (cx-radius, cy-radius, cx+radius, cy+radius),
                fill="#123b78",
                outline="#3b8cff",
                width=3,
            )
            if self.playing:
                bar_width = max(4,round(radius*.22)); bar_height = round(radius*.9)
                draw.rectangle((cx-round(radius*.38),cy-bar_height//2,cx-round(radius*.38)+bar_width,cy+bar_height//2),fill="white")
                draw.rectangle((cx+round(radius*.18),cy-bar_height//2,cx+round(radius*.18)+bar_width,cy+bar_height//2),fill="white")
            else:
                draw.polygon(((cx-round(radius*.28),cy-round(radius*.55)),(cx-round(radius*.28),cy+round(radius*.55)),(cx+round(radius*.48),cy)),fill="white")
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

    def _draw_mute_button(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        """Draw an economical speaker icon with an explicit muted slash."""
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
                (center_x - round(radius * .55), center_y - round(radius * .55), center_x + round(radius * .55), center_y + round(radius * .55)),
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

    def _draw_quota_indicators(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        """Draw five-hour and weekly progress rings beside playback."""
        if self.quotas is None or not self.quota_visible or width < 80:
            return
        left_center, right_center, ring_radius = quota_ring_geometry(width=width, height=height)
        ring_width = max(2, round(ring_radius * .20))
        try:
            value_font = ImageFont.truetype("segoeuib.ttf", max(8, round(ring_radius * .56)))
            label_font = ImageFont.truetype("segoeuib.ttf", max(10, round(ring_radius * .62)))
            reset_font = ImageFont.truetype("segoeui.ttf", max(7, round(ring_radius * .44)))
        except OSError:
            value_font = label_font = reset_font = ImageFont.load_default()
        for index, (label, percent) in enumerate(zip(("5h", "7d"), self.quotas)):
            remaining = 100 - percent
            center_x, center_y = left_center if index == 0 else right_center
            bounds = (center_x - ring_radius, center_y - ring_radius, center_x + ring_radius, center_y + ring_radius)
            draw.ellipse(bounds, fill="#101820", outline="#315078", width=ring_width)
            draw.arc(bounds, start=-90, end=-90 + round(360 * remaining / 100), fill=quota_bar_color(percent), width=ring_width)
            value = f"{remaining}%"
            value_bounds = draw.textbbox((0, 0), value, font=value_font)
            draw.text((center_x - (value_bounds[2] - value_bounds[0]) / 2, center_y - (value_bounds[3] - value_bounds[1]) / 2 - 3), value, font=value_font, fill="white")
            label_bounds = draw.textbbox((0, 0), label, font=label_font)
            label_gap = max(5, round(ring_radius * .28))
            draw.text((center_x - (label_bounds[2] - label_bounds[0]) / 2, center_y - ring_radius - (label_bounds[3] - label_bounds[1]) - label_gap), label, font=label_font, fill="#a9c8f7")
            reset = self.quota_resets[index] if self.quota_resets else ""
            if reset:
                reset_bounds = draw.textbbox((0, 0), reset, font=reset_font)
                reset_x = center_x - (reset_bounds[2] - reset_bounds[0]) / 2
                reset_y = min(height - (reset_bounds[3] - reset_bounds[1]) - 1, center_y + ring_radius + 2)
                draw.text((reset_x, reset_y), reset, font=reset_font, fill="#a9c8f7")
