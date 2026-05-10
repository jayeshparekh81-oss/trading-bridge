"""Day-of-week signal — 0 (Mon) through 6 (Sun) per bar.

Reads each candle's timestamp and emits the ISO weekday number
shifted to 0-indexed Mon..Sun. Useful as a "day-of-week effect"
filter for intraday strategies (e.g. avoid Friday afternoons,
prefer Tuesday mornings).

Output range: ``[0, 6]``. Distinct integers per day:

    0 -> Monday
    1 -> Tuesday
    2 -> Wednesday
    3 -> Thursday
    4 -> Friday
    5 -> Saturday   (no NSE trading; only present in synthetic data)
    6 -> Sunday     (likewise)

Output length equals input length. No warm-up — every bar gets
a value as long as its timestamp is valid.

Edge cases:
    * Empty input -> ``[]``.
    * Mismatched timestamp count -> ``ValueError`` (handled by the
      dispatcher; this calc takes only the timestamps).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime


def day_of_week_signal(
    timestamps: Sequence[datetime],
) -> list[float | None]:
    """0=Mon..6=Sun for each candle's timestamp."""
    return [float(ts.weekday()) for ts in timestamps]


__all__ = ["day_of_week_signal"]
