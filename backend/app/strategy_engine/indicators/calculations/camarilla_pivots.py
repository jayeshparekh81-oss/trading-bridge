"""Camarilla Pivots — intraday support/resistance ladder.

Definition (Slade, 1989):

    Reference inputs are the prior bar's H/L/C (e.g. yesterday's
    daily candle for an intraday session). The 4-level ladder this
    module emits — R3, R4, S3, S4 — is the most-watched subset:

        R4 = close + (high - low) * 1.1 / 2
        R3 = close + (high - low) * 1.1 / 4
        S3 = close - (high - low) * 1.1 / 4
        S4 = close - (high - low) * 1.1 / 2

Like :mod:`pivot_points`, this implementation uses bar ``i - 1``
as the reference for bar ``i``. Bar 0 is ``None`` for every level
(no prior bar). Session-anchored Camarilla pivots ship in a future
phase alongside the simulator's session awareness.

Output tuple: ``(r3, r4, s3, s4)``.

Edge cases per Phase 1 contract:
    * Empty input -> ``([], [], [], [])``.
    * Mismatched lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def camarilla_pivots(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> tuple[
    list[float | None],
    list[float | None],
    list[float | None],
    list[float | None],
]:
    """Return ``(r3, r4, s3, s4)`` Camarilla levels."""
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return ([], [], [], [])

    r3: list[float | None] = [None] * n
    r4: list[float | None] = [None] * n
    s3: list[float | None] = [None] * n
    s4: list[float | None] = [None] * n
    for i in range(1, n):
        rng = highs[i - 1] - lows[i - 1]
        c = closes[i - 1]
        r4[i] = c + rng * 1.1 / 2.0
        r3[i] = c + rng * 1.1 / 4.0
        s3[i] = c - rng * 1.1 / 4.0
        s4[i] = c - rng * 1.1 / 2.0
    return (r3, r4, s3, s4)


__all__ = ["camarilla_pivots"]
