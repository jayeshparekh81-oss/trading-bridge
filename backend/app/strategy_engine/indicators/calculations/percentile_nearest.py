"""Percentile (Nearest Rank) — value at percentage P in a rolling window.

Matches Pine ``ta.percentile_nearest_rank(source, length, percentage)``:
returns the value at the requested percentile using the
nearest-rank method (no interpolation).

    sorted_window = sorted(values[i - period + 1..i])
    rank          = ceil(percentage / 100 * period)
    out[i]        = sorted_window[rank - 1]   (1-indexed -> 0-indexed)

Pine clamps ``rank`` to ``[1, period]`` for safety; we mirror that.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
    * ``percentage`` outside ``[0, 100]`` -> ``ValueError``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def percentile_nearest(
    values: Sequence[float],
    period: int = 100,
    percentage: float = 50.0,
) -> list[float | None]:
    """Nearest-rank percentile over a trailing ``period`` window."""
    _check_period(period)
    if not (0.0 <= percentage <= 100.0):
        raise ValueError(
            f"percentage must be in [0, 100]; got {percentage!r}."
        )
    n = len(values)
    if n == 0 or period > n:
        return []

    rank_idx = max(1, min(period, math.ceil(percentage / 100.0 * period)))
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = sorted(values[i - period + 1 : i + 1])
        out[i] = window[rank_idx - 1]
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["percentile_nearest"]
