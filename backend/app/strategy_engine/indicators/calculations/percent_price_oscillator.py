"""Percentage Price Oscillator (PPO) — MACD's % cousin.

Definition::

    PPO[i] = (EMA(close, fast)[i] - EMA(close, slow)[i])
              / EMA(close, slow)[i] * 100

Defaults ``fast = 12``, ``slow = 26``. The signal/histogram lines
that Pine's ``ta.ppo`` returns alongside the main line are not
emitted here — strategies that need them can pair this with
distinct EMA configs. Pine equivalent ``ta.ppo(fast, slow, signal)``
returns the main line; the signal and histogram are derived
externally in TradingView's stock template.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``fast >= slow`` -> ``ValueError``.
    * ``slow > n`` -> ``[]``.
    * EMA(close, slow)[i] == 0 -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def percent_price_oscillator(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> list[float | None]:
    """PPO main line over fast/slow EMAs."""
    if not isinstance(fast, int) or isinstance(fast, bool) or fast <= 0:
        raise ValueError(f"fast must be a positive int; got {fast!r}.")
    if not isinstance(slow, int) or isinstance(slow, bool) or slow <= 0:
        raise ValueError(f"slow must be a positive int; got {slow!r}.")
    if not isinstance(signal, int) or isinstance(signal, bool) or signal <= 0:
        raise ValueError(f"signal must be a positive int; got {signal!r}.")
    if fast >= slow:
        raise ValueError(
            f"fast must be strictly less than slow; got fast={fast}, slow={slow}."
        )
    n = len(closes)
    if n == 0 or slow > n:
        return []

    fast_ema = ema(list(closes), fast)
    slow_ema = ema(list(closes), slow)
    if not fast_ema or not slow_ema:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        f = fast_ema[i]
        s = slow_ema[i]
        if f is None or s is None or s == 0:
            continue
        out[i] = (f - s) / s * 100.0
    return out


__all__ = ["percent_price_oscillator"]
