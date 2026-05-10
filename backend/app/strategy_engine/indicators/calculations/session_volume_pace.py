"""Session volume pace — today's cumulative volume vs typical pace.

For each intraday bar, computes the ratio of today's cumulative
volume up to and including this bar to the *typical* cumulative
volume at the same time-of-day, averaged over the prior
``lookback_days`` trading sessions.

    > 1.0 -> volume above pace (heavier session than usual)
    < 1.0 -> volume below pace (lighter session than usual)
    = 1.0 -> on pace

Useful as a session-strength filter: heavy-volume sessions often
trend; light sessions chop.

Default ``lookback_days = 20``.

Honest scope notes:

* The "typical pace" is built from observed time-of-day buckets
  (rounded to the bar's hour:minute). Sparse data (gaps, missed
  bars) can skew the average; we average only over days where
  the same bar-of-day actually has data.
* Returns ``None`` for any bar whose time-of-day hasn't been
  observed enough times in the prior ``lookback_days`` (need
  at least 2 prior observations to form an average).

Frequency-aware: returns all-``None`` for daily-or-larger candles.

Output length equals input length.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Daily frequency -> all-``None``.
    * Insufficient prior days at this time-of-day -> ``None``.
    * Typical-pace == 0 -> ``None`` (degenerate).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta


def session_volume_pace(
    volumes: Sequence[float],
    timestamps: Sequence[datetime],
    lookback_days: int = 20,
) -> list[float | None]:
    """Per-intraday-bar session-volume pace ratio."""
    if not isinstance(lookback_days, int) or isinstance(lookback_days, bool) or lookback_days < 2:
        raise ValueError(
            f"lookback_days must be an int >= 2; got {lookback_days!r}."
        )
    n = len(volumes)
    if n != len(timestamps):
        raise ValueError(
            f"volumes and timestamps must have the same length; "
            f"got {n}, {len(timestamps)}."
        )
    if n == 0:
        return []
    if n < 2 or timestamps[1] - timestamps[0] >= timedelta(hours=24):
        return [None] * n

    # Pre-pass: compute today's cumulative volume up to each bar
    # AND a per-(date, time-of-day) lookup of cumulative volume
    # at that time-of-day on each historic day.
    cum_volume: list[float] = [0.0] * n
    current_date = None
    running = 0.0
    for i, ts in enumerate(timestamps):
        if ts.date() != current_date:
            current_date = ts.date()
            running = 0.0
        running += volumes[i]
        cum_volume[i] = running

    # Per-day, per-time-of-day cumulative volume.
    by_day: dict[date, dict[tuple[int, int], float]] = {}
    for i, ts in enumerate(timestamps):
        d = ts.date()
        key = (ts.hour, ts.minute)
        if d not in by_day:
            by_day[d] = {}
        by_day[d][key] = cum_volume[i]

    # Sorted unique trading dates.
    dates_sorted = sorted(by_day.keys())
    date_pos: dict[date, int] = {d: idx for idx, d in enumerate(dates_sorted)}

    out: list[float | None] = [None] * n
    for i, ts in enumerate(timestamps):
        d = ts.date()
        key = (ts.hour, ts.minute)
        my_idx = date_pos[d]
        prior_dates = dates_sorted[max(0, my_idx - lookback_days) : my_idx]
        prior_values = [
            by_day[pd][key] for pd in prior_dates if key in by_day[pd]
        ]
        if len(prior_values) < 2:
            continue
        typical = sum(prior_values) / len(prior_values)
        if typical == 0:
            continue
        out[i] = cum_volume[i] / typical
    return out


__all__ = ["session_volume_pace"]
