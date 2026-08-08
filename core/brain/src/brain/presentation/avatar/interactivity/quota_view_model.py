# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Toolkit-neutral quota labels, animation, and threshold decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Protocol


_MONTHS = ("ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC")


class QuotaSnapshotPort(Protocol):
    """Values required from any quota transport.

    Attributes:
        five_hour_percent (int): Percentage consumed in the five-hour window.
        weekly_percent (int): Percentage consumed in the weekly window.
        five_hour_resets_at (int): Five-hour reset epoch.
        weekly_resets_at (int): Weekly reset epoch.
    """

    five_hour_percent: int
    weekly_percent: int
    five_hour_resets_at: int
    weekly_resets_at: int


@dataclass(frozen=True, slots=True)
class QuotaViewModel:
    """Complete quota projection consumed by either toolkit.

    Attributes:
        five_hour_used (int): Bounded five-hour quota percentage.
        weekly_used (int): Bounded weekly quota percentage.
        five_hour_remaining (int): Remaining five-hour quota percentage.
        weekly_remaining (int): Remaining weekly quota percentage.
        five_hour_reset_label (str): Local five-hour reset label.
        weekly_reset_label (str): Local weekly reset label.
        awaiting_animation (str): Emotion state selected for the quota level.
    """

    five_hour_used: int
    weekly_used: int
    five_hour_remaining: int
    weekly_remaining: int
    five_hour_reset_label: str
    weekly_reset_label: str
    awaiting_animation: str

    @classmethod
    def from_snapshot(
        cls,
        snapshot: QuotaSnapshotPort,
        *,
        ignore_emotion: bool = False,
    ) -> "QuotaViewModel":
        """Normalize percentages, labels, and low-quota animation.

        Args:
            snapshot (QuotaSnapshotPort): Raw quota values from a transport.
            ignore_emotion (bool): Whether to suppress quota emotion selection.

        Returns:
            QuotaViewModel: Bounded quota values and presentation labels.
        """
        five_hour_used = _percentage(snapshot.five_hour_percent)
        weekly_used = _percentage(snapshot.weekly_percent)

        animation = ""

        if not ignore_emotion:
            if weekly_used >= 90:
                animation = "sad"
            elif five_hour_used >= 90:
                animation = "tired"
            else:
                animation = "happy"

        return cls(
            five_hour_used=five_hour_used,
            weekly_used=weekly_used,
            five_hour_remaining=100 - five_hour_used,
            weekly_remaining=100 - weekly_used,
            five_hour_reset_label=quota_reset_label(snapshot.five_hour_resets_at, weekly=False),
            weekly_reset_label=quota_reset_label(snapshot.weekly_resets_at, weekly=True),
            awaiting_animation=animation,
        )


@dataclass(slots=True)
class QuotaThresholdTracker:
    """Track announced remaining deciles without toolkit state duplication.

    Attributes:
        announced (tuple[int, int] | None): Last announced deciles.
        previous_remaining (tuple[int, int] | None): Previous raw remaining values.
    """

    announced: tuple[int, int] | None = None
    previous_remaining: tuple[int, int] | None = None

    def consume(self, view: QuotaViewModel) -> tuple[str, ...]:
        """Return warnings only when a remaining quota crosses a lower decile.

        Args:
            view (QuotaViewModel): Current bounded quota projection.

        Returns:
            tuple[str, ...]: Newly crossed threshold messages.
        """
        remaining = (view.five_hour_remaining, view.weekly_remaining)
        current = tuple(quota_decile(value) for value in remaining)

        if self.announced is None:
            self.announced = current
            self.previous_remaining = remaining
            return ()

        announced = list(self.announced)
        warnings: list[str] = []
        labels = ("la cuota de cinco horas", "la cuota semanal")
        previous = self.previous_remaining or remaining

        for index, threshold in enumerate(current):
            if remaining[index] - previous[index] >= 10:
                announced[index] = threshold
            elif threshold < announced[index]:
                announced[index] = threshold
                warnings.append(f"{labels[index]} bajó a {remaining[index]} por ciento restante")

        self.announced = (announced[0], announced[1])
        self.previous_remaining = remaining
        return tuple(warnings)


def quota_decile(remaining: int) -> int:
    """Round bounded remaining quota upward to a stable ten-percent step.

    Args:
        remaining (int): Remaining quota percentage.

    Returns:
        int: Remaining percentage rounded up to a ten-percent decile.
    """
    bounded = _percentage(remaining)

    return min(100, int(ceil(bounded / 10)) * 10)


def quota_reset_label(timestamp: int, *, weekly: bool) -> str:
    """Format a local reset epoch for the compact avatar meters.

    Args:
        timestamp (int): Reset epoch in local-time conversion.
        weekly (bool): Whether to format a day and month instead of a time.

    Returns:
        str: Compact local reset label.
    """
    if not timestamp:
        return "--:--" if not weekly else "-- ---"

    value = datetime.fromtimestamp(timestamp).astimezone()

    if weekly:
        return f"{value.day:02d} {_MONTHS[value.month - 1]}"

    return value.strftime("%H:%M")


def _percentage(value: int) -> int:
    """Clamp a raw quota percentage to the inclusive range zero through one hundred.

    Args:
        value (int): Raw quota percentage.

    Returns:
        int: Bounded integer percentage, or zero for invalid input.
    """
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0
