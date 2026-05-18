"""Kaufman's Adaptive Moving Average (KAMA, Perry J. Kaufman, 1995).

Variable-smoothing MA that adapts to "efficiency ratio" (ER) — the
ratio of net price change to total bar-by-bar variation over a
trailing window. In a strong trend ER ≈ 1 and KAMA accelerates;
in chop ER ≈ 0 and KAMA flattens out.

Canonical formulation:

    change[i]   = abs(close[i] - close[i - period])
    volatility[i] = sum_{k=0..period-1} abs(close[i-k] - close[i-k-1])
    ER[i] = change[i] / volatility[i]                  (0 when vol == 0)

    fast_sc = 2 / (fast + 1)        # default fast = 2  → 2/3
    slow_sc = 2 / (slow + 1)        # default slow = 30 → 2/31
    sc[i]   = (ER[i] * (fast_sc - slow_sc) + slow_sc) ** 2

    KAMA[period - 1] = close[period - 1]               # seed
    KAMA[i]          = KAMA[i-1] + sc[i] * (close[i] - KAMA[i-1])

Defaults match Kaufman's original (period=10, fast=2, slow=30).
Reference: ``ta.kaufman_adaptive_ma`` in pandas-ta and ``KAMA`` in
TA-Lib both implement this formula.

Edge cases:
    * Empty input -> ``[]``
    * ``period < 2`` rejected
    * ``fast < 1`` or ``slow <= fast`` rejected
    * ``len(values) < period`` -> ``[]`` (insufficient warm-up)
    * ``volatility == 0`` (flat window) -> ER = 0 → KAMA stays flat
"""

from __future__ import annotations

from collections.abc import Sequence


def kama(
    values: Sequence[float],
    period: int = 10,
    fast: int = 2,
    slow: int = 30,
) -> list[float | None]:
    """KAMA over ``values`` with the canonical (period, fast, slow) tuning."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be int >= 2; got {period!r}.")
    if not isinstance(fast, int) or isinstance(fast, bool) or fast < 1:
        raise ValueError(f"fast must be int >= 1; got {fast!r}.")
    if not isinstance(slow, int) or isinstance(slow, bool):
        raise ValueError(f"slow must be int; got {slow!r}.")
    if slow <= fast:
        raise ValueError(f"slow must be > fast; got fast={fast} slow={slow}.")

    n = len(values)
    if n == 0 or n < period:
        return []

    fast_sc = 2.0 / (fast + 1.0)
    slow_sc = 2.0 / (slow + 1.0)

    out: list[float | None] = [None] * n
    # Seed at index period-1 with the close at that index — matches
    # TA-Lib + pandas-ta seeding convention.
    out[period - 1] = float(values[period - 1])

    for i in range(period, n):
        change = abs(values[i] - values[i - period])
        volatility = 0.0
        for k in range(period):
            volatility += abs(values[i - k] - values[i - k - 1])
        if volatility == 0:
            er = 0.0
        else:
            er = change / volatility
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        prev = out[i - 1]
        assert prev is not None  # invariant: KAMA was seeded at period-1
        out[i] = prev + sc * (values[i] - prev)
    return out


__all__ = ["kama"]
