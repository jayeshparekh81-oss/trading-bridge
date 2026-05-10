"""Sentiment Oscillator — % of bullish bars in trailing window.

Definition::

    SO[i] = sum(close[k] >= open[k] for k in last `period` bars) / period * 100

Range ``[0, 100]``. > 70 = persistent bullish sentiment;
< 30 = persistent bearish sentiment.

Default ``period = 20``.

Output length equals input length. Indices ``0 .. period - 2``
are ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def sentiment_oscillator(
    opens: Sequence[float],
    closes: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Per-bar % of bullish bars in the trailing window."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(opens)
    if n != len(closes):
        raise ValueError(
            f"opens and closes must have the same length; got {n}, {len(closes)}."
        )
    if n == 0 or period > n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        bullish = sum(
            1 for k in range(i - period + 1, i + 1)
            if closes[k] >= opens[k]
        )
        out[i] = bullish / period * 100.0
    return out


__all__ = ["sentiment_oscillator"]
