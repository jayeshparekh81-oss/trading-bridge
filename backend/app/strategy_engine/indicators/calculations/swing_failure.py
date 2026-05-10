"""Swing-failure pattern detector.

Flags bars where price *attempted* a new swing high / low but
closed back inside the prior range — a classic failure-swing
reversal candidate.

Per-bar code:

    +1.0  → bullish failure: low pierced prior swing low but
            close finished above it (bear trap / reversal up)
    -1.0  → bearish failure: high pierced prior swing high but
            close finished below it (bull trap / reversal down)
     0.0  → no failure pattern this bar

Default ``lookback = 10``. Output length equals input length;
indices ``0 .. lookback - 1`` are ``None``.
"""

from __future__ import annotations

from collections.abc import Sequence


def swing_failure(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    lookback: int = 10,
) -> list[float | None]:
    """Swing-failure pattern code over a trailing ``lookback`` window."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback <= 0:
        raise ValueError(f"lookback must be a positive int; got {lookback!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or lookback >= n:
        return []

    out: list[float | None] = [None] * n
    for i in range(lookback, n):
        prior_high = max(highs[i - lookback : i])
        prior_low = min(lows[i - lookback : i])
        if lows[i] < prior_low and closes[i] > prior_low:
            out[i] = 1.0  # bullish failure
        elif highs[i] > prior_high and closes[i] < prior_high:
            out[i] = -1.0  # bearish failure
        else:
            out[i] = 0.0
    return out


__all__ = ["swing_failure"]
