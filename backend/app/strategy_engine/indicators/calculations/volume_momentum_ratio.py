"""Volume momentum ratio - velocity-of-volume vs velocity-of-price.

ML-style feature. Formed from the two first-derivatives::

    vol_vel   = (volume[i] - volume[i - period]) / period
    price_vel = (close[i]  - close[i - period])  / period
    ratio     = vol_vel / max(|price_vel|, eps)

Where ``eps = max(close[i] * 1e-6, 1e-9)`` to keep the denominator
strictly positive but proportional to price scale (so a NIFTY
close near 24000 doesn't trigger eps from a large-but-real-tiny
price_vel). Sign of the ratio is the volume direction; magnitude
is how fast volume is changing per unit of price velocity.

When ``|price_vel|`` is below the eps floor (essentially a flat
price), the ratio is undefined and emits ``None`` (the volume-
velocity number alone is not particularly meaningful without
price context).

Output length matches input. Positions ``0 .. period - 1`` are
``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period >= len(closes)`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def volume_momentum_ratio(
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Volume-velocity / price-velocity ratio."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    if n == 0 or period >= n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period, n):
        price_vel = (closes[i] - closes[i - period]) / period
        vol_vel = (volumes[i] - volumes[i - period]) / period
        eps = max(abs(closes[i]) * 1e-6, 1e-9)
        if abs(price_vel) < eps:
            continue
        out[i] = vol_vel / abs(price_vel)
    return out


__all__ = ["volume_momentum_ratio"]
