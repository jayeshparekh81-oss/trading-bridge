"""Chaikin Oscillator (Marc Chaikin, 1970s).

Definition::

    AD     = accumulation_distribution(H, L, C, V)
    CO     = EMA(AD, fast) - EMA(AD, slow)

Default fast/slow = 3/10. Values above zero suggest accumulation;
below zero suggest distribution. Crossings of zero are classic
divergence signals.

Output length equals input length. ``None`` for the warm-up
bars (the slow-EMA seed lands at index ``slow - 1``).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``slow >= len(closes)`` -> ``[]``.
    * ``fast >= slow`` -> ``ValueError`` (would produce a positive
      lag bias instead of a momentum signal).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.accumulation_distribution import (
    accumulation_distribution,
)
from app.strategy_engine.indicators.calculations.ema import ema


def chaikin_oscillator(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    fast: int = 3,
    slow: int = 10,
) -> list[float | None]:
    """Chaikin Oscillator over an A/D line."""
    _check_period(fast, "fast")
    _check_period(slow, "slow")
    if fast >= slow:
        raise ValueError(
            f"fast must be strictly less than slow; got fast={fast}, slow={slow}."
        )
    n = len(closes)
    if n == 0 or slow >= n:
        return []

    ad = accumulation_distribution(highs, lows, closes, volumes)
    # ``accumulation_distribution`` returns floats end-to-end (no
    # warm-up), so we can feed straight into the EMA helper.
    ad_floats = [v if v is not None else 0.0 for v in ad]
    fast_ema = ema(ad_floats, fast)
    slow_ema = ema(ad_floats, slow)
    if not fast_ema or not slow_ema:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        f = fast_ema[i]
        s = slow_ema[i]
        if f is None or s is None:
            continue
        out[i] = f - s
    return out


def _check_period(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive int; got {value!r}.")


__all__ = ["chaikin_oscillator"]
