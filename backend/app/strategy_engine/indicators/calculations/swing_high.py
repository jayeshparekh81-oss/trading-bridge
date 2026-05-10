"""Swing High — pivot-high level confirmed after right-bars delay.

Matches Pine ``ta.pivothigh(left, right)``: a bar at index ``p``
is a swing high iff its high is the maximum across the window
``[p - left_bars, p + right_bars]`` (inclusive). The pivot value
appears in the output at index ``p + right_bars`` — never earlier
— because the look-ahead window only completes ``right_bars`` bars
after the actual pivot.

Output: ``highs[p]`` at index ``p + right_bars`` for every detected
pivot; ``None`` everywhere else (including the actual pivot bar
itself, which is still inside its confirmation window).

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Insufficient bars (``left + right + 1 > n``) -> ``[None] * n``.
"""

from __future__ import annotations

from collections.abc import Sequence


def swing_high(
    highs: Sequence[float],
    left_bars: int = 5,
    right_bars: int = 5,
) -> list[float | None]:
    """Confirmed pivot-high level series."""
    if not isinstance(left_bars, int) or left_bars < 1:
        raise ValueError(
            f"left_bars must be a positive int; got {left_bars!r}."
        )
    if not isinstance(right_bars, int) or right_bars < 1:
        raise ValueError(
            f"right_bars must be a positive int; got {right_bars!r}."
        )
    n = len(highs)
    if n == 0:
        return []

    out: list[float | None] = [None] * n
    for confirm_idx in range(left_bars + right_bars, n):
        pivot_idx = confirm_idx - right_bars
        window_start = pivot_idx - left_bars
        window = highs[window_start : confirm_idx + 1]
        if highs[pivot_idx] >= max(window):
            out[confirm_idx] = highs[pivot_idx]
    return out


__all__ = ["swing_high"]
