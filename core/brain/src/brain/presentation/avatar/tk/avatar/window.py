# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Borderless transparent avatar window coupled to the voice daemon."""

from __future__ import annotations

import os
import queue
import time
import tkinter as tk
from typing import Any

from brain.infrastructure.codex.quota_client import CodexQuotaClient
from brain.presentation.avatar.interactivity.presentation_state import ProjectedMessageState
from brain.presentation.avatar.interactivity.quota_view_model import QuotaThresholdTracker
from brain.presentation.avatar.interactivity.reactions import ReactionPhraseBag, load_avatar_interaction_config
from brain.presentation.avatar.tk.avatar.renderer import AnimatedGif
from brain.presentation.avatar.tk.runtime.backend import TkDaemonAdapter
from brain.presentation.avatar.tk.bubble.geometry import (
    BUBBLE_FONT, bubble_required_height, bubble_tail_geometry, bubble_tail_height,
    bubble_tail_side, detached_bubble_position, detached_bubble_width,
    dialogue_markdown_blocks,
)
from brain.presentation.avatar.tk.bubble.view import TkBubbleViewMixin
from brain.presentation.avatar.tk.controls.view import TkControlsMixin
from brain.presentation.avatar.tk.runtime.message import TkMessageController
from brain.presentation.avatar.tk.quota.controller import TkQuotaControllerMixin
from brain.presentation.avatar.tk.runtime.adapter import TkRuntimeAdapterMixin
from brain.presentation.avatar.window.config import (
    MIN_HEIGHT, MIN_WIDTH, POLL_INTERVAL_MS, TRANSPARENT_COLOR, default_geometry,
)


class AvatarWindow(TkRuntimeAdapterMixin, TkQuotaControllerMixin, TkControlsMixin, TkBubbleViewMixin):
    """Own the borderless Tk avatar, controls, and detached message bubble.

    Attributes:
        root (tk.Tk): Main transparent avatar window.
        label (tk.Label): Tk label hosting rendered avatar frames.
        player (AnimatedGif): GIF compositor and control renderer.
        transport (TkDaemonAdapter): HTTP transport client for daemon commands.
        presentation (ProjectedMessageState): Current active presentation state.
        message_controller (TkMessageController): Controller for message history and replay target.
        quota_tracker (QuotaThresholdTracker): Tracker for quota threshold events.
        state (str): Current runtime state identifier.
        last_seen (float): Monotonic timestamp of last daemon contact.
        ignore_quota_state (bool): Whether quota emotion overrides are ignored.
        reaction_bag (ReactionPhraseBag): Random phrase bag for double-click reactions.
        avatar_click_job (str | None): Scheduled callback ID for single-click confirmation.
        daemon_instance_id (str): Expected voice daemon instance ID.
        is_pinned (bool): Whether avatar window stays always on top.
        is_visible (bool): Whether avatar window is shown.
        controls_visible (bool): Whether controls overlay is visible.
        awaiting_quota_animation (str): Active animation key while quota is loading.
        last_quota_remaining (tuple[int, int] | None): Last recorded remaining quota values.
        announced_quota_deciles (tuple[int, int] | None): Last announced quota decile levels.
        emotion (str): Current active emotion string.
        speech_text (str): Current speech text rendered in bubble.
        quota_client (CodexQuotaClient): Source of avatar quota telemetry.
        quota_results (queue.Queue): Queue transferring quota snapshots from worker thread.
        quota_refresh_in_flight (bool): Whether a quota fetch thread is active.
        base_height (int): Baseline height for aspect-ratio window resizing.
        drag_origin (tuple[int, int, int, int]): Origin coordinates for window drag gesture.
        bubble_drag_origin (tuple[int, int, int, int]): Origin coordinates for bubble drag gesture.
        bubble_resize_origin (tuple[str, int, int, int, int, int, int]): Origin parameters for bubble resize gesture.
        bubble_resize_active (bool): Whether bubble resize gesture is in progress.
        bubble_manual_size (tuple[int, int] | None): Manually resized bubble dimensions (width, height).
        bubble_has_position (bool): Whether bubble has a valid screen position.
        bubble_root (tk.Toplevel): Detached rich-message window.
        bubble (tk.Canvas): Canvas rendering message bubble and controls.
    """

    def __init__(self) -> None:
        """Initialize the component with its required Tk collaborators.

        Returns:
            None.
        """
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.geometry(default_geometry(self.root.winfo_screenwidth()))
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)

        self.label = tk.Label(self.root, bg=TRANSPARENT_COLOR, bd=0, highlightthickness=0)
        self.label.place(x=0, y=0, relwidth=1, relheight=1)

        self.player = AnimatedGif(self.label)
        self.transport = TkDaemonAdapter()
        self.presentation = ProjectedMessageState()
        self.message_controller = TkMessageController()
        self.quota_tracker = QuotaThresholdTracker()

        self.state, self.last_seen = "", time.monotonic()
        self.ignore_quota_state, configured_reactions = load_avatar_interaction_config()
        self.reaction_bag = ReactionPhraseBag(reactions=configured_reactions)
        self.avatar_click_job: str | None = None
        self.daemon_instance_id = os.environ.get("BRAIN_VOICE_DAEMON_INSTANCE_ID", "")
        self.is_pinned, self.is_visible = True, True
        self.controls_visible = False
        self.awaiting_quota_animation = ""
        self.last_quota_remaining: tuple[int, int] | None = None
        self.announced_quota_deciles: tuple[int, int] | None = None

        self.root.attributes("-topmost", True)
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
        self.root.after_idle(self._signal_window_ready)
        self.root.after(POLL_INTERVAL_MS, self._poll)
        self.root.after(100, self._refresh_quotas)
        self.root.after(250, self._consume_quota_result)
        self.root.after(100, self._poll_control_hover)

    def run(self) -> None:
        """Enter the Tk event loop for this avatar window.

        Returns:
            None.
        """
        self.root.mainloop()
