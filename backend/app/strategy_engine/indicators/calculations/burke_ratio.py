"""Burke Ratio — return / sqrt(sum of squared drawdowns).

A risk-adjusted return measure that penalises drawdowns
quadratically (small drawdowns barely matter; big ones dominate).
Sortino-family cousin — Sortino uses downside-return stddev;
Burke uses drawdown magnitude directly.

Definition::

    period_return[i] = (close[i] - close[i - period]) / close[i - period] * 100
    drawdowns[i]     = drops from running peak inside the window
    Burke[i]         = period_return[i] / sqrt(sum(drawdowns^2))

Default ``period = 14``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n`` -> ``[]``.
    * Window with zero drawdowns (monotone uptrend) -> ``+inf``
      if return is positive (caller branches on the sentinel).
    * ``close[i - period] == 0`` -> ``None`` for that bar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def burke_ratio(
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Burke Ratio over a rolling ``period`` window."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period, n):
        prev = closes[i - period]
        if prev == 0:
            continue
        ret = (closes[i] - prev) / prev * 100.0
        # Per-bar drawdown vs running peak inside the window.
        peak = closes[i - period]
        sq_sum = 0.0
        for k in range(i - period + 1, i + 1):
            peak = max(peak, closes[k])
            if peak == 0:
                continue
            dd = (closes[k] - peak) / peak * 100.0
            sq_sum += dd * dd
        if sq_sum == 0:
            if ret > 0:
                out[i] = math.inf
            elif ret < 0:
                out[i] = -math.inf
            else:
                out[i] = 0.0
        else:
            out[i] = ret / math.sqrt(sq_sum)
    return out


__all__ = ["burke_ratio"]
