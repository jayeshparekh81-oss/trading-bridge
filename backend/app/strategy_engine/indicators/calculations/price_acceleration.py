"""Price acceleration - second derivative of close.

ML-style feature. Computes velocity twice::

    velocity[i]     = (close[i] - close[i - period]) / period
    acceleration[i] = velocity[i] - velocity[i - period]

Equivalently, the change-in-rate-of-change. Output in price units
per bar^2. Positions ``0 .. 2 * period - 1`` are ``None``.

Edge cases:
    * Empty input -> ``[]``.
    * ``2 * period >= len(closes)`` -> ``[]``.
    * ``period`` not a positive int -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.price_velocity import (
    price_velocity,
)


def price_acceleration(
    closes: Sequence[float],
    period: int = 5,
) -> list[float | None]:
    """Second-difference of close (change in velocity over ``period``)."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(closes)
    if n == 0 or 2 * period >= n:
        return []
    velocity = price_velocity(list(closes), period)
    if not velocity:
        return []
    out: list[float | None] = [None] * n
    for i in range(2 * period, n):
        v_now = velocity[i]
        v_prev = velocity[i - period]
        if v_now is None or v_prev is None:
            continue
        out[i] = v_now - v_prev
    return out


__all__ = ["price_acceleration"]
