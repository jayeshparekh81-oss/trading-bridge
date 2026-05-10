"""Divergence Strength Score — composite of Pack-11 divergences.

Sums the per-bar codes from RSI / MACD / OBV divergence into a
single severity score in ``[-3, +3]``:

    DSS[i] = rsi_divergence[i] + macd_divergence[i] + obv_divergence[i]

Each component emits +1 (bullish), -1 (bearish), or 0. A score
of +3 = all three flagging bullish (highest-conviction reversal
candidate); -3 = all three flagging bearish.

Default ``period = 14`` (passed to RSI internal); other periods
use the divergence-detector defaults (lookback=20).

Output length equals input length. ``None`` if any of the three
components is unavailable at that bar.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Insufficient bars for the slowest component -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.macd_divergence import (
    macd_divergence,
)
from app.strategy_engine.indicators.calculations.obv_divergence import (
    obv_divergence,
)
from app.strategy_engine.indicators.calculations.rsi_divergence import (
    rsi_divergence,
)


def divergence_strength_score(
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Composite divergence severity in ``[-3, +3]``."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    if n == 0:
        return []

    rsi_d = rsi_divergence(list(closes), rsi_period=period, lookback=20)
    macd_d = macd_divergence(list(closes), fast=12, slow=26, signal=9, lookback=20)
    obv_d = obv_divergence(list(closes), list(volumes), lookback=20)
    if not rsi_d or not macd_d or not obv_d:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        r = rsi_d[i]
        m = macd_d[i]
        o = obv_d[i]
        if r is None or m is None or o is None:
            continue
        out[i] = r + m + o
    return out


__all__ = ["divergence_strength_score"]
