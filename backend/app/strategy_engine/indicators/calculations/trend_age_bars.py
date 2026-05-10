"""Trend Age Bars - bars since the last EMA-fast / EMA-slow cross.

Definition::

    bars_since_cross[i] = i - last_cross_index_at_or_before_i

Where a "cross" is any bar where ``sign(ema_fast - ema_slow)`` flips
from the previous bar. Returns the bar count as a positive integer.
``None`` for bars before the first cross. The count resets to 0 at
each cross bar and increments by 1 each subsequent bar.

Useful for "trend exhaustion" filters - very old trends carry more
reversion risk.

Output length matches input.
Edge cases:
    * Empty input -> ``[]``.
    * ``ema_fast >= ema_slow`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def trend_age_bars(
    closes: Sequence[float],
    ema_fast: int = 12,
    ema_slow: int = 26,
) -> list[float | None]:
    """Bars since last EMA-fast / EMA-slow cross."""
    if not isinstance(ema_fast, int) or isinstance(ema_fast, bool) or ema_fast < 1:
        raise ValueError(f"ema_fast must be a positive int; got {ema_fast!r}.")
    if not isinstance(ema_slow, int) or isinstance(ema_slow, bool) or ema_slow <= ema_fast:
        raise ValueError(
            f"ema_slow must be int > ema_fast; got fast={ema_fast!r}, slow={ema_slow!r}."
        )
    n = len(closes)
    if n == 0:
        return []

    fast = ema(closes, ema_fast)
    slow = ema(closes, ema_slow)
    if not fast or not slow:
        return [None] * n

    out: list[float | None] = [None] * n
    last_sign: int | None = None
    age: int | None = None
    for i in range(n):
        f = fast[i]
        s = slow[i]
        if f is None or s is None:
            continue
        cur_sign = 1 if f >= s else -1
        if last_sign is None:
            last_sign = cur_sign
            continue
        if cur_sign != last_sign:
            age = 0
            last_sign = cur_sign
        elif age is not None:
            age += 1
        if age is not None:
            out[i] = float(age)
    return out


__all__ = ["trend_age_bars"]
