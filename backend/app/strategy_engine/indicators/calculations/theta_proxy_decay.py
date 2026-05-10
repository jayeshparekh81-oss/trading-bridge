"""Theta proxy - per-bar realised range "decay" rate.

⚠️  PROXY, not Black-Scholes theta. Real theta is the rate at
which option price decays per unit time, derived from the
options-pricing model. This indicator approximates the *idea*
of time decay using observed bar ranges:

    decay[i] = avg_range_first_half(window) - avg_range_second_half(window)

Positive output = ranges shrinking (decay regime, options
sellers favoured); negative = ranges expanding (vol-of-vol
rising, options buyers favoured).

Default ``lookback = 20`` (half-window of 10 bars on each side).

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``lookback < 4`` rejected (need at least 2 bars per half).
    * ``lookback >= n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def theta_proxy_decay(
    highs: Sequence[float],
    lows: Sequence[float],
    lookback: int = 20,
) -> list[float | None]:
    """Per-bar range-shrinkage proxy."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 4:
        raise ValueError(f"lookback must be an int >= 4; got {lookback!r}.")
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0 or lookback >= n:
        return []
    half = lookback // 2
    ranges = [highs[i] - lows[i] for i in range(n)]
    out: list[float | None] = [None] * n
    for i in range(lookback - 1, n):
        first_half = ranges[i - lookback + 1 : i - lookback + 1 + half]
        second_half = ranges[i - half + 1 : i + 1]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        out[i] = avg_first - avg_second
    return out


__all__ = ["theta_proxy_decay"]
