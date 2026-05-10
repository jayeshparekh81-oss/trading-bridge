"""Donchian Channel — Richard Donchian.

Three outputs (matches Pine ``ta.donchian``):

    * ``upper``  — highest high over the last ``period`` bars.
    * ``lower``  — lowest low over the last ``period`` bars.
    * ``middle`` — (upper + lower) / 2.

Heavily used in turtle-style breakout systems.

Edge cases per Phase 1 contract:
    * Empty input -> ``([], [], [])``.
    * ``period > len(values)`` -> ``([], [], [])``.
    * Mismatched lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def donchian_channel(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 20,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Return ``(upper, middle, lower)`` over ``period`` bars."""
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n} and {len(lows)}."
        )
    if n == 0 or period > n:
        return ([], [], [])

    upper: list[float | None] = [None] * n
    middle: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    for i in range(period - 1, n):
        hh = max(highs[i - period + 1 : i + 1])
        ll = min(lows[i - period + 1 : i + 1])
        upper[i] = hh
        lower[i] = ll
        middle[i] = (hh + ll) / 2.0
    return (upper, middle, lower)


__all__ = ["donchian_channel"]
