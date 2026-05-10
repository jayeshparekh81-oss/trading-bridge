"""Cycle Period Oscillator — period-normalised price-position oscillator.

A simpler, no-Hilbert cousin of the MESA family. For each bar
positions the close inside its trailing high/low envelope and
maps to ``[-1, +1]``:

    out[i] = 2 * (close[i] - low_window) / (high_window - low_window) - 1

Where ``high_window`` and ``low_window`` are the highest-high and
lowest-low over the trailing ``period`` bars.

Default ``period = 14``. Output is identical in shape to a
fast-stochastic %K mapped from 0-100 to -1..+1; the
"cycle" framing is just operator preference for cycle-trading
strategies that already use MESA-style indicators.

Output length equals input length. Indices ``0 .. period - 2`` are
``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
    * Flat window (high == low) -> ``0.0`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def cycle_period_oscillator(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Period-normalised oscillator over close inside the trailing
    high/low envelope."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or period > n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        hh = max(highs[i - period + 1 : i + 1])
        ll = min(lows[i - period + 1 : i + 1])
        rng = hh - ll
        if rng == 0:
            out[i] = 0.0
        else:
            out[i] = 2.0 * (closes[i] - ll) / rng - 1.0
    return out


__all__ = ["cycle_period_oscillator"]
