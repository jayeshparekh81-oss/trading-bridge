"""Momentum Quality Score - 0..100 composite of momentum strength.

Synthesises three Pack 2-16 primitives::

    rsi_part   = clamp(|rsi - 50| / 50, 0, 1)              * 40
    macd_part  = clamp(|macd_hist| / (close * 0.005),
                       0, 1)                               * 30
    roc_part   = (count of last `period` ROC values whose
                  sign matches the current ROC sign / period) * 30
    score      = rsi_part + macd_part + roc_part

Score 0..100. Useful as a regime tag for momentum strategies.

Output length matches input.
Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.macd import macd
from app.strategy_engine.indicators.calculations.roc import roc
from app.strategy_engine.indicators.calculations.rsi import rsi


def momentum_quality_score(
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Composite 0..100 momentum-quality score over ``period`` bars."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(closes)
    if n == 0:
        return []

    rsi_line = rsi(closes, period)
    _macd_line, _signal_line, hist_line = macd(closes)
    roc_line = roc(closes, period)
    if not rsi_line or not hist_line or not roc_line:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        r = rsi_line[i]
        h = hist_line[i]
        cur_roc = roc_line[i]
        if r is None or h is None or cur_roc is None:
            continue
        if i < period:
            continue
        rsi_part = _clamp(abs(r - 50.0) / 50.0, 0.0, 1.0) * 40.0
        denom = max(abs(closes[i]) * 0.005, 1e-9)
        macd_part = _clamp(abs(h) / denom, 0.0, 1.0) * 30.0
        sign_now = 1 if cur_roc >= 0 else -1
        same = 0
        seen = 0
        for j in range(i - period + 1, i + 1):
            rj = roc_line[j]
            if rj is None:
                continue
            seen += 1
            if (rj >= 0) == (sign_now == 1):
                same += 1
        roc_part = (same / seen if seen else 0.0) * 30.0
        out[i] = rsi_part + macd_part + roc_part
    return out


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


__all__ = ["momentum_quality_score"]
