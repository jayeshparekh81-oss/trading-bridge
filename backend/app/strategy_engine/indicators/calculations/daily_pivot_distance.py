"""Distance from the current day's classic pivot, in % of pivot.

Per bar::

    pivot = (prior_day_H + prior_day_L + prior_day_C) / 3
    out[i] = (close[i] - pivot) / pivot * 100

Uses the *prior* trading day's HLC so the value is forward-look-
safe (no leak from later-in-the-day bars). Bars on the very first
day of the input series are ``None``.

Requires per-bar ``timestamps`` for day grouping.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Prior-day pivot == 0 (degenerate) -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime


def daily_pivot_distance(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    timestamps: Sequence[datetime],
) -> list[float | None]:
    """% distance from the prior-day pivot."""
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(timestamps):
        raise ValueError(
            f"highs, lows, closes, timestamps must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(timestamps)}."
        )
    if n == 0:
        return []

    # Group bar indices by trading date.
    by_date: dict[object, list[int]] = {}
    date_keys: list[object] = []
    for i, ts in enumerate(timestamps):
        d = ts.date()
        if d not in by_date:
            by_date[d] = []
            date_keys.append(d)
        by_date[d].append(i)

    # Per-day HLC summary.
    daily_pivot: dict[object, float] = {}
    for d, indices in by_date.items():
        dh = max(highs[k] for k in indices)
        dl = min(lows[k] for k in indices)
        dc = closes[indices[-1]]
        daily_pivot[d] = (dh + dl + dc) / 3.0

    out: list[float | None] = [None] * n
    for bar_idx in range(n):
        d = timestamps[bar_idx].date()
        date_pos = date_keys.index(d)
        if date_pos == 0:
            continue
        prior_pivot = daily_pivot[date_keys[date_pos - 1]]
        if prior_pivot == 0:
            continue
        out[bar_idx] = (closes[bar_idx] - prior_pivot) / prior_pivot * 100.0
    return out


__all__ = ["daily_pivot_distance"]
