"""Percentile Rank — current value's percentile within a rolling window.

Matches Pine ``ta.percentrank(source, length)``: returns the percent
of bars in the lookback window whose value is ``<= values[i]``.
Output range ``[0, 100]``.

    rank[i] = 100 * count(values[j] <= values[i] for j in i-period+1..i)
              / period

The current bar is included in the count (its value is always
``<= itself``), so a perfectly flat series yields 100.0 every bar.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def percentile_rank(
    values: Sequence[float], period: int = 100
) -> list[float | None]:
    """Percentile rank of each bar within the trailing ``period``."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        cur = values[i]
        count_le = sum(1 for v in window if v <= cur)
        out[i] = 100.0 * count_le / period
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["percentile_rank"]
