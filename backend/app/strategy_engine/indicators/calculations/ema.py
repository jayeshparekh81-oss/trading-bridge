"""Exponential Moving Average — TradingView-compatible (SMA-seeded).

Definition (matches ``ta.ema`` in Pine v5/v6):
    * ``alpha = 2 / (period + 1)``.
    * Seed at index ``period - 1``: ``EMA[period - 1] = SMA(values[0..period - 1])``.
    * Recursion for ``i >= period``: ``EMA[i] = alpha * values[i] + (1 - alpha) * EMA[i - 1]``.
    * Positions ``0 .. period - 2`` are ``None``.

Edge cases per Phase 1 contract:
    * ``len(values) == 0`` -> ``[]``
    * ``period > len(values)`` -> ``[]``
"""

from __future__ import annotations

from collections.abc import Sequence


def ema(values: Sequence[float], period: int) -> list[float | None]:
    """Exponential moving average. SMA-seeded for TradingView parity."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    alpha = 2.0 / (period + 1)
    out: list[float | None] = [None] * (period - 1)
    seed = float(sum(values[:period])) / period
    out.append(seed)
    prev = seed
    for i in range(period, n):
        current = alpha * values[i] + (1 - alpha) * prev
        out.append(current)
        prev = current
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["ema"]
