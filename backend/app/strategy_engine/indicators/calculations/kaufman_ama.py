"""Kaufman Adaptive Moving Average (KAMA, Perry Kaufman, 1995).

Adapts smoothing speed to the *efficiency ratio* — how directly
price moved across the trailing window. Trending price → fast
smoothing; choppy / sideways price → slow smoothing.

Definition::

    direction[i]   = abs(close[i] - close[i - period])
    volatility[i]  = sum(abs(close[k] - close[k - 1]) for k in last `period` bars)
    er[i]          = direction[i] / volatility[i]                   # 0..1
    fast_alpha     = 2 / (fast + 1)
    slow_alpha     = 2 / (slow + 1)
    sc[i]          = (er[i] * (fast_alpha - slow_alpha) + slow_alpha)^2
    KAMA[i]        = KAMA[i - 1] + sc[i] * (close[i] - KAMA[i - 1])

Defaults ``period = 10``, ``fast = 2``, ``slow = 30``.

Output length equals input length. ``None`` until index ``period``
where the seed lands (KAMA seeded with ``close[period - 1]``).

Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` / ``fast < 1`` / ``slow < 1`` rejected.
    * ``fast >= slow`` rejected.
    * Zero-volatility window -> ``er = 0`` (slowest smoothing).
"""

from __future__ import annotations

from collections.abc import Sequence


def kaufman_ama(
    values: Sequence[float],
    period: int = 10,
    fast: int = 2,
    slow: int = 30,
) -> list[float | None]:
    """Kaufman Adaptive Moving Average."""
    _validate(period, fast, slow)
    n = len(values)
    if n == 0 or period >= n:
        return []

    fast_alpha = 2.0 / (fast + 1)
    slow_alpha = 2.0 / (slow + 1)
    out: list[float | None] = [None] * n
    out[period - 1] = values[period - 1]
    for i in range(period, n):
        direction = abs(values[i] - values[i - period])
        volatility = sum(
            abs(values[k] - values[k - 1])
            for k in range(i - period + 1, i + 1)
        )
        er = 0.0 if volatility == 0 else direction / volatility
        sc_term = er * (fast_alpha - slow_alpha) + slow_alpha
        sc = sc_term * sc_term
        prev = out[i - 1]
        if prev is None:
            prev = values[i - 1]
        out[i] = prev + sc * (values[i] - prev)
    return out


def _validate(period: int, fast: int, slow: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    if not isinstance(fast, int) or isinstance(fast, bool) or fast < 1:
        raise ValueError(f"fast must be a positive int; got {fast!r}.")
    if not isinstance(slow, int) or isinstance(slow, bool) or slow < 1:
        raise ValueError(f"slow must be a positive int; got {slow!r}.")
    if fast >= slow:
        raise ValueError(
            f"fast must be strictly less than slow; got fast={fast}, slow={slow}."
        )


__all__ = ["kaufman_ama"]
