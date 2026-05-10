"""IV Rank — current vol-proxy as % of trailing range.

⚠️  Uses ``iv_proxy_atr`` as the underlying volatility series
(NOT real IV — see :mod:`iv_proxy_atr`). The "rank" computation
is the standard Tastyworks-style formula:

    IV Rank[i] = (current - min) / (max - min) * 100

over the trailing ``lookback`` bars. Output is in ``[0, 100]``.

    100 -> current vol-proxy is at the highest in the lookback window
      0 -> at the lowest
     50 -> midway between range extremes

Distinct from :mod:`iv_percentile` (which counts the % of
historical readings BELOW current — different ranking method).

Default ``lookback = 252`` (one trading year).

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``lookback >= n`` -> ``[]``.
    * Flat window (max == min) -> ``50.0`` (midpoint by convention).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.iv_proxy_atr import iv_proxy_atr


def iv_rank(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    lookback: int = 252,
    atr_period: int = 20,
) -> list[float | None]:
    """IV Rank in ``[0, 100]`` from the iv_proxy_atr series."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 2:
        raise ValueError(f"lookback must be an int >= 2; got {lookback!r}.")
    if not isinstance(atr_period, int) or isinstance(atr_period, bool) or atr_period <= 0:
        raise ValueError(f"atr_period must be a positive int; got {atr_period!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or lookback >= n:
        return []

    iv = iv_proxy_atr(highs, lows, closes, atr_period)
    if not iv:
        return [None] * n
    out: list[float | None] = [None] * n
    for i in range(lookback, n):
        cur = iv[i]
        if cur is None:
            continue
        window = [v for v in iv[i - lookback : i + 1] if v is not None]
        if len(window) < 2:
            continue
        lo = min(window)
        hi = max(window)
        rng = hi - lo
        out[i] = 50.0 if rng == 0 else (cur - lo) / rng * 100.0
    return out


__all__ = ["iv_rank"]
