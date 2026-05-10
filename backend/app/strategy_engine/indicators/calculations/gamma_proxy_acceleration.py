"""Gamma proxy - second derivative of price (acceleration).

⚠️  PROXY, not Black-Scholes gamma. Real gamma is the rate at
which delta changes per 1 unit of underlying movement —
captures how *sharp* a position's directional exposure is. This
indicator approximates the *concept* via the second-difference
of close (price acceleration):

    velocity[i]     = close[i] - close[i - 1]
    acceleration[i] = velocity[i] - velocity[i - 1]
                    = close[i] - 2*close[i - 1] + close[i - 2]
    gamma[i]        = SMA(acceleration, period)[i]

Output is a smoothed acceleration signal centred near zero.
Positive = price accelerating upward; negative = decelerating
or accelerating downward.

Default ``period = 10``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n - 1`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def gamma_proxy_acceleration(
    closes: Sequence[float],
    period: int = 10,
) -> list[float | None]:
    """Smoothed second-difference of close - price acceleration."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n - 1:
        return []
    accel: list[float] = [0.0, 0.0]
    for i in range(2, n):
        accel.append(closes[i] - 2.0 * closes[i - 1] + closes[i - 2])
    out: list[float | None] = [None] * n
    for i in range(period + 1, n):
        # Smooth via SMA over the trailing ``period`` accel values.
        # accel[0..1] are placeholder zeros; the window slides past
        # them by index ``period + 1``.
        window = accel[i - period + 1 : i + 1]
        out[i] = sum(window) / period
    return out


__all__ = ["gamma_proxy_acceleration"]
