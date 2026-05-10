"""Weekly Trend Strength - bar-based weekly direction persistence score.

Bar-based proxy for "weekly trend": treats every 5 consecutive
bars as one "week" (works for daily candles; intraday users
should resample upstream). Output is the percentage of those
weeks that closed in the SAME direction as the most recent
week, in ``[0, 100]``.

Definition::

    bars_per_week = 5
    For the trailing `weeks` weekly-blocks ending at bar i:
        week_change[k] = close[end_k] - close[start_k]
    last_dir = sign(week_change[-1])
    score    = (count of week_change with sign == last_dir) / weeks * 100

Output length matches input. ``None`` until ``weeks * 5 - 1``.

Edge cases:
    * Empty input -> ``[]``.
    * ``weeks < 2`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

_BARS_PER_WEEK = 5


def weekly_trend_strength(
    closes: Sequence[float],
    weeks: int = 4,
) -> list[float | None]:
    """0..100 directional persistence score across last ``weeks`` weekly-blocks."""
    if not isinstance(weeks, int) or isinstance(weeks, bool) or weeks < 2:
        raise ValueError(f"weeks must be int >= 2; got {weeks!r}.")
    n = len(closes)
    needed = weeks * _BARS_PER_WEEK
    if n == 0 or needed > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(needed - 1, n):
        week_changes: list[float] = []
        for k in range(weeks):
            end_idx = i - k * _BARS_PER_WEEK
            start_idx = end_idx - _BARS_PER_WEEK + 1
            if start_idx < 0:
                continue
            week_changes.append(closes[end_idx] - closes[start_idx])
        if len(week_changes) != weeks:
            continue
        last_dir = 1 if week_changes[0] >= 0 else -1
        same = sum(1 for wc in week_changes if (wc >= 0) == (last_dir == 1))
        out[i] = same / weeks * 100.0
    return out


__all__ = ["weekly_trend_strength"]
