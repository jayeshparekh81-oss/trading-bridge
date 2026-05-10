"""Coppock Curve (Edwin Coppock, 1962).

Long-term momentum oscillator originally designed for monthly
equity-index data — flags major buy/sell regimes when crossing
zero.

Definition::

    short_roc[i] = (close[i] - close[i - short_period]) / close[i - short_period] * 100
    long_roc[i]  = (close[i] - close[i - long_period])  / close[i - long_period]  * 100
    sum_roc[i]   = short_roc[i] + long_roc[i]
    Coppock      = WMA(sum_roc, wma_period)

Defaults: ``short_period = 11``, ``long_period = 14``,
``wma_period = 10`` (Coppock's originals).

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * Insufficient bars -> ``[]``.
    * ``close[i - n] == 0`` -> contribution that bar is 0.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.wma import wma


def coppock_curve(
    closes: Sequence[float],
    short_period: int = 11,
    long_period: int = 14,
    wma_period: int = 10,
) -> list[float | None]:
    """Coppock long-term momentum curve."""
    _check_period(short_period, "short_period")
    _check_period(long_period, "long_period")
    _check_period(wma_period, "wma_period")
    n = len(closes)
    minimum = max(short_period, long_period) + wma_period
    if n == 0 or n < minimum:
        return []

    sum_roc: list[float] = [0.0] * n
    for i in range(n):
        if i - short_period < 0 or i - long_period < 0:
            continue
        short_prev = closes[i - short_period]
        long_prev = closes[i - long_period]
        s = (
            0.0
            if short_prev == 0
            else (closes[i] - short_prev) / short_prev * 100.0
        )
        long_pct = (
            0.0
            if long_prev == 0
            else (closes[i] - long_prev) / long_prev * 100.0
        )
        sum_roc[i] = s + long_pct

    smoothed = wma(sum_roc, wma_period)
    if not smoothed:
        return [None] * n

    # Mask the warm-up region — WMA itself is full-length but the
    # underlying ROCs are zero for the first ``max(short, long)``
    # bars, so the smoothed values there are meaningless.
    out: list[float | None] = list(smoothed)
    cutoff = max(short_period, long_period) + wma_period - 1
    for i in range(min(cutoff, n)):
        out[i] = None
    return out


def _check_period(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive int; got {value!r}.")


__all__ = ["coppock_curve"]
