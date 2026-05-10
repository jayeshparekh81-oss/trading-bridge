"""Narrowest-Range-7 (NR7) — compression / pre-breakout detector.

Per-bar code:

    +1.0  → current bar's range is the narrowest of the last 7 bars
     0.0  → not the narrowest

Coined by Tony Crabel (1990 *Day Trading with Short Term Price
Patterns*). Bars compressed to the smallest range in 7 sessions
often precede a directional breakout. The signal is *symmetric*
— it doesn't predict direction, only that compression has built up.

Output length equals input length. Indices ``0 .. 5`` are
``None`` (need 6 prior bars to compare against).
"""

from __future__ import annotations

from collections.abc import Sequence

#: Hardcoded 7 — the indicator's name pins the window.
_NR_WINDOW = 7


def nr7(
    highs: Sequence[float],
    lows: Sequence[float],
) -> list[float | None]:
    """Narrowest-Range-7 per-bar code."""
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n < _NR_WINDOW:
        return []
    ranges = [highs[i] - lows[i] for i in range(n)]
    out: list[float | None] = [None] * n
    for i in range(_NR_WINDOW - 1, n):
        window = ranges[i - _NR_WINDOW + 1 : i + 1]
        out[i] = 1.0 if ranges[i] == min(window) else 0.0
    return out


__all__ = ["nr7"]
