"""Relative Strength Index — Wilder's original smoothing.

Definition (J. Welles Wilder Jr., "New Concepts in Technical Trading
Systems", 1978; matches Pine ``ta.rsi``):

    1. Compute price changes ``d[i] = values[i] - values[i - 1]`` for
       ``i >= 1``.
    2. Split each into gain (``max(d, 0)``) and loss (``max(-d, 0)``).
    3. Seed at index ``period``: average gain / loss is the simple mean
       of the first ``period`` gains / losses (i.e. ``d[1..period]``).
    4. Wilder smoothing for ``i > period``::

           avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
           avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period

    5. ``RSI[i] = 100 - 100 / (1 + avg_gain / avg_loss)``. When
       ``avg_loss == 0``, RSI is 100. When both are 0, RSI is 50 by
       convention (no movement).

Output length matches input length. Positions ``0 .. period - 1`` are
``None`` (need ``period`` price changes, which require ``period + 1``
prices, but the seed convention emits the first RSI at index ``period``).

Edge cases per Phase 1 contract:
    * ``len(values) == 0`` -> ``[]``
    * ``period >= len(values)`` -> ``[]`` (need ``period`` changes plus
      one prior price; with ``len == period`` we have only ``period - 1``
      changes which is one short).
"""

from __future__ import annotations

from collections.abc import Sequence


def rsi(values: Sequence[float], period: int) -> list[float | None]:
    """Wilder RSI of ``values`` with window ``period``."""
    _check_period(period)
    n = len(values)
    if n == 0 or period >= n:
        return []

    gains: list[float] = [0.0] * n
    losses: list[float] = [0.0] * n
    for i in range(1, n):
        delta = values[i] - values[i - 1]
        if delta >= 0:
            gains[i] = delta
        else:
            losses[i] = -delta

    out: list[float | None] = [None] * (period)
    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period
    out.append(_rsi_value(avg_gain, avg_loss))

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out.append(_rsi_value(avg_gain, avg_loss))

    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    """Convert smoothed gain/loss to an RSI value in [0, 100]."""
    if avg_loss == 0:
        # All up moves (or no down moves yet): max RSI.
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["rsi"]
