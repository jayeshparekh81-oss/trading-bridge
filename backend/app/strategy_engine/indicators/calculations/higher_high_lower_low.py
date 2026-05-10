"""Higher-high / lower-low pattern detector.

Per-bar code that summarises the relationship between the current
bar's extremes and the trailing ``lookback`` window of extremes:

    +1.0  → current high > max(prior highs) AND current low > max(prior lows)
            (textbook "higher high & higher low" — uptrend continuation)
    -1.0  → current high < min(prior highs) AND current low < min(prior lows)
            (textbook "lower high & lower low" — downtrend continuation)
     0.0  → mixed / consolidation

Default ``lookback = 5``. Output length equals input length;
indices ``0 .. lookback - 1`` are ``None``.
"""

from __future__ import annotations

from collections.abc import Sequence


def higher_high_lower_low(
    highs: Sequence[float],
    lows: Sequence[float],
    lookback: int = 5,
) -> list[float | None]:
    """HH/LL pattern code over a trailing ``lookback`` window."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback <= 0:
        raise ValueError(f"lookback must be a positive int; got {lookback!r}.")
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0 or lookback >= n:
        return []
    out: list[float | None] = [None] * n
    for i in range(lookback, n):
        prior_high = max(highs[i - lookback : i])
        prior_low_high = min(highs[i - lookback : i])
        prior_low = min(lows[i - lookback : i])
        prior_high_low = max(lows[i - lookback : i])
        if highs[i] > prior_high and lows[i] > prior_high_low:
            out[i] = 1.0
        elif highs[i] < prior_low_high and lows[i] < prior_low:
            out[i] = -1.0
        else:
            out[i] = 0.0
    return out


__all__ = ["higher_high_lower_low"]
