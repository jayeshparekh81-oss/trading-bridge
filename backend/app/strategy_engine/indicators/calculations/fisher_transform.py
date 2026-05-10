"""Fisher Transform of price (John Ehlers, 2002).

Maps the closing price into a near-Gaussian distribution so that
extremes become statistically rare — sharp turns in the Fisher
line line up with reversal points in the underlying.

Definition::

    median[i] = (high[i] + low[i]) / 2
    HH[i] = max(median over period)
    LL[i] = min(median over period)
    raw[i]  = 0.66 * ((median[i] - LL[i]) / (HH[i] - LL[i]) - 0.5) + 0.67 * raw[i - 1]
    raw[i]  = clamp(raw[i], -0.999, 0.999)
    fish[i] = 0.5 * ln((1 + raw[i]) / (1 - raw[i])) + 0.5 * fish[i - 1]

Default ``period = 9``.

Output length equals input length. ``None`` for the warm-up
(period - 1 bars).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period >= n`` -> ``[]``.
    * Flat window (HH == LL) -> raw component contributes 0 that bar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def fisher_transform(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 9,
) -> list[float | None]:
    """Fisher Transform of the median-price series."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 1:
        raise ValueError(f"period must be an int > 1; got {period!r}.")
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0 or period >= n:
        return []

    median = [(highs[i] + lows[i]) / 2.0 for i in range(n)]
    raw_prev = 0.0
    fish_prev = 0.0
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = median[i - period + 1 : i + 1]
        hh = max(window)
        ll = min(window)
        rng = hh - ll
        if rng == 0:
            raw = 0.67 * raw_prev
        else:
            raw = 0.66 * ((median[i] - ll) / rng - 0.5) + 0.67 * raw_prev
        # Clamp to keep the log argument finite.
        if raw > 0.999:
            raw = 0.999
        elif raw < -0.999:
            raw = -0.999
        fish = 0.5 * math.log((1.0 + raw) / (1.0 - raw)) + 0.5 * fish_prev
        out[i] = fish
        raw_prev = raw
        fish_prev = fish
    return out


__all__ = ["fisher_transform"]
