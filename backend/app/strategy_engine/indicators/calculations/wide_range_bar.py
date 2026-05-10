"""Wide-Range Bar — expansion-of-range detector.

Per-bar code:

    +1.0  -> bar's range > mult * rolling-average range (bullish close)
    -1.0  -> bar's range > mult * rolling-average range (bearish close)
     0.0  -> not a wide-range bar

Symmetric concept to :mod:`nr7` (compression) — wide-range bars
mark conviction-driven expansion. We pair the size signal with
the bar's direction so the value carries sign.

Defaults ``lookback = 20``, ``mult = 1.5``.

Output length equals input length. Indices ``0 .. lookback - 1``
are ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``lookback >= n`` -> ``[]``.
    * Window with zero average range -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def wide_range_bar(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    lookback: int = 20,
    mult: float = 1.5,
) -> list[float | None]:
    """Wide-range-bar per-bar code."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback <= 0:
        raise ValueError(f"lookback must be a positive int; got {lookback!r}.")
    if not isinstance(mult, (int, float)) or isinstance(mult, bool):
        raise ValueError(f"mult must be a number; got {mult!r}.")
    if mult <= 0:
        raise ValueError(f"mult must be > 0; got {mult}.")
    n = len(highs)
    if n != len(lows) or n != len(opens) or n != len(closes):
        raise ValueError(
            f"opens, highs, lows, closes must have the same length; "
            f"got {n}, {len(highs)}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or lookback >= n:
        return []

    ranges = [highs[i] - lows[i] for i in range(n)]
    out: list[float | None] = [None] * n
    for i in range(lookback, n):
        avg = sum(ranges[i - lookback : i]) / lookback
        if avg == 0:
            continue
        if ranges[i] < mult * avg:
            out[i] = 0.0
        else:
            out[i] = 1.0 if closes[i] >= opens[i] else -1.0
    return out


__all__ = ["wide_range_bar"]
