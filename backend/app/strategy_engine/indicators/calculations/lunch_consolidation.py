"""Lunch consolidation flag — quiet-hour boolean.

Per intraday bar, returns 1.0 if ALL of:

    * Bar's hour falls in [lunch_start_hour, lunch_end_hour)
    * Bar's volume is below the session's average volume so far
    * Bar's range is below the session's average range so far

Returns 0.0 otherwise (including bars outside lunch hours).

Useful as a chop-detection filter — strategies that want to
stand down during the typical low-conviction lunch period
(roughly 12:00-13:00 IST on Indian exchanges).

Defaults ``lunch_start_hour = 12``, ``lunch_end_hour = 13``.

Frequency-aware: returns all-``None`` for daily-or-larger
candles.

Output length equals input length.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Daily frequency -> all-``None``.
    * Bar before any lunch averages can form -> 0.0 (default-no).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta


def lunch_consolidation(
    highs: Sequence[float],
    lows: Sequence[float],
    volumes: Sequence[float],
    timestamps: Sequence[datetime],
    lunch_start_hour: int = 12,
    lunch_end_hour: int = 13,
) -> list[float | None]:
    """Lunch-consolidation per-bar flag."""
    if not isinstance(lunch_start_hour, int) or isinstance(lunch_start_hour, bool):
        raise ValueError(f"lunch_start_hour must be an int; got {lunch_start_hour!r}.")
    if not isinstance(lunch_end_hour, int) or isinstance(lunch_end_hour, bool):
        raise ValueError(f"lunch_end_hour must be an int; got {lunch_end_hour!r}.")
    if not 0 <= lunch_start_hour < lunch_end_hour <= 23:
        raise ValueError(
            f"lunch_start_hour < lunch_end_hour <= 23 required; "
            f"got start={lunch_start_hour}, end={lunch_end_hour}."
        )
    n = len(highs)
    if n != len(lows) or n != len(volumes) or n != len(timestamps):
        raise ValueError(
            f"highs, lows, volumes, timestamps must have the same length; "
            f"got {n}, {len(lows)}, {len(volumes)}, {len(timestamps)}."
        )
    if n == 0:
        return []
    if n < 2 or timestamps[1] - timestamps[0] >= timedelta(hours=24):
        return [None] * n

    out: list[float | None] = [None] * n
    current_date = None
    session_volume_sum = 0.0
    session_range_sum = 0.0
    bars_seen = 0
    for i, ts in enumerate(timestamps):
        if ts.date() != current_date:
            current_date = ts.date()
            session_volume_sum = 0.0
            session_range_sum = 0.0
            bars_seen = 0
        bar_range = highs[i] - lows[i]
        # Update running session averages BEFORE checking the
        # current bar so the comparison is against the pre-bar
        # context (avoids the bar comparing itself against
        # itself).
        if bars_seen == 0:
            avg_volume = volumes[i]
            avg_range = bar_range
        else:
            avg_volume = session_volume_sum / bars_seen
            avg_range = session_range_sum / bars_seen
        in_lunch = lunch_start_hour <= ts.hour < lunch_end_hour
        if in_lunch and volumes[i] < avg_volume and bar_range < avg_range:
            out[i] = 1.0
        else:
            out[i] = 0.0
        session_volume_sum += volumes[i]
        session_range_sum += bar_range
        bars_seen += 1
    return out


__all__ = ["lunch_consolidation"]
