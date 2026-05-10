"""Mean-reversion half-life via Ornstein-Uhlenbeck regression.

For each bar, fits the OU model ``delta_y[t] = a + b * y[t-1] +
epsilon`` on the trailing window. If the slope ``b`` is
negative, the series mean-reverts and the *half-life* (bars to
revert half the distance to the mean) is::

    half_life = -ln(2) / b

Returns:

    finite positive value -> mean-reverting (faster reversion =
                              smaller half-life)
    None                   -> not mean-reverting (b >= 0 → series
                              is trending or random-walk-like)

Useful as a regime filter for pairs / mean-reversion strategies.

Default ``period = 60`` (need a reasonable sample for the OU
regression).

Output length equals input length. ``None`` for the warm-up
plus any bar where the series isn't mean-reverting.

Edge cases:
    * Empty input -> ``[]``.
    * ``period < 10`` rejected (too small for stable OU fit).
    * ``period >= n`` -> ``[]``.
    * Constant window -> ``None`` (no variance to fit).
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def half_life_mean_reversion(
    closes: Sequence[float], period: int = 60,
) -> list[float | None]:
    """Per-bar OU half-life estimate (bars to revert half-way)."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 10:
        raise ValueError(f"period must be an int >= 10; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period, n):
        # Build (y[t-1], delta_y[t]) pairs from the trailing window.
        ys = closes[i - period : i]
        delta_ys = [closes[k + 1] - closes[k] for k in range(i - period, i)]
        # OLS regression: delta_y = a + b * y_prev.
        n_pts = len(ys)
        mean_y = sum(ys) / n_pts
        mean_dy = sum(delta_ys) / n_pts
        sxx = sum((y - mean_y) ** 2 for y in ys)
        if sxx == 0:
            continue
        sxy = sum(
            (ys[k] - mean_y) * (delta_ys[k] - mean_dy)
            for k in range(n_pts)
        )
        b = sxy / sxx
        if b >= 0:
            # Trending or random walk - no mean-reversion.
            continue
        out[i] = -math.log(2.0) / b
    return out


__all__ = ["half_life_mean_reversion"]
