"""Mean Reversion Score - 0..100 composite of stretched-from-mean signals.

Synthesises three Pack 2-16 primitives::

    bb_part    = clamp(2 * |bb_percent_b - 0.5|, 0, 1)        * 40
    rsi_part   = clamp(|rsi - 50| / 50, 0, 1)                 * 30
    z_part     = clamp(|close - sma| / (2 * std_dev), 0, 1)   * 30
    score      = bb_part + rsi_part + z_part

Higher score = price is more stretched from its mean and a
mean-reversion entry is more likely to work. Use ``> 70`` as a
rule-of-thumb.

Output length matches input.
Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.bollinger_percent_b import (
    bollinger_percent_b,
)
from app.strategy_engine.indicators.calculations.rsi import rsi
from app.strategy_engine.indicators.calculations.sma import sma
from app.strategy_engine.indicators.calculations.std_dev import std_dev


def mean_reversion_score(
    closes: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Composite 0..100 mean-reversion score over ``period`` bars."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(closes)
    if n == 0:
        return []

    bb_line = bollinger_percent_b(closes, period, 2.0)
    rsi_line = rsi(closes, period)
    sma_line = sma(closes, period)
    sd_line = std_dev(closes, period)
    if not bb_line or not rsi_line or not sma_line or not sd_line:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        b = bb_line[i]
        r = rsi_line[i]
        s = sma_line[i]
        sd = sd_line[i]
        if b is None or r is None or s is None or sd is None or sd == 0:
            continue
        bb_part = _clamp(2.0 * abs(b - 0.5), 0.0, 1.0) * 40.0
        rsi_part = _clamp(abs(r - 50.0) / 50.0, 0.0, 1.0) * 30.0
        z_part = _clamp(abs(closes[i] - s) / (2.0 * sd), 0.0, 1.0) * 30.0
        out[i] = bb_part + rsi_part + z_part
    return out


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


__all__ = ["mean_reversion_score"]
