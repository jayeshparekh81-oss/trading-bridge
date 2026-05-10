"""Hour-of-day signal — 0..23 for intraday candles, None for daily+.

Detects bar frequency by inter-bar timestamp gap. If the first
two bars are >= 24 hours apart we treat the series as daily-or-
larger and return all-``None`` (hour-of-day is meaningless when
each bar is one full day).

Useful as a session-of-day filter for intraday strategies (e.g.
avoid the open and close in volatile names; favour morning over
afternoon).

Default hours: 0..23 IST (timestamps are assumed naive-or-IST;
tz-aware UTC timestamps land in the wrong hour and the operator
should pre-normalise).

Output length equals input length.

Edge cases:
    * Empty input -> ``[]``.
    * Daily / weekly / monthly frequency -> all-``None``.
    * Single bar -> all-``None`` (can't infer frequency).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta


def hour_of_day(
    timestamps: Sequence[datetime],
) -> list[float | None]:
    """0..23 hour for intraday timestamps; all-None for daily+."""
    n = len(timestamps)
    if n == 0:
        return []
    if n < 2:
        return [None] * n
    # Frequency detection: if the first two bars are 24h+ apart,
    # we're not on intraday data.
    if timestamps[1] - timestamps[0] >= timedelta(hours=24):
        return [None] * n
    return [float(ts.hour) for ts in timestamps]


__all__ = ["hour_of_day"]
