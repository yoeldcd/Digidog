# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Tk scheduling adapter for the shared quota view-model."""

from __future__ import annotations

import queue
import threading
import time
from typing import Any

from brain.presentation.avatar.interactivity.quota_view_model import (
    QuotaThresholdTracker, QuotaViewModel, quota_decile, quota_reset_label,
)


class TkQuotaControllerMixin:
    """Schedule quota transport and project shared decisions into Tk views.

    Attributes:
        root (Any): Main avatar window root widget collaborator.
        player (Any): Animated GIF player collaborator.
        quota_client (Any): Source of avatar quota telemetry collaborator.
        quota_tracker (QuotaThresholdTracker): Tracker for quota threshold events collaborator.
        quota_results (queue.Queue): Queue transferring quota snapshots from worker thread.
        quota_refresh_in_flight (bool): Whether a quota fetch thread is active.
        ignore_quota_state (bool): Whether quota emotion overrides are ignored.
        awaiting_quota_animation (str): Active animation key while quota is loading.
        state (str): Current presentation state name.
        transport (Any): Daemon transport client adapter collaborator.
    """

    def _refresh_quotas(self) -> None:
        """Start a quota refresh and expose its pending state to the renderer.

        Returns:
            None.
        """
        self._start_quota_refresh()
        self.root.after(60_000, self._refresh_quotas)

    def _start_quota_refresh(self) -> None:
        """Schedule the asynchronous quota request and its completion poll.

        Returns:
            None.
        """
        if not self.quota_refresh_in_flight:
            self.quota_refresh_in_flight = True
            self.player.set_quota_refreshing(True)
            threading.Thread(target=self._read_quotas, daemon=True, name="codex-quotas").start()

    def _read_quotas(self) -> None:
        """Read the latest quota snapshot from the daemon adapter.

        Returns:
            None.
        """
        snapshot = self.quota_client.read()

        if self.quota_tracker.previous_remaining is None:
            time.sleep(.25)
            snapshot = self.quota_client.read() or snapshot

        try:
            self.quota_results.put_nowait(snapshot)
        except queue.Full:
            pass

        self.quota_refresh_in_flight = False

    def _consume_quota_result(self) -> None:
        """Project the completed quota snapshot into rings, labels, and warnings.

        Returns:
            None.
        """
        try:
            snapshot = self.quota_results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.player.set_quota_refreshing(False)

            if snapshot is not None:
                view = QuotaViewModel.from_snapshot(snapshot, ignore_emotion=self.ignore_quota_state)

                self.player.set_quotas(
                    view.five_hour_used, view.weekly_used,
                    view.five_hour_reset_label, view.weekly_reset_label,
                )

                warnings = self.quota_tracker.consume(view)

                if warnings:
                    self._speak_quota_warning(list(warnings))

                if view.awaiting_animation != self.awaiting_quota_animation:
                    self.awaiting_quota_animation = view.awaiting_animation

                    if self.state == "awaiting":
                        self._set_state("awaiting", force=True)

        self.root.after(250, self._consume_quota_result)

    @staticmethod
    def _quota_awaiting_animation(five_hour_used: int, weekly_used: int) -> str:
        """Choose the waiting glyph while quota data is unavailable.

        Args:
            five_hour_used (int): Consumed five-hour quota percentage used by the waiting glyph.
            weekly_used (int): Consumed weekly quota percentage used by the waiting glyph.

        Returns:
            str: Animation key selected for the quota-waiting state.
        """
        class Snapshot:
            """Minimal quota snapshot used for animation projection.

            Attributes:
                five_hour_percent (int): Consumed five-hour quota percentage.
                weekly_percent (int): Consumed weekly quota percentage.
                five_hour_resets_at (int): Placeholder five-hour reset timestamp.
                weekly_resets_at (int): Placeholder weekly reset timestamp.
            """

            five_hour_percent = five_hour_used
            weekly_percent = weekly_used
            five_hour_resets_at = 0
            weekly_resets_at = 0

        return QuotaViewModel.from_snapshot(Snapshot()).awaiting_animation

    @staticmethod
    def _quota_decile(remaining: int) -> int:
        """Round a remaining percentage to the display decile used by the rings.

        Args:
            remaining (int): Remaining quota percentage to round for the ring display.

        Returns:
            int: Rounded remaining-percentage decile.
        """
        return quota_decile(remaining)

    @staticmethod
    def _quota_reset_labels(snapshot: Any) -> tuple[str, str]:
        """Extract human-readable reset labels from a quota snapshot.

        Args:
            snapshot (Any): Parsed quota snapshot returned by the daemon adapter.

        Returns:
            tuple[str, str]: Five-hour and weekly reset labels.
        """
        return (
            quota_reset_label(snapshot.five_hour_resets_at, weekly=False),
            quota_reset_label(snapshot.weekly_resets_at, weekly=True),
        )

    def _speak_quota_warning(self, warnings: list[str]) -> None:
        """Send quota warnings to the speech channel when they become actionable.

        Args:
            warnings (list[str]): Human-readable quota warnings ready for speech.

        Returns:
            None.
        """
        if not warnings:
            return

        joined = warnings[0] if len(warnings) == 1 else f"{warnings[0]} y {warnings[1]}"

        try:
            self.transport.post("/speak", {
                "text": f"Atención, {joined}.", "lang": "es", "emotion": "concerned",
            })
        except OSError:
            pass