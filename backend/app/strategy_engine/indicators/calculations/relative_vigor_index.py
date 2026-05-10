"""Relative Vigor Index (John Ehlers, 2002).

Compares the close-open spread to the high-low spread to measure
"vigor" — how decisively price closes within its range.

Definition (with the symmetric weighted-average kernel Ehlers
specifies)::

    co[i] = close[i] - open[i]
    hl[i] = high[i]  - low[i]
    co_smooth[i] = (co[i] + 2 * co[i - 1] + 2 * co[i - 2] + co[i - 3]) / 6
    hl_smooth[i] = (hl[i] + 2 * hl[i - 1] + 2 * hl[i - 2] + hl[i - 3]) / 6
    co_sum[i] = sum(co_smooth over period)
    hl_sum[i] = sum(hl_smooth over period)
    RVI[i]    = co_sum[i] / hl_sum[i]                     (0 if hl_sum == 0)

Default ``period = 14``. Output range is approximately ``[-1, +1]``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period >= n - 3`` (smoothing eats 3 bars) -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def relative_vigor_index(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """RVI line over a smoothed close-open / high-low ratio."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(opens)
    if n != len(highs) or n != len(lows) or n != len(closes):
        raise ValueError(
            f"opens, highs, lows, closes must have the same length; "
            f"got {n}, {len(highs)}, {len(lows)}, {len(closes)}."
        )
    minimum = period + 3
    if n == 0 or n < minimum:
        return []

    co = [closes[i] - opens[i] for i in range(n)]
    hl = [highs[i] - lows[i] for i in range(n)]

    co_smooth: list[float | None] = [None] * n
    hl_smooth: list[float | None] = [None] * n
    for i in range(3, n):
        co_smooth[i] = (
            co[i] + 2.0 * co[i - 1] + 2.0 * co[i - 2] + co[i - 3]
        ) / 6.0
        hl_smooth[i] = (
            hl[i] + 2.0 * hl[i - 1] + 2.0 * hl[i - 2] + hl[i - 3]
        ) / 6.0

    out: list[float | None] = [None] * n
    for i in range(period + 2, n):
        window_co = co_smooth[i - period + 1 : i + 1]
        window_hl = hl_smooth[i - period + 1 : i + 1]
        if any(v is None for v in window_co + window_hl):
            continue
        co_sum = sum(v for v in window_co if v is not None)
        hl_sum = sum(v for v in window_hl if v is not None)
        out[i] = 0.0 if hl_sum == 0 else co_sum / hl_sum
    return out


__all__ = ["relative_vigor_index"]
