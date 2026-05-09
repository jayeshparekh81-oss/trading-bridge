"""True Range — single-bar volatility measure (no smoothing).

The unsmoothed input to ATR. Definition (Wilder, 1978):

    TR[0] = high[0] - low[0]
    TR[i] = max(
        high[i] - low[i],
        |high[i] - close[i - 1]|,
        |low[i]  - close[i - 1]|,
    )                                       for i >= 1

Useful as a standalone indicator when the strategy wants the *raw*
volatility tick, e.g. for sizing single-bar stops or filtering out
bars whose range is unusually small.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Mismatched lengths -> ``ValueError``.
    * Output length equals input length; bar 0 is the simple
      high-low (no prior close to extend the range).
"""

from __future__ import annotations

from collections.abc import Sequence


def true_range(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[float | None]:
    """True Range of every bar."""
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return []

    out: list[float | None] = [highs[0] - lows[0]]
    for i in range(1, n):
        out.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    return out


__all__ = ["true_range"]
