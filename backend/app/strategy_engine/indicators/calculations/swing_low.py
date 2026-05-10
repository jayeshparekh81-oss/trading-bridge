"""Swing Low — pivot-low level confirmed after right-bars delay.

Mirror of :mod:`swing_high`. Matches Pine ``ta.pivotlow(left, right)``.

The pivot value appears in the output at index ``p + right_bars``
— never earlier. Output: ``lows[p]`` at index ``p + right_bars``
for every detected pivot; ``None`` elsewhere.

Edge cases per Phase 1 contract: same as :mod:`swing_high`.
"""

from __future__ import annotations

from collections.abc import Sequence


def swing_low(
    lows: Sequence[float],
    left_bars: int = 5,
    right_bars: int = 5,
) -> list[float | None]:
    """Confirmed pivot-low level series."""
    if not isinstance(left_bars, int) or left_bars < 1:
        raise ValueError(
            f"left_bars must be a positive int; got {left_bars!r}."
        )
    if not isinstance(right_bars, int) or right_bars < 1:
        raise ValueError(
            f"right_bars must be a positive int; got {right_bars!r}."
        )
    n = len(lows)
    if n == 0:
        return []

    out: list[float | None] = [None] * n
    for confirm_idx in range(left_bars + right_bars, n):
        pivot_idx = confirm_idx - right_bars
        window_start = pivot_idx - left_bars
        window = lows[window_start : confirm_idx + 1]
        if lows[pivot_idx] <= min(window):
            out[confirm_idx] = lows[pivot_idx]
    return out


__all__ = ["swing_low"]
