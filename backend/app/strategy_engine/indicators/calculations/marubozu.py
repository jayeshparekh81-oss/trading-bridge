"""Marubozu candlestick pattern.

Solid candle with no (or near-zero) wicks — open == low and
close == high (bullish) OR open == high and close == low (bearish).

Definition:

    range          = high - low
    body           = |close - open|
    upper_shadow   = high - max(open, close)
    lower_shadow   = min(open, close) - low

    Marubozu iff:
        range > 0
        upper_shadow <= max_wick_ratio * range  (default 0.05)
        lower_shadow <= max_wick_ratio * range
        body         >= (1 - 2 * max_wick_ratio) * range

Direction-agnostic — bullish and bearish marubozu both detected.
Strategy-level filtering by close > open / close < open is the
caller's job (use the existing ``CandleCondition`` pattern).

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Mismatched lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def marubozu(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    max_wick_ratio: float = 0.05,
) -> list[float | None]:
    """Detect marubozu bars."""
    if not (0 <= max_wick_ratio < 0.5):
        raise ValueError(
            f"max_wick_ratio must be in [0, 0.5); got {max_wick_ratio!r}."
        )
    n = _check_lengths(opens, highs, lows, closes)
    if n == 0:
        return []

    out: list[float | None] = [0.0] * n
    for i in range(n):
        rng = highs[i] - lows[i]
        if rng <= 0:
            continue
        body_top = max(opens[i], closes[i])
        body_bottom = min(opens[i], closes[i])
        body = body_top - body_bottom
        upper = highs[i] - body_top
        lower = body_bottom - lows[i]
        if (
            upper <= rng * max_wick_ratio
            and lower <= rng * max_wick_ratio
            and body >= rng * (1.0 - 2.0 * max_wick_ratio)
        ):
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


__all__ = ["marubozu"]
