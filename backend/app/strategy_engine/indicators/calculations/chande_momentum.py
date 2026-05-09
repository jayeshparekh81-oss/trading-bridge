"""Chande Momentum Oscillator (Tushar Chande, 1995).

Definition (matches Pine ``ta.cmo``):

    diff[i]   = close[i] - close[i - 1]
    up[i]     = diff[i] if diff[i] > 0 else 0
    down[i]   = -diff[i] if diff[i] < 0 else 0
    sum_up    = sum(up   over last ``period`` bars)
    sum_down  = sum(down over last ``period`` bars)
    CMO[i]    = 100 * (sum_up - sum_down) / (sum_up + sum_down)

Output range is ``[-100, +100]``. Unlike RSI, CMO uses the *raw*
sums (no Wilder smoothing) — it reacts faster but is noisier.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period >= len(values)`` -> ``[]`` (need ``period + 1`` bars
      for the first defined output, since ``diff`` skips bar 0).
    * Window with zero up + down totals -> ``None`` (division by
      zero — happens on a flat ``period``-bar window).
"""

from __future__ import annotations

from collections.abc import Sequence


def chande_momentum(
    values: Sequence[float], period: int = 9
) -> list[float | None]:
    """Chande Momentum Oscillator over ``period`` bars."""
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(values)
    # Need at least ``period + 1`` bars: bar 0 has no diff, then
    # ``period`` diffs to fill the first window.
    if n == 0 or period >= n:
        return []

    out: list[float | None] = [None] * n
    ups = [0.0] * n
    downs = [0.0] * n
    for i in range(1, n):
        d = values[i] - values[i - 1]
        if d > 0:
            ups[i] = d
        elif d < 0:
            downs[i] = -d

    for i in range(period, n):
        sum_up = sum(ups[i - period + 1 : i + 1])
        sum_down = sum(downs[i - period + 1 : i + 1])
        denom = sum_up + sum_down
        if denom == 0.0:
            out[i] = None
            continue
        out[i] = 100.0 * (sum_up - sum_down) / denom
    return out


__all__ = ["chande_momentum"]
