"""Inside-bar breakout detector.

Per-bar code emitted *one bar after* an inside bar:

    +1.0  → prior bar was inside, current bar broke above its high
    -1.0  → prior bar was inside, current bar broke below its low
     0.0  → no inside-bar-breakout pattern at this bar

Distinct from Pack-4's :mod:`inside_bar` (single boolean — "is
this bar inside the prior?"). This module pairs the inside-bar
recognition with the breakout direction on the *next* bar — a
direct entry signal rather than a structural marker.

Output length equals input length. Indices 0 and 1 are always
``None`` (need bar i-2 for the parent + bar i-1 for the inside).
"""

from __future__ import annotations

from collections.abc import Sequence


def inside_bar_breakout(
    highs: Sequence[float],
    lows: Sequence[float],
) -> list[float | None]:
    """Inside-bar-breakout per-bar code."""
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n < 3:
        return []
    out: list[float | None] = [None] * n
    for i in range(2, n):
        # Bar i - 1 is "inside" if its high <= bar i-2's high AND
        # its low >= bar i-2's low.
        is_inside = (
            highs[i - 1] <= highs[i - 2] and lows[i - 1] >= lows[i - 2]
        )
        if not is_inside:
            out[i] = 0.0
            continue
        if highs[i] > highs[i - 1]:
            out[i] = 1.0
        elif lows[i] < lows[i - 1]:
            out[i] = -1.0
        else:
            out[i] = 0.0
    return out


__all__ = ["inside_bar_breakout"]
