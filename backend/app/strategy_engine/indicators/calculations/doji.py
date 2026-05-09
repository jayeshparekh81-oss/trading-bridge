"""Doji candlestick pattern.

A doji has near-equal open and close — body is small relative to the
total range. Signals indecision; reversal interpretation depends on
the surrounding context (uptrend → potential top; downtrend →
potential bottom).

Definition (matches the existing :mod:`engines.candle_pattern`
threshold of 10 % so single-bar / strategy-rule users see the same
detections):

    body  = |close - open|
    range = high - low
    Doji iff range > 0 and body <= body_ratio * range.

A bar with ``high == low`` (zero range, every price equal) is a
degenerate doji — body and range are both zero. Match.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Mismatched input lengths -> ``ValueError``.
    * Output length equals input length; every bar carries 1.0 / 0.0.
"""

from __future__ import annotations

from collections.abc import Sequence


def doji(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    body_ratio: float = 0.1,
) -> list[float | None]:
    """Detect doji bars."""
    if body_ratio <= 0 or body_ratio > 1:
        raise ValueError(f"body_ratio must be in (0, 1]; got {body_ratio!r}.")
    n = _check_lengths(opens, highs, lows, closes)
    if n == 0:
        return []

    out: list[float | None] = [0.0] * n
    for i in range(n):
        rng = highs[i] - lows[i]
        body = abs(closes[i] - opens[i])
        if rng <= 0:
            # Degenerate flat bar — treat as a doji.
            out[i] = 1.0
            continue
        out[i] = 1.0 if body <= rng * body_ratio else 0.0
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


__all__ = ["doji"]
