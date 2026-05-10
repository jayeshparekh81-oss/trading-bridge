"""Expiry-day volatility surge proxy.

Per intraday bar, compares today's session range so far against
the typical session range on the same weekday over the prior N
sessions. The "expiry day" = the configured ``weekday_target``
(default Thursday for Indian weekly options).

Output: ratio of today's running session range to the historical
average session range on this weekday. > 1.0 = elevated; < 1.0
= subdued. ``None`` for non-target-weekday bars and when
history is insufficient.

Default ``weekday_target = 3`` (Thursday: Mon=0..Sun=6).

Honest scope notes:

    * Single-symbol proxy. Real expiry-day vol surge involves
      options-OI dynamics that aren't visible at the price-data
      layer.
    * "Session range so far" is the high - low of bars seen on
      the current trading day up to and including this bar (ratchet).
    * Historical average uses the last 4 occurrences of
      ``weekday_target`` (i.e. ~4 weeks back) by default.

Frequency-aware: returns all-``None`` for daily-or-larger
candles (concept needs intraday timestamps).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Daily frequency -> all-``None``.
    * Insufficient history (< 2 prior weekday_target sessions
      with data) -> ``None``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta


def expiry_day_volatility(
    highs: Sequence[float],
    lows: Sequence[float],
    timestamps: Sequence[datetime],
    weekday_target: int = 3,
    history_sessions: int = 4,
) -> list[float | None]:
    """Per-intraday-bar expiry-day vol surge ratio."""
    if not isinstance(weekday_target, int) or isinstance(weekday_target, bool):
        raise ValueError(
            f"weekday_target must be an int 0..6; got {weekday_target!r}."
        )
    if not 0 <= weekday_target <= 6:
        raise ValueError(
            f"weekday_target must be in [0, 6]; got {weekday_target}."
        )
    if not isinstance(history_sessions, int) or isinstance(history_sessions, bool) or history_sessions < 2:
        raise ValueError(
            f"history_sessions must be an int >= 2; got {history_sessions!r}."
        )
    n = len(highs)
    if n != len(lows) or n != len(timestamps):
        raise ValueError(
            f"highs, lows, timestamps must have the same length; "
            f"got {n}, {len(lows)}, {len(timestamps)}."
        )
    if n == 0:
        return []
    if n < 2 or timestamps[1] - timestamps[0] >= timedelta(hours=24):
        return [None] * n

    # Group bar indices by trading date.
    by_date: dict[date, list[int]] = {}
    date_keys: list[date] = []
    for i, ts in enumerate(timestamps):
        d = ts.date()
        if d not in by_date:
            by_date[d] = []
            date_keys.append(d)
        by_date[d].append(i)

    # Daily total session range (high - low across all bars in
    # the day).
    daily_range: dict[date, float] = {}
    for d, idxs in by_date.items():
        daily_range[d] = max(highs[k] for k in idxs) - min(lows[k] for k in idxs)

    out: list[float | None] = [None] * n
    for bar_idx in range(n):
        ts = timestamps[bar_idx]
        if ts.weekday() != weekday_target:
            continue
        d = ts.date()
        # Today's session range so far (running max - min over the
        # bars seen on this date up to + including this bar).
        today_idxs = [k for k in by_date[d] if k <= bar_idx]
        if not today_idxs:
            continue
        today_running_high = max(highs[k] for k in today_idxs)
        today_running_low = min(lows[k] for k in today_idxs)
        today_running_range = today_running_high - today_running_low
        # Find the prior ``history_sessions`` occurrences of
        # ``weekday_target`` in the input.
        prior_target_dates = [
            pd for pd in date_keys
            if pd < d and pd.weekday() == weekday_target
        ]
        if len(prior_target_dates) < 2:
            continue
        recent = prior_target_dates[-history_sessions:]
        avg_prior_range = sum(daily_range[pd] for pd in recent) / len(recent)
        if avg_prior_range == 0:
            continue
        out[bar_idx] = today_running_range / avg_prior_range
    return out


__all__ = ["expiry_day_volatility"]
