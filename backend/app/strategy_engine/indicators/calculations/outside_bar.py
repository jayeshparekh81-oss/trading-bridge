"""Outside-bar detector — bar that engulfs the prior bar's range.

Per-bar code:

    +1.0  → outside bar with bullish close (close >= open) — bullish engulfing range
    -1.0  → outside bar with bearish close (close < open)  — bearish engulfing range
     0.0  → not an outside bar

An outside bar prints when ``high[i] > high[i-1]`` AND
``low[i] < low[i-1]`` — strictly engulfs the prior bar's range.

Output length equals input length. Index 0 is always ``None`` (no
prior bar to compare).
"""

from __future__ import annotations

from collections.abc import Sequence


def outside_bar(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[float | None]:
    """Outside-bar per-bar code."""
    n = len(highs)
    if n != len(lows) or n != len(opens) or n != len(closes):
        raise ValueError(
            f"opens, highs, lows, closes must have the same length; "
            f"got {n}, {len(highs)}, {len(lows)}, {len(closes)}."
        )
    if n < 2:
        return []
    out: list[float | None] = [None] * n
    for i in range(1, n):
        is_outside = (
            highs[i] > highs[i - 1] and lows[i] < lows[i - 1]
        )
        if not is_outside:
            out[i] = 0.0
            continue
        out[i] = 1.0 if closes[i] >= opens[i] else -1.0
    return out


__all__ = ["outside_bar"]
