"""Distance from prior month's classic pivot, in % of pivot.

Substitute for the spec's ``weekly_pivot_distance``, which would
have computed the same numbers as Pack 8's already-active
``weekly_pivot_close`` (both are ``(close - weekly_pivot) /
weekly_pivot * 100``). Same Pack 10 lesson — duplicate calc
under a different name is LOC without signal.

This indicator extends the timeframe to the calendar MONTH —
the natural sibling of weekly pivot distance, useful for swing
strategies. Same calc structure, distinct period.

Definition::

    pivot_M[d] = (high_prior_month + low_prior_month + close_prior_month) / 3
    out[i]     = (close[i] - pivot_M) / pivot_M * 100

For every bar in calendar month M, uses the pivot of month
``M - months_back`` (default 1).

Frequency-agnostic: works on intraday + daily + weekly bars.
Bars in the very first month of the input have ``None`` (no
prior month available).

Default ``months_back = 1``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Less than ``months_back`` complete prior months in input
      -> all-``None``.
    * Prior-month pivot == 0 (degenerate) -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime


def monthly_pivot_distance(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    timestamps: Sequence[datetime],
    months_back: int = 1,
) -> list[float | None]:
    """% distance from the pivot of ``months_back``-th prior calendar month."""
    if not isinstance(months_back, int) or isinstance(months_back, bool) or months_back <= 0:
        raise ValueError(f"months_back must be a positive int; got {months_back!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(timestamps):
        raise ValueError(
            f"highs, lows, closes, timestamps must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(timestamps)}."
        )
    if n == 0:
        return []

    # Group bar indices by (year, month).
    month_buckets: dict[tuple[int, int], list[int]] = {}
    month_keys: list[tuple[int, int]] = []
    for i, ts in enumerate(timestamps):
        key = (ts.year, ts.month)
        if key not in month_buckets:
            month_buckets[key] = []
            month_keys.append(key)
        month_buckets[key].append(i)

    # Per-month classic pivot.
    month_pivot: dict[tuple[int, int], float] = {}
    for key, indices in month_buckets.items():
        mh = max(highs[k] for k in indices)
        ml = min(lows[k] for k in indices)
        mc = closes[indices[-1]]
        month_pivot[key] = (mh + ml + mc) / 3.0

    out: list[float | None] = [None] * n
    for bar_idx in range(n):
        ts = timestamps[bar_idx]
        bar_key = (ts.year, ts.month)
        bar_pos = month_keys.index(bar_key)
        target_pos = bar_pos - months_back
        if target_pos < 0:
            continue
        prior_pivot = month_pivot[month_keys[target_pos]]
        if prior_pivot == 0:
            continue
        out[bar_idx] = (closes[bar_idx] - prior_pivot) / prior_pivot * 100.0
    return out


__all__ = ["monthly_pivot_distance"]
