# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Borderless transparent avatar window coupled to the voice daemon."""
from __future__ import annotations
import json
import os
import re
import time
from datetime import datetime
import tkinter as tk
import queue
import threading
from urllib.request import Request, urlopen
from brain.infrastructure.voice.daemon_client import VOICE_DAEMON_URL
from brain.presentation.avatar.tk.animated_gif import AnimatedGif, mute_button_geometry, playback_button_geometry, quota_ring_geometry
from brain.presentation.avatar.window.config import DAEMON_LOSS_GRACE_SECONDS, MIN_HEIGHT, MIN_WIDTH, POLL_INTERVAL_MS, TRANSPARENT_COLOR, avatar_asset, default_geometry
from brain.presentation.avatar.interactivity.reactions import ReactionPhraseBag
from brain.presentation.avatar.interactivity.emotions import emotion_emoji
from brain.presentation.avatar.window.native import NativeWindowPriority
from brain.infrastructure.codex.quota_client import CodexQuotaClient

BUBBLE_FONT = ("Segoe UI", 12)
BUBBLE_META_FONT = ("Segoe UI", 11, "italic")
BUBBLE_BORDER = 3
BUBBLE_OUTER_PAD = 6
BUBBLE_TEXT_PAD_X = 18
BUBBLE_TEXT_PAD_Y = 12
BUBBLE_CLOSE_SIZE = 32
BUBBLE_RIGHT_PAD = BUBBLE_CLOSE_SIZE + 18
BUBBLE_SCREEN_MARGIN = 18
BUBBLE_AVATAR_GAP = 18
BUBBLE_MIN_WIDTH = 520
BUBBLE_RESIZE_MIN_WIDTH = 320
BUBBLE_RESIZE_MIN_HEIGHT = 72
BUBBLE_RESIZE_HANDLE = 10


def dialogue_markdown_blocks(text: str) -> list[tuple[str, str]]:
    """Split bracket-delimited narrative metatext from spoken dialogue."""
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
    return blocks or ([('dialogue', text.strip())] if text.strip() else [])


def bubble_tail_height(width: int) -> int:
    """Return a bounded tail height derived from bubble width, not text height."""
    return max(14, min(28, round(width * .08)))


def bubble_required_height(width: int, text_height: int) -> int:
    """Return the complete bubble height required to contain its text and tail."""
    return max(72, text_height + (BUBBLE_TEXT_PAD_Y * 2) + (bubble_tail_height(width) * 2) + (BUBBLE_BORDER * 2))


def detached_bubble_width(screen_width: int, avatar_width: int) -> int:
    """Choose a readable message width independently from the avatar viewport."""
    available = max(240, screen_width - (BUBBLE_SCREEN_MARGIN * 2))
    preferred = max(BUBBLE_MIN_WIDTH, avatar_width * 3)
    return min(available, preferred, max(240, round(screen_width * .58)))


def detached_bubble_position(
    screen_size: tuple[int, int],
    avatar_bounds: tuple[int, int, int, int],
    bubble_size: tuple[int, int],
) -> tuple[int, int]:
    """Center a new bubble above or below the avatar without covering it."""
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
        y = BUBBLE_SCREEN_MARGIN if space_above >= space_below else screen_height - BUBBLE_SCREEN_MARGIN - bubble_height
    return x, max(BUBBLE_SCREEN_MARGIN, y)


def bubble_tail_side(
    bubble_bounds: tuple[int, int, int, int],
    avatar_bounds: tuple[int, int, int, int],
) -> str:
    """Resolve the bubble edge facing the avatar after either window moves."""
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
    """Return a stable body and an angled tail pointing toward a target."""
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


class AvatarWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.geometry(default_geometry(self.root.winfo_screenwidth()))
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.label = tk.Label(self.root, bg=TRANSPARENT_COLOR, bd=0, highlightthickness=0)
        self.label.place(x=0, y=0, relwidth=1, relheight=1)
        self.player = AnimatedGif(self.label)
        self.state, self.last_seen = "", time.monotonic()
        self.daemon_instance_id = os.environ.get("BRAIN_VOICE_DAEMON_INSTANCE_ID", "")
        self.is_pinned, self.is_visible = True, True
        self.controls_visible = False
        self.awaiting_quota_animation = ""
        self.last_quota_remaining: tuple[int, int] | None = None
        self.announced_quota_deciles: tuple[int, int] | None = None
        self.root.attributes("-topmost", True)
        self.reaction_bag = ReactionPhraseBag()
        self.click_count, self.last_click_at = 0, 0.0
        self.emotion = ""
        self.speech_text = ""
        self.quota_client = CodexQuotaClient()
        self.quota_results: queue.Queue = queue.Queue(maxsize=1)
        self.quota_refresh_in_flight = False
        self.base_height = 300
        self.drag_origin = (0, 0, 0, 0)
        self.bubble_drag_origin = (0, 0, 0, 0)
        self.bubble_resize_origin = ("", 0, 0, 0, 0, 0, 0)
        self.bubble_resize_active = False
        self.bubble_manual_size: tuple[int, int] | None = None
        self.bubble_has_position = False
        self.bubble_root = tk.Toplevel(self.root)
        self.bubble_root.overrideredirect(True)
        self.bubble_root.configure(bg=TRANSPARENT_COLOR)
        self.bubble_root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.bubble_root.attributes("-topmost", True)
        self.bubble_root.withdraw()
        self.bubble = tk.Canvas(self.bubble_root, bg=TRANSPARENT_COLOR, bd=0, highlightthickness=0)
        self.bubble.pack(fill="both", expand=True)
        self.bubble.bind("<Configure>", self._draw_bubble)
        self._build_controls()
        self.player.set_controls_visible(False)
        self.root.bind("<Configure>", self._layout_controls, add="+")
        self.root.bind("<Configure>", self._redraw_bubble_tail, add="+")
        for widget in (self.root, self.label):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
        self.bubble.bind("<Motion>", self._bubble_pointer_motion)
        self.bubble.bind("<Leave>", self._bubble_pointer_leave)
        self.bubble.bind("<ButtonPress-1>", self._bubble_pointer_press)
        self.bubble.bind("<B1-Motion>", self._bubble_drag_move)
        self.bubble.bind("<ButtonRelease-1>", self._bubble_resize_end)
        self.label.bind("<ButtonRelease-1>", self._label_click)
        # Resolve the placed label to its real viewport before the first HD
        # frame is resized. Otherwise Tk can cache a 1x1 startup framebuffer.
        self.root.update_idletasks()
        self._set_state("awaiting")
        self.root.after(POLL_INTERVAL_MS, self._poll)
        self.root.after(100, self._refresh_quotas)
        self.root.after(250, self._consume_quota_result)
        self.root.after(100, self._poll_control_hover)

    def _draw_bubble(self, _event=None) -> None:
        width, height = self.bubble.winfo_width(), self.bubble.winfo_height()
        self.bubble.delete("all")
        if width <= 2 or height <= 2:
            return
        bubble_bounds = (self.bubble_root.winfo_x(), self.bubble_root.winfo_y(), width, height)
        avatar_bounds = (self.root.winfo_x(), self.root.winfo_y(), self.root.winfo_width(), self.root.winfo_height())
        side = bubble_tail_side(bubble_bounds, avatar_bounds)
        avatar_center = (
            avatar_bounds[0] + avatar_bounds[2] / 2 - bubble_bounds[0],
            avatar_bounds[1] + avatar_bounds[3] / 2 - bubble_bounds[1],
        )
        body, tail_points = bubble_tail_geometry(side, width, height, avatar_center)
        left, top, right, bottom = body
        radius = min(18, max(10, round(min(right - left, bottom - top) * .08)))
        self.bubble.create_polygon(tail_points, fill="#fff8fd", outline="#f062b7", width=BUBBLE_BORDER)
        points = (left+radius,top,right-radius,top,right,top,right,bottom-radius,right,bottom,left,bottom,left,bottom-radius,left,top+radius,left,top)
        self.bubble.create_polygon(points,smooth=True,splinesteps=24,fill="#fff8fd",outline="#f062b7",width=3)
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

    def _bubble_close_hover(self, active: bool) -> None:
        self.bubble.configure(cursor="hand2" if active else "")
        self.bubble.itemconfigure("bubble-close-icon", fill="#d62839" if active else "#111111")

    def _bubble_corner_at(self, x: int, y: int) -> str:
        width, height = self.bubble.winfo_width(), self.bubble.winfo_height()
        tail = bubble_tail_height(width)
        corners = {
            "nw": (tail, tail),
            "ne": (width - tail, tail),
            "sw": (tail, height - tail),
            "se": (width - tail, height - tail),
        }
        corner, distance = min(
            ((name, ((x - point_x) ** 2 + (y - point_y) ** 2) ** .5) for name, (point_x, point_y) in corners.items()),
            key=lambda item: item[1],
        )
        return corner if distance <= BUBBLE_RESIZE_HANDLE else ""

    def _bubble_pointer_motion(self, event) -> None:
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
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill="#d62885",
            outline="",
            tags="resize-indicator",
        )

    def _bubble_pointer_leave(self, _event=None) -> None:
        if not self.bubble_resize_active:
            self.bubble.delete("resize-indicator")
            self.bubble.configure(cursor="")

    def _bubble_pointer_press(self, event) -> str | None:
        corner = self._bubble_corner_at(event.x, event.y)
        if corner:
            return self._bubble_resize_start(event, corner)
        self._bubble_drag_start(event)
        return None

    def _bubble_resize_start(self, event, corner: str) -> str:
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

    def _bubble_resize_end(self, _event=None) -> None:
        self.bubble_resize_active = False

    def _bubble_resize_move(self, event) -> str:
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

    def _redraw_bubble_tail(self, _event=None) -> None:
        if self.speech_text and self.bubble_root.state() != "withdrawn":
            self.bubble.after_idle(self._draw_bubble)

    def _set_text(self, text: str, emotion: str = "") -> None:
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
        tail_space = bubble_tail_height(bubble_width) * 2
        text_width = max(20, bubble_width - tail_space - BUBBLE_TEXT_PAD_X - BUBBLE_RIGHT_PAD)
        text_height = self._render_bubble_text(0, 0, text_width, probe=True)
        return bubble_required_height(width=bubble_width, text_height=text_height)

    def _render_bubble_text(self, x: int, y: int, width: int, probe: bool = False) -> int:
        """Render Markdown-like narrative blocks and return their combined height."""
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
        screen_width, screen_height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        height = min(height, max(100, screen_height - (BUBBLE_SCREEN_MARGIN * 2)))
        if self.bubble_has_position:
            x = max(BUBBLE_SCREEN_MARGIN, min(self.bubble_root.winfo_x(), screen_width - width - BUBBLE_SCREEN_MARGIN))
            y = max(BUBBLE_SCREEN_MARGIN, min(self.bubble_root.winfo_y(), screen_height - height - BUBBLE_SCREEN_MARGIN))
        else:
            x, y = detached_bubble_position(
                (screen_width, screen_height),
                (self.root.winfo_x(), self.root.winfo_y(), self.root.winfo_width(), self.root.winfo_height()),
                (width, height),
            )
            self.bubble_has_position = True
        self.bubble_root.geometry(f"{width}x{height}+{x}+{y}")

    def _dismiss_bubble(self) -> None:
        """Dismiss only the current visual message; voice and avatar keep running."""
        self.bubble_root.withdraw()

    def _bubble_drag_start(self, event) -> None:
        self.bubble_drag_origin = event.x_root, event.y_root, self.bubble_root.winfo_x(), self.bubble_root.winfo_y()

    def _bubble_drag_move(self, event) -> str:
        if self.bubble_resize_active:
            return self._bubble_resize_move(event)
        x, y, window_x, window_y = self.bubble_drag_origin
        next_x, next_y = window_x + event.x_root - x, window_y + event.y_root - y
        self.bubble_root.geometry(f"+{next_x}+{next_y}")
        self.bubble.after_idle(self._draw_bubble)
        return "break"

    def _build_controls(self) -> None:
        style = {"bg":"#101820","activebackground":"#172536","fg":"white","activeforeground":"white","bd":0,"highlightthickness":0,"font":("Segoe UI Symbol",18,"bold")}
        self.pin = tk.Button(self.root,text="📌",command=self._toggle_pin,cursor="hand2",**style)
        self.pin.place(x=6,y=4,anchor="nw",width=42,height=42)
        grip_style = {key:value for key,value in style.items() if not key.startswith("active")}
        self.grip = tk.Label(self.root,text="◢",cursor="size_nw_se",**grip_style)
        self.grip.place(relx=1,rely=1,anchor="se",width=28,height=28)
        self.grip.bind("<ButtonPress-1>", lambda event: "break")
        self.grip.bind("<B1-Motion>", self._resize_move)
        self._layout_controls()

    def _layout_controls(self, _event=None) -> None:
        width = max(1,self.root.winfo_width())
        size = max(32,min(58,round(width*.18)))
        grip_size = max(22,min(38,round(width*.12)))
        pad = max(4,round(width*.025))
        font_size = max(14,round(size*.45))
        self.pin.configure(font=("Segoe UI Symbol",font_size,"bold"))
        self.grip.configure(font=("Segoe UI Symbol",max(12,round(grip_size*.55)),"bold"))
        if not self.controls_visible:
            self.pin.place_forget()
            self.grip.place_forget()
            return
        if not self.speech_text:
            self.pin.place(x=pad,y=pad,anchor="nw",width=size,height=size)
        self.grip.place(relx=1,rely=1,anchor="se",width=grip_size,height=grip_size)

    def _poll_control_hover(self) -> None:
        """Resolve hover from global coordinates, including transparent pixels."""
        pointer_x, pointer_y = self.root.winfo_pointerxy()
        left, top = self.root.winfo_x(), self.root.winfo_y()
        inside = left <= pointer_x < left + self.root.winfo_width() and top <= pointer_y < top + self.root.winfo_height()
        self._set_controls_visible(inside and self.is_visible)
        self.root.after(100, self._poll_control_hover)

    def _set_controls_visible(self, visible: bool) -> None:
        """Apply one visibility state to native widgets and raster controls."""
        if visible == self.controls_visible:
            return
        self.controls_visible = visible
        self.player.set_controls_visible(visible)
        self._layout_controls()

    def _drag_start(self, event) -> None:
        self.drag_origin = event.x_root,event.y_root,self.root.winfo_x(),self.root.winfo_y()

    def _drag_move(self, event) -> None:
        x,y,wx,wy = self.drag_origin
        self.root.geometry(f"+{wx+event.x_root-x}+{wy+event.y_root-y}")

    def _resize_move(self, event) -> str:
        width = max(MIN_WIDTH,event.x_root-self.root.winfo_x())
        height = max(MIN_HEIGHT,round(width*4/3))
        width = round(height*3/4)
        self.base_height = height
        self.root.geometry(f"{width}x{height}+{self.root.winfo_x()}+{self.root.winfo_y()}")
        return "break"

    def _post(self, path: str) -> None:
        request = Request(f"{VOICE_DAEMON_URL}{path}",data=b"{}",method="POST",headers={"Content-Type":"application/json"})
        urlopen(request,timeout=.5).close()

    def _toggle_pin(self) -> None:
        self.is_pinned = not self.is_pinned
        self._apply_topmost()
        self.pin.configure(fg="#3b8cff" if self.is_pinned else "white")
        if self.is_pinned:
            self.root.lift()

    def _apply_topmost(self) -> None:
        """Apply temporary speaking priority over the persisted pin choice."""
        playback_active = self.state in {"preparing", "speaking"}
        topmost = self.is_pinned or playback_active
        NativeWindowPriority.apply(self.root, topmost=topmost, show=playback_active)
        NativeWindowPriority.apply(self.bubble_root, topmost=topmost, show=False)

    def _toggle_playback(self) -> None:
        try: self._post("/pause" if self.state in {"muted_replay", "preparing", "speaking"} else "/replay")
        except Exception: pass

    def _toggle_mute(self) -> None:
        """Toggle daemon-owned audio output while retaining visual messages."""
        try:
            self._post("/mute")
        except Exception:
            pass

    def _label_click(self, event) -> None:
        mute_center, mute_radius = mute_button_geometry(self.label.winfo_width(), self.label.winfo_height())
        if (event.x - mute_center[0]) ** 2 + (event.y - mute_center[1]) ** 2 <= mute_radius ** 2:
            self._toggle_mute()
            return
        left_center, right_center, quota_radius = quota_ring_geometry(self.label.winfo_width(), self.label.winfo_height())
        if any((event.x - x) ** 2 + (event.y - y) ** 2 <= quota_radius ** 2 for x, y in (left_center, right_center)):
            self._start_quota_refresh()
            return
        (center_x, center_y), radius = playback_button_geometry(self.label.winfo_width(), self.label.winfo_height())
        if (event.x-center_x)**2 + (event.y-center_y)**2 <= radius**2:
            self._toggle_playback()
        else:
            self._avatar_click(event)

    def _avatar_click(self, _event) -> None:
        if self.state in {"preparing", "speaking"}:
            return
        now = time.monotonic()
        self.click_count = self.click_count + 1 if now - self.last_click_at <= 2.0 else 1
        self.last_click_at = now
        if self.click_count >= 2:
            self.click_count = 0
            try:
                phrase = self.reaction_bag.draw()
                request = Request(
                    f"{VOICE_DAEMON_URL}/speak",
                    data=json.dumps({"text": phrase, "lang": "es", "emotion": "reacting", "preludeSeconds": 1}).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type":"application/json"},
                )
                urlopen(request,timeout=.5).close()
            except Exception: pass

    def _refresh_quotas(self) -> None:
        """Read Codex quotas outside Tk's render thread once per minute."""
        self._start_quota_refresh()
        self.root.after(60_000, self._refresh_quotas)

    def _start_quota_refresh(self) -> None:
        """Start one non-blocking quota read unless another is active."""
        if not self.quota_refresh_in_flight:
            self.quota_refresh_in_flight = True
            self.player.set_quota_refreshing(True)
            threading.Thread(target=self._read_quotas, daemon=True, name="codex-quotas").start()

    def _read_quotas(self) -> None:
        """Publish one App Server quota result to the Tk thread."""
        snapshot = self.quota_client.read()
        if self.last_quota_remaining is None:
            # The App Server can expose one cached warm-up value immediately
            # after initialization. Its next response owns the current truth.
            time.sleep(.25)
            snapshot = self.quota_client.read() or snapshot
        try:
            self.quota_results.put_nowait(snapshot)
        except queue.Full:
            pass
        self.quota_refresh_in_flight = False

    def _consume_quota_result(self) -> None:
        """Apply a pending quota snapshot without blocking animation."""
        try:
            snapshot = self.quota_results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.player.set_quota_refreshing(False)
            if snapshot is not None:
                five_hour_reset, weekly_reset = self._quota_reset_labels(snapshot)
                self.player.set_quotas(
                    snapshot.five_hour_percent,
                    snapshot.weekly_percent,
                    five_hour_reset,
                    weekly_reset,
                )
                remaining = (100 - snapshot.five_hour_percent, 100 - snapshot.weekly_percent)
                current_deciles = tuple(self._quota_decile(value) for value in remaining)
                if self.announced_quota_deciles is None:
                    self.announced_quota_deciles = current_deciles
                else:
                    announced = list(self.announced_quota_deciles)
                    warnings = []
                    labels = ("la cuota de cinco horas", "la cuota semanal")
                    for index, current_decile in enumerate(current_deciles):
                        previous_remaining = self.last_quota_remaining[index] if self.last_quota_remaining else remaining[index]
                        if remaining[index] - previous_remaining >= 10:
                            announced[index] = current_decile
                        elif current_decile < announced[index]:
                            announced[index] = current_decile
                            warnings.append(f"{labels[index]} bajó a {remaining[index]} por ciento restante")
                    self.announced_quota_deciles = (announced[0], announced[1])
                    if warnings:
                        self._speak_quota_warning(warnings)
                self.last_quota_remaining = remaining
                next_animation = self._quota_awaiting_animation(
                    five_hour_used=snapshot.five_hour_percent,
                    weekly_used=snapshot.weekly_percent,
                )
                if next_animation != self.awaiting_quota_animation:
                    self.awaiting_quota_animation = next_animation
                    if self.state == "awaiting":
                        self._set_state("awaiting", force=True)
        self.root.after(250, self._consume_quota_result)

    @staticmethod
    def _quota_awaiting_animation(five_hour_used: int, weekly_used: int) -> str:
        """Select the low-quota animation at ten percent remaining or less."""
        if weekly_used >= 90:
            return "sad"
        if five_hour_used >= 90:
            return "tired"
        return ""

    @staticmethod
    def _quota_decile(remaining: int) -> int:
        """Round remaining quota upward to its stable ten-percent threshold."""
        bounded = max(0, min(100, int(remaining)))
        return min(100, ((bounded + 9) // 10) * 10)

    @staticmethod
    def _quota_reset_labels(snapshot) -> tuple[str, str]:
        """Format reset epochs as local clock time and Gregorian day/month."""
        weekly = datetime.fromtimestamp(snapshot.weekly_resets_at).astimezone()
        months = ("ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC")
        five_hour_label = "--:--"
        if snapshot.five_hour_resets_at:
            five_hour = datetime.fromtimestamp(snapshot.five_hour_resets_at).astimezone()
            five_hour_label = five_hour.strftime("%H:%M")
        return five_hour_label, f"{weekly.day:02d} {months[weekly.month - 1]}"

    def _speak_quota_warning(self, warnings: list[str]) -> None:
        """Enqueue one combined spoken warning without blocking the quota thread."""
        if not warnings:
            return
        if len(warnings) == 1:
            sentence = f"Atención, {warnings[0]}."
        else:
            sentence = f"Atención, {warnings[0]} y {warnings[1]}."
        try:
            request = Request(
                f"{VOICE_DAEMON_URL}/speak",
                data=json.dumps({"text": sentence, "lang": "es", "emotion": "concerned"}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            urlopen(request, timeout=.5).close()
        except Exception:
            pass

    def _show(self) -> None:
        if not self.is_visible: self.root.deiconify(); self.is_visible=True

    def _hide(self) -> None:
        if self.is_visible: self.player.stop(); self.root.withdraw(); self.is_visible=False

    def _set_state(self,state: str,force: bool=False,emotion: str="") -> None:
        changed = state != self.state or emotion != self.emotion
        self.state = state
        self.emotion = emotion
        self.player.set_playing(state in {"muted_replay", "speaking"})
        if state in {"preparing", "speaking"}:
            self._show()
        self._apply_topmost()
        animation, fallback_state = self._animation_for_state(state=state, emotion=emotion)
        path = avatar_asset(animation, fallback_state=fallback_state)
        needs_recovery = self.player.displayed_path != str(path)
        if (changed or force or needs_recovery) and path.is_file():
            self.player.load(path)

    def _animation_for_state(self, state: str, emotion: str) -> tuple[str, str]:
        """Resolve thinking as awaiting and speaking only after playback starts."""
        if state in {"preparing", "speaking"}:
            return emotion or "speaking", "speaking"
        if state == "working":
            return "working", "awaiting"
        if state in {"awaiting", "thinking", "muted", "muted_replay"}:
            return self.awaiting_quota_animation or "awaiting", "awaiting"
        return state, "speaking"

    def _poll(self) -> None:
        """Poll daemon transport without treating presentation faults as daemon loss."""
        try:
            with urlopen(f"{VOICE_DAEMON_URL}/status",timeout=.2) as response: payload=json.loads(response.read())
        except Exception:
            if time.monotonic()-self.last_seen >= DAEMON_LOSS_GRACE_SECONDS: self._shutdown_window(); return
            self.root.after(POLL_INTERVAL_MS,self._poll)
            return
        if self.daemon_instance_id and payload.get("instanceId") != self.daemon_instance_id:
            self._shutdown_window(); return
        self.last_seen=time.monotonic()
        try:
            state = payload.get("state", "awaiting")
            emotion = payload.get("emotion", "") or ("happy" if state == "speaking" else "")
            self.player.set_muted(bool(payload.get("muted", False)))
            self._set_state(state, emotion=emotion)
            self._set_text(payload.get("text",""), emotion=emotion)
        except Exception:
            pass
        self.root.after(POLL_INTERVAL_MS,self._poll)

    def _shutdown_window(self) -> None:
        """Release owned integrations when the daemon lifecycle ends."""
        self.quota_client.close()
        self.player.stop()
        self.bubble_root.destroy()
        self.root.destroy()

    def run(self) -> None: self.root.mainloop()
