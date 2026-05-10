"""Inside Bar — single-bar consolidation pattern.

Bar ``i`` is an *inside bar* when its range is fully contained
within bar ``i - 1``'s range:

    high[i] <= high[i - 1]
    low[i]  >= low[i - 1]

Outputs 1.0 / 0.0; bar 0 is ``None`` (no prior bar to compare
against).

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Mismatched lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def inside_bar(
    highs: Sequence[float],
    lows: Sequence[float],
) -> list[float | None]:
    """Detect inside bars."""
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n} and {len(lows)}."
        )
    if n == 0:
        return []

    out: list[float | None] = [None] + [0.0] * (n - 1)
    for i in range(1, n):
        if highs[i] <= highs[i - 1] and lows[i] >= lows[i - 1]:
            out[i] = 1.0
    return out


__all__ = ["inside_bar"]
