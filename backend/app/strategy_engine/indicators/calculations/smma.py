"""Smoothed Moving Average — Wilder's RMA.

Definition (matches Pine ``ta.rma`` / ``ta.smma``):

    SMMA[period - 1] = mean(values[0..period - 1])
    SMMA[i]          = (SMMA[i - 1] * (period - 1) + values[i]) / period   (i >= period)

    Equivalent to an EMA with ``alpha = 1 / period``. Wilder used it
    for RSI / ATR / ADX seeding; many TradingView scripts call it
    explicitly via ``ta.rma``.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def smma(values: Sequence[float], period: int = 20) -> list[float | None]:
    """Wilder-smoothed moving average."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    seed_sum = sum(values[i] for i in range(period))
    prev = seed_sum / period
    out[period - 1] = prev
    for i in range(period, n):
        prev = (prev * (period - 1) + values[i]) / period
        out[i] = prev
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["smma"]
