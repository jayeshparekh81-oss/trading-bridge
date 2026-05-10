"""ZigZag — turning-point reversal filter.

Marks bars where price reversed by at least ``deviation_pct`` from
the most-recent confirmed extreme. Per-bar code:

    +1.0  → confirmed swing low at this bar (turn upward)
    -1.0  → confirmed swing high at this bar (turn downward)
     0.0  → not a turning point

ZigZag is a *visual* tool — turning-point assignment is
backward-looking-confirmed (a swing low at bar i is only known
once price moves > ``deviation_pct`` above it later). For
real-time strategies, treat each non-zero bar as the "we now
know bar i was a turning point" signal, not "this bar will be a
turn".

Default ``deviation_pct = 5.0``.

Edge cases:
    * Empty input -> ``[]``.
    * ``deviation_pct <= 0`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def zigzag(
    highs: Sequence[float],
    lows: Sequence[float],
    deviation_pct: float = 5.0,
) -> list[float | None]:
    """ZigZag turning-point markers."""
    if not isinstance(deviation_pct, (int, float)) or isinstance(deviation_pct, bool):
        raise ValueError(f"deviation_pct must be a number; got {deviation_pct!r}.")
    if deviation_pct <= 0:
        raise ValueError(f"deviation_pct must be > 0; got {deviation_pct}.")
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0:
        return []

    out: list[float | None] = [0.0] * n
    threshold = deviation_pct / 100.0
    # Track the most recent confirmed extreme.
    last_pivot_idx = 0
    last_pivot_price = highs[0]
    direction: int | None = None  # +1 = looking for a high; -1 = for a low

    for i in range(1, n):
        if direction is None:
            # First leg — pick whichever has moved further.
            if highs[i] >= last_pivot_price * (1 + threshold):
                direction = 1
                last_pivot_idx = i
                last_pivot_price = highs[i]
            elif lows[i] <= last_pivot_price * (1 - threshold):
                direction = -1
                last_pivot_idx = i
                last_pivot_price = lows[i]
            continue
        if direction == 1:
            # Climbing — extend the high or confirm it.
            if highs[i] > last_pivot_price:
                last_pivot_idx = i
                last_pivot_price = highs[i]
            elif lows[i] <= last_pivot_price * (1 - threshold):
                # Reversal confirmed → mark the prior pivot as a high.
                out[last_pivot_idx] = -1.0
                direction = -1
                last_pivot_idx = i
                last_pivot_price = lows[i]
        else:
            # direction == -1: descending leg.
            if lows[i] < last_pivot_price:
                last_pivot_idx = i
                last_pivot_price = lows[i]
            elif highs[i] >= last_pivot_price * (1 + threshold):
                out[last_pivot_idx] = 1.0
                direction = 1
                last_pivot_idx = i
                last_pivot_price = highs[i]
    return out


__all__ = ["zigzag"]
