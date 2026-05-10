"""Price Volume Trend (PVT, Joseph Granville-style).

Definition::

    PVT[0] = 0
    PVT[i] = PVT[i - 1] + ((close[i] - close[i - 1]) / close[i - 1]) * volume[i]

Cumulative — no parameters, no warm-up gap. Tracks volume weighted
by percentage price change. Rising PVT confirms an uptrend; a
divergence between PVT and price warns of a fading move.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``close[i-1] == 0`` -> contribution that bar is 0 (avoid div-by-zero).
"""

from __future__ import annotations

from collections.abc import Sequence


def price_volume_trend(
    closes: Sequence[float],
    volumes: Sequence[float],
) -> list[float | None]:
    """Cumulative PVT — no parameters."""
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    if n == 0:
        return []

    out: list[float | None] = [0.0]
    running = 0.0
    for i in range(1, n):
        prev = closes[i - 1]
        increment = (
            0.0 if prev == 0 else ((closes[i] - prev) / prev) * volumes[i]
        )
        running += increment
        out.append(running)
    return out


__all__ = ["price_volume_trend"]
