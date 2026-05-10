"""Classic Pivot Points — daily PP plus R1/R2 and S1/S2.

This is the *bar-shift* implementation Pine traders use when they don't
have intraday session boundaries: pivots at bar ``i`` are computed from
bar ``i - 1``'s high / low / close::

    PP = (H + L + C) / 3
    R1 = 2 * PP - L
    S1 = 2 * PP - H
    R2 = PP + (H - L)
    S2 = PP - (H - L)

True daily pivots (using the prior session's bars rather than the prior
bar) are a Phase 11 enhancement when the simulator gains session
awareness.

Output length equals input length. Index 0 is ``None`` for every level
(no prior bar). All five outputs are filled from index 1 onward.

Edge cases per Phase 1 contract:
    * Empty input or mismatched lengths -> ``[]`` / ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def pivot_points(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> tuple[
    list[float | None],
    list[float | None],
    list[float | None],
    list[float | None],
    list[float | None],
]:
    """Return ``(pp, r1, r2, s1, s2)``."""
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return [], [], [], [], []

    pp: list[float | None] = [None] * n
    r1: list[float | None] = [None] * n
    r2: list[float | None] = [None] * n
    s1: list[float | None] = [None] * n
    s2: list[float | None] = [None] * n

    for i in range(1, n):
        h = highs[i - 1]
        low = lows[i - 1]
        c = closes[i - 1]
        pp_val = (h + low + c) / 3.0
        rng = h - low
        pp[i] = pp_val
        r1[i] = 2 * pp_val - low
        s1[i] = 2 * pp_val - h
        r2[i] = pp_val + rng
        s2[i] = pp_val - rng

    return pp, r1, r2, s1, s2


__all__ = ["pivot_points"]
