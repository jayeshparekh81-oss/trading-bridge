"""Bollinger Bandwidth — band width as a percentage of the mid-band.

Definition::

    upper, middle, lower = bollinger_bands(values, period, std_dev)
    BBW                  = (upper - lower) / middle * 100

Output is a percentage (e.g. ``2.4`` means the band span is 2.4 %
of the mid-band). Useful as a *volatility regime* signal —
contracted bandwidth ("squeeze") often precedes a breakout.

Default ``period = 20``, ``std_dev = 2``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period > n`` -> ``[]``.
    * ``middle == 0`` for a bar -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.bollinger_bands import (
    bollinger_bands,
)


def bollinger_bandwidth(
    values: Sequence[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> list[float | None]:
    """Bollinger Bandwidth as a percentage of the mid-band."""
    upper, middle, lower = bollinger_bands(list(values), period, std_dev)
    n = len(values)
    if not upper:
        return []
    out: list[float | None] = [None] * n
    for i in range(n):
        u = upper[i]
        m = middle[i]
        lo = lower[i]
        if u is None or m is None or lo is None or m == 0:
            continue
        out[i] = (u - lo) / m * 100.0
    return out


__all__ = ["bollinger_bandwidth"]
