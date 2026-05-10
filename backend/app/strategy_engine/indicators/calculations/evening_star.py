"""Evening Star candlestick pattern (three-bar bearish reversal).

Mirror of :mod:`morning_star`.

Definition:

    Bar i-2 bullish AND big-body:
        close[i-2] > open[i-2]
        body[i-2] >= big_body_ratio * range[i-2]   (default 0.5)

    Bar i-1 small body, gapped above bar i-2 body:
        |close[i-1] - open[i-1]| <= small_body_ratio * range[i-1]   (default 0.3)
        min(open[i-1], close[i-1]) > close[i-2]

    Bar i bearish AND closes below bar i-2 mid-body:
        close[i] < open[i]
        close[i] < (open[i-2] + close[i-2]) / 2
"""

from __future__ import annotations

from collections.abc import Sequence


def evening_star(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    small_body_ratio: float = 0.3,
    big_body_ratio: float = 0.5,
) -> list[float | None]:
    """Detect evening-star sequences."""
    if not (0 < small_body_ratio < 1):
        raise ValueError(
            f"small_body_ratio must be in (0, 1); got {small_body_ratio!r}."
        )
    if not (0 < big_body_ratio < 1):
        raise ValueError(
            f"big_body_ratio must be in (0, 1); got {big_body_ratio!r}."
        )
    n = _check_lengths(opens, highs, lows, closes)
    if n == 0:
        return []

    out: list[float | None] = [None, None] + [0.0] * (n - 2) if n >= 2 else [None] * n
    for i in range(2, n):
        rng_a = highs[i - 2] - lows[i - 2]
        rng_b = highs[i - 1] - lows[i - 1]
        if rng_a <= 0 or rng_b <= 0:
            continue
        body_a = abs(closes[i - 2] - opens[i - 2])
        body_b = abs(closes[i - 1] - opens[i - 1])
        bar_a_bullish_big = (
            closes[i - 2] > opens[i - 2]
            and body_a >= rng_a * big_body_ratio
        )
        if not bar_a_bullish_big:
            continue
        if body_b > rng_b * small_body_ratio:
            continue
        if min(opens[i - 1], closes[i - 1]) <= closes[i - 2]:
            continue
        if closes[i] >= opens[i]:
            continue
        midpoint_a = (opens[i - 2] + closes[i - 2]) / 2.0
        if closes[i] >= midpoint_a:
            continue
        out[i] = 1.0
    return out


def _check_lengths(*series: Sequence[float]) -> int:
    n = len(series[0])
    for s in series[1:]:
        if len(s) != n:
            raise ValueError(
                f"OHLC series must have the same length; got "
                f"{[len(x) for x in series]}."
            )
    return n


__all__ = ["evening_star"]
