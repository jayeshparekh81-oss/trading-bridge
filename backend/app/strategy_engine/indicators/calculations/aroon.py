"""Aroon Up / Aroon Down / Aroon Oscillator.

Definition (Chande, 1995):

    Within the trailing window of ``period + 1`` bars (so the high /
    low can be at the very oldest bar)::

        bars_since_high = (period - argmax(highs[i - period .. i]))
        Aroon Up   = 100 * (period - bars_since_high) / period
        Aroon Down = 100 * (period - bars_since_low)  / period
        Oscillator = Aroon Up - Aroon Down

Output length equals input length. Indices ``0 .. period - 1`` are
``None``; from ``period`` onward the trio is filled in.

Edge cases per Phase 1 contract:
    * Empty input or mismatched high/low lengths -> ``[]`` /
      ``ValueError`` respectively.
    * ``period >= len(highs)`` -> three empty lists (at least
      ``period + 1`` bars are needed for one defined value).
"""

from __future__ import annotations

from collections.abc import Sequence


def aroon(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 25,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Return ``(aroon_up, aroon_down, oscillator)``."""
    _check_period(period)
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0 or period >= n:
        return [], [], []

    up: list[float | None] = [None] * n
    down: list[float | None] = [None] * n
    osc: list[float | None] = [None] * n

    for i in range(period, n):
        window_highs = highs[i - period : i + 1]
        window_lows = lows[i - period : i + 1]
        # ``index`` returns the *first* match — for a tie the oldest
        # extreme wins, which matches Pine's behaviour.
        bars_since_high = period - _argmax(window_highs)
        bars_since_low = period - _argmin(window_lows)
        up_val = 100.0 * (period - bars_since_high) / period
        down_val = 100.0 * (period - bars_since_low) / period
        up[i] = up_val
        down[i] = down_val
        osc[i] = up_val - down_val

    return up, down, osc


def _argmax(window: Sequence[float]) -> int:
    """First-occurrence argmax — ties resolve to the lowest index."""
    best = 0
    for i in range(1, len(window)):
        if window[i] > window[best]:
            best = i
    return best


def _argmin(window: Sequence[float]) -> int:
    """First-occurrence argmin."""
    best = 0
    for i in range(1, len(window)):
        if window[i] < window[best]:
            best = i
    return best


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["aroon"]
