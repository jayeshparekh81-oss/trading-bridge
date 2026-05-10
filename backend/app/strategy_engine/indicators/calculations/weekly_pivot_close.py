"""Distance from the prior week's pivot, in % of the pivot.

For every bar we compute the *prior* completed week's classic
pivot ``P = (H + L + C) / 3`` and emit::

    out[i] = (close[i] - P_prior) / P_prior * 100

Where ``P_prior`` is the pivot of the most-recently-closed
calendar ISO-week relative to the current bar's date. Bars in the
same week as the most-recent close use the previous week's
pivot — the metric is forward-looking-safe, no future leak.

Requires per-bar ``timestamps`` (the dispatcher passes them in
from the Candle list). Bars before the first pivot becomes
available are ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Less than one full prior week of data -> all-``None``.
    * ``P_prior == 0`` (degenerate) -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime


def weekly_pivot_close(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    timestamps: Sequence[datetime],
    weeks_back: int = 1,
) -> list[float | None]:
    """% distance from the pivot of the ``weeks_back``-th prior
    completed ISO week."""
    if not isinstance(weeks_back, int) or isinstance(weeks_back, bool) or weeks_back <= 0:
        raise ValueError(f"weeks_back must be a positive int; got {weeks_back!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(timestamps):
        raise ValueError(
            f"highs, lows, closes, timestamps must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(timestamps)}."
        )
    if n == 0:
        return []

    # Group bar indices by ISO (year, week).
    week_buckets: dict[tuple[int, int], list[int]] = {}
    week_keys: list[tuple[int, int]] = []
    for i, ts in enumerate(timestamps):
        iso_year, iso_week, _ = ts.isocalendar()
        key = (iso_year, iso_week)
        if key not in week_buckets:
            week_buckets[key] = []
            week_keys.append(key)
        week_buckets[key].append(i)

    # Per-week pivot.
    week_pivot: dict[tuple[int, int], float] = {}
    for key, indices in week_buckets.items():
        wh = max(highs[k] for k in indices)
        wl = min(lows[k] for k in indices)
        wc = closes[indices[-1]]  # last close of the week
        week_pivot[key] = (wh + wl + wc) / 3.0

    # Per-bar lookup of the right prior pivot.
    out: list[float | None] = [None] * n
    for bar_idx in range(n):
        bar_key = (timestamps[bar_idx].isocalendar().year,
                   timestamps[bar_idx].isocalendar().week)
        bar_key_pos = week_keys.index(bar_key)
        target_pos = bar_key_pos - weeks_back
        if target_pos < 0:
            continue
        prior_pivot = week_pivot[week_keys[target_pos]]
        if prior_pivot == 0:
            continue
        out[bar_idx] = (closes[bar_idx] - prior_pivot) / prior_pivot * 100.0
    return out


__all__ = ["weekly_pivot_close"]
