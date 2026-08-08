# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt asynchronous quota transport bound to the shared quota view-model."""
from __future__ import annotations

import queue
import threading

from brain.presentation.avatar.interactivity.quota_view_model import QuotaViewModel


class QtQuotaControllerMixin:
    """Coordinate quota transport while delegating all quota policy."""

    def _refresh_quotas(self) -> None:
        """Trigger an asynchronous background quota fetch thread.

        Returns:
            None.
        """
        if self.quota_refreshing:
            return

        self.quota_refreshing = True
        self.controls.set_quota_refreshing(True)

        def worker() -> None:
            """Background thread routine fetching quota snapshot from client.

            Returns:
                None.
            """
            try:
                snapshot = self.quota_client.read()
            except Exception:
                snapshot = None

            while not self.quota_results.empty():
                try:
                    self.quota_results.get_nowait()
                except queue.Empty:
                    break

            self.quota_results.put(snapshot)

        threading.Thread(target=worker, daemon=True, name="qt-avatar-quota").start()

    def _consume_quota_result(self) -> None:
        """Process any pending background quota snapshot result on the main GUI thread.

        Returns:
            None.
        """
        try:
            snapshot = self.quota_results.get_nowait()
        except queue.Empty:
            return

        self.quota_refreshing = False
        self.controls.set_quota_refreshing(False)

        if snapshot is None:
            return

        view = QuotaViewModel.from_snapshot(snapshot, ignore_emotion=self.ignore_quota_state)
        self.controls.set_quotas(
            view.five_hour_used,
            view.weekly_used,
            view.five_hour_reset_label,
            view.weekly_reset_label,
        )
        self.last_quota_remaining = (view.five_hour_remaining, view.weekly_remaining)

        if view.awaiting_animation != self.awaiting_quota_animation:
            self.awaiting_quota_animation = view.awaiting_animation
            if self.state == "awaiting":
                self._set_state("awaiting", force=True)

