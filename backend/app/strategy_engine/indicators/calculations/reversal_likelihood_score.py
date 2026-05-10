"""Reversal Likelihood Score - 0..100 multi-factor reversal signal.

Synthesises three components into a 0..100 score::

    rsi_part       = clamp((|rsi - 50| - 20) / 30, 0, 1)   * 40
    divergence_part = (|rsi_divergence value| in {0, 1})    * 30
    range_part     = clamp((|close - prev_close|) /
                           atr, 0, 2) / 2                   * 30
    score          = rsi_part + divergence_part + range_part

Distinct from Pack 13's ``divergence_strength_score`` (which is
the *sum of three divergence types*). Reversal-likelihood adds
RSI extremity + range-shock context to ONE divergence-detector
output - a different mechanism aimed at "is this turn worth
trading" rather than "how many divergence types agree".

Output 0..100. Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr
from app.strategy_engine.indicators.calculations.rsi import rsi
from app.strategy_engine.indicators.calculations.rsi_divergence import (
    rsi_divergence,
)


def reversal_likelihood_score(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Composite 0..100 reversal-likelihood score."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(closes)
    if n != len(highs) or n != len(lows):
        raise ValueError(
            f"highs/lows/closes must have the same length; "
            f"got {len(highs)}, {len(lows)}, {n}."
        )
    if n == 0:
        return []

    rsi_line = rsi(closes, period)
    div_line = rsi_divergence(list(closes), rsi_period=period, lookback=20)
    atr_line = atr(highs, lows, closes, period)
    if not rsi_line or not div_line or not atr_line:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        r = rsi_line[i]
        d = div_line[i]
        t = atr_line[i]
        if r is None or t is None or t == 0 or i == 0:
            continue
        rsi_part = _clamp((abs(r - 50.0) - 20.0) / 30.0, 0.0, 1.0) * 40.0
        div_part = (1.0 if d is not None and abs(d) >= 1 else 0.0) * 30.0
        bar_move = abs(closes[i] - closes[i - 1])
        range_part = _clamp(bar_move / t, 0.0, 2.0) / 2.0 * 30.0
        out[i] = rsi_part + div_part + range_part
    return out


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


__all__ = ["reversal_likelihood_score"]
