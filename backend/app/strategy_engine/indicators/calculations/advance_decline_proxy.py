"""Advance-Decline Proxy — net bullish-bar count.

The real A/D line is market-wide: cumulative net of advancing
- declining issues. Single-symbol proxy uses bar direction:

    AD[i] = sum((+1 if close >= open else -1) for k in last `period` bars)

Range ``[-period, +period]``. Distinct from :mod:`tick_index`
which uses *close-to-close* direction; this uses *intra-bar*
(close vs open) direction.

Default ``period = 10``.

Output length equals input length. Indices ``0 .. period - 2``
are ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
    * Doji bar (close == open) treated as bullish (matches Pine's
      ``close >= open`` convention).
"""

from __future__ import annotations

from collections.abc import Sequence


def advance_decline_proxy(
    opens: Sequence[float],
    closes: Sequence[float],
    period: int = 10,
) -> list[float | None]:
    """Per-bar net intra-bar direction over the trailing window."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(opens)
    if n != len(closes):
        raise ValueError(
            f"opens and closes must have the same length; got {n}, {len(closes)}."
        )
    if n == 0 or period > n:
        return []
    bar_sign: list[int] = [
        1 if closes[i] >= opens[i] else -1 for i in range(n)
    ]
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        out[i] = float(sum(bar_sign[i - period + 1 : i + 1]))
    return out


__all__ = ["advance_decline_proxy"]
