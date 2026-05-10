"""Price Momentum Index (PMI) - linear-weighted-MA based momentum.

Distinct from ``momentum_oscillator`` (raw price diff) and
``momentum_quality_score`` (Pack 17 composite). Uses the linear-
weighted moving average (LWMA) as the centre line so recent bars
dominate the average:

    weights[j]  = (period - j)        for j = 0..period-1
    lwma[i]     = sum(close[i - j] * weights[j]) / sum(weights)
    PMI[i]      = (close[i] - lwma[i]) / lwma[i] * 100

Output is unbounded percent. Sign = direction; magnitude = stretch
from the LWMA. Output length matches input. Positions ``0 .. period - 1``
are ``None``. ``None`` for bars where lwma == 0.

Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def price_momentum_index(
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """LWMA-stretch percent."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be int >= 2; got {period!r}.")
    n = len(closes)
    if n == 0 or period > n:
        return []
    weight_sum = period * (period + 1) / 2.0
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        weighted = 0.0
        for j in range(period):
            weighted += closes[i - j] * (period - j)
        lwma = weighted / weight_sum
        if lwma == 0:
            continue
        out[i] = (closes[i] - lwma) / lwma * 100.0
    return out


__all__ = ["price_momentum_index"]
