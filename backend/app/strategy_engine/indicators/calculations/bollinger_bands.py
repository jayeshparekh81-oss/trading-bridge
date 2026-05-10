"""Bollinger Bands — SMA middle line + k * stdev bands.

Definition:
    middle[i] = SMA(values, period)[i]
    sigma[i]  = population stdev of values[i - period + 1 .. i]
    upper[i]  = middle[i] + std_dev * sigma[i]
    lower[i]  = middle[i] - std_dev * sigma[i]

We use the **population** standard deviation (divisor ``period``) to
match TradingView's ``ta.stdev`` / ``ta.bb`` convention, NOT the sample
stdev (divisor ``period - 1``). This is the de facto standard in
charting libraries.

Edge cases per Phase 1 contract:
    * ``len(values) == 0`` -> three empty lists.
    * ``period > len(values)`` -> three empty lists.
    * Otherwise: warm-up positions are ``None``; outputs align with input.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.sma import sma


def bollinger_bands(
    values: Sequence[float], period: int = 20, std_dev: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Upper, middle (SMA), and lower Bollinger Bands. Returns three lists."""
    _check_period(period)
    if not isinstance(std_dev, (int, float)) or isinstance(std_dev, bool) or std_dev <= 0:
        raise ValueError(f"std_dev must be a positive number; got {std_dev!r}.")

    n = len(values)
    if n == 0 or period > n:
        return [], [], []

    middle = sma(values, period)
    upper: list[float | None] = []
    lower: list[float | None] = []

    for i, mid in enumerate(middle):
        if mid is None:
            upper.append(None)
            lower.append(None)
            continue
        window = values[i - period + 1 : i + 1]
        mean = mid
        variance = sum((v - mean) ** 2 for v in window) / period
        sigma = math.sqrt(variance)
        upper.append(mid + std_dev * sigma)
        lower.append(mid - std_dev * sigma)

    return upper, middle, lower


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["bollinger_bands"]
