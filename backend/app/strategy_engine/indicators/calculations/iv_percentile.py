"""IV Percentile — % of historical IV-proxy readings <= current.

⚠️  Uses ``iv_proxy_atr`` as the underlying volatility series
(NOT real IV — see :mod:`iv_proxy_atr`).

Different from :mod:`iv_rank`:

    * IV Rank uses ``(current - min) / (max - min) * 100`` —
      sensitive to outliers in the trailing range.
    * IV Percentile counts the % of historical readings <=
      current — robust to outliers; tells you how often vol
      has been THIS LOW or lower.

Both are popular among options traders; they answer slightly
different questions. Ship both.

Definition::

    iv_pct[i] = count(v <= current for v in trailing window) / window_size * 100

Default ``lookback = 252``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``lookback >= n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.iv_proxy_atr import iv_proxy_atr


def iv_percentile(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    lookback: int = 252,
    atr_period: int = 20,
) -> list[float | None]:
    """IV Percentile in ``[0, 100]``."""
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
        leq_count = sum(1 for v in window if v <= cur)
        out[i] = leq_count / len(window) * 100.0
    return out


__all__ = ["iv_percentile"]
