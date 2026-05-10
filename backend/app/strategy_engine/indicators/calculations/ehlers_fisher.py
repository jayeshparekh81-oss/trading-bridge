"""Ehlers Inverse Fisher Transform of RSI.

Distinct from the standard Pack-7 :mod:`fisher_transform` (which
applies the Fisher transform to *price* directly). This module
applies the *inverse* Fisher transform to RSI:

    x[i]   = 0.1 * (RSI[i] - 50)
    IFT[i] = (exp(2 * x[i]) - 1) / (exp(2 * x[i]) + 1)

Output range is ``[-1, +1]``. Sharp peaks / troughs (near +1 /
-1) line up with overbought / oversold conditions more
aggressively than raw RSI — useful for fast-mean-reversion
entries.

Default ``period = 10``.

Output length equals input length. ``None`` for the RSI warm-up
(first ``period`` bars).

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n`` -> ``[]``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.rsi import rsi


def ehlers_fisher(
    closes: Sequence[float],
    period: int = 10,
) -> list[float | None]:
    """Inverse Fisher Transform of RSI."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 1:
        raise ValueError(f"period must be an int > 1; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n:
        return []

    rsi_series = rsi(list(closes), period)
    if not rsi_series:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        r = rsi_series[i]
        if r is None:
            continue
        x = 0.1 * (r - 50.0)
        # exp(2x) can overflow for large |x| (RSI extremes); clamp x
        # to keep math.exp finite. ~25 ≫ any reasonable RSI delta.
        if x > 25:
            out[i] = 1.0
        elif x < -25:
            out[i] = -1.0
        else:
            e2x = math.exp(2.0 * x)
            out[i] = (e2x - 1.0) / (e2x + 1.0)
    return out


__all__ = ["ehlers_fisher"]
