"""High-Low Spread — bar range as a percentage of close.

Definition:

    HLS[i] = (high[i] - low[i]) / close[i] * 100

Useful for filtering bars where the true range is unusually small
(consolidation) or unusually large (event-driven spikes). Unitless
% so different-priced symbols are comparable.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Mismatched lengths -> ``ValueError``.
    * ``close <= 0`` -> ``None`` for that bar (division would be
      undefined or sign-flipped).
"""

from __future__ import annotations

from collections.abc import Sequence


def high_low_spread(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[float | None]:
    """High-low spread as a percent of close."""
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return []

    out: list[float | None] = [None] * n
    for i in range(n):
        if closes[i] <= 0:
            continue
        out[i] = (highs[i] - lows[i]) / closes[i] * 100.0
    return out


__all__ = ["high_low_spread"]
