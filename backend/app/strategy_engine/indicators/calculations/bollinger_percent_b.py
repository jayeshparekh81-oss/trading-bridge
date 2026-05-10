"""Bollinger %B — where the source price sits within the band.

Definition::

    upper, middle, lower = bollinger_bands(values, period, std_dev)
    %B                   = (value - lower) / (upper - lower)

Output range is roughly 0-1 when price is *inside* the bands and
goes negative / above 1 when price pierces them. ``0.5`` = at the
mid-band; ``1.0`` = at the upper band; ``0.0`` = at the lower band.

Default ``period = 20``, ``std_dev = 2``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period > n`` -> ``[]``.
    * ``upper == lower`` for a bar (zero-width band) -> ``None``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.bollinger_bands import (
    bollinger_bands,
)


def bollinger_percent_b(
    values: Sequence[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> list[float | None]:
    """Bollinger %B — fractional position within the band."""
    upper, _middle, lower = bollinger_bands(list(values), period, std_dev)
    n = len(values)
    if not upper:
        return []
    out: list[float | None] = [None] * n
    for i in range(n):
        u = upper[i]
        lo = lower[i]
        if u is None or lo is None:
            continue
        width = u - lo
        if width == 0:
            continue
        out[i] = (values[i] - lo) / width
    return out


__all__ = ["bollinger_percent_b"]
