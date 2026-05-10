"""Woodie Pivots — close-weighted central pivot variant.

Definition:

    PP = (H + L + 2 * C) / 4              (close-weighted central pivot)
    R1 = 2 * PP - L
    R2 = PP + (H - L)
    S1 = 2 * PP - H
    S2 = PP - (H - L)

H/L/C are taken from the prior bar — same convention as the
existing :mod:`pivot_points`. Bar 0 is ``None`` for every level.

Output tuple: ``(pp, r1, r2, s1, s2)``.

Edge cases per Phase 1 contract: same as :mod:`camarilla_pivots`.
"""

from __future__ import annotations

from collections.abc import Sequence


def woodie_pivots(
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
    """Return ``(pp, r1, r2, s1, s2)`` Woodie pivot levels."""
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return ([], [], [], [], [])

    pp: list[float | None] = [None] * n
    r1: list[float | None] = [None] * n
    r2: list[float | None] = [None] * n
    s1: list[float | None] = [None] * n
    s2: list[float | None] = [None] * n
    for i in range(1, n):
        h = highs[i - 1]
        lo = lows[i - 1]
        c = closes[i - 1]
        rng = h - lo
        pivot = (h + lo + 2.0 * c) / 4.0
        pp[i] = pivot
        r1[i] = 2.0 * pivot - lo
        r2[i] = pivot + rng
        s1[i] = 2.0 * pivot - h
        s2[i] = pivot - rng
    return (pp, r1, r2, s1, s2)


__all__ = ["woodie_pivots"]
