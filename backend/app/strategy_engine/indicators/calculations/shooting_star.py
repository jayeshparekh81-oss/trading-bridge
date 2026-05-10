"""Shooting Star candlestick pattern.

Mirror image of :mod:`hammer` — body in the lower third of the
range, long upper shadow, short lower shadow. Single-bar bearish
reversal hint.

Definition (matches :mod:`engines.candle_pattern` thresholds):

    range          = high - low
    body           = |close - open|
    upper_shadow   = high - max(open, close)
    lower_shadow   = min(open, close) - low

    Shooting star iff:
        range > 0
        body         <= body_ratio    * range  (default 0.30)
        upper_shadow >= shadow_ratio  * range  (default 0.60)
        lower_shadow <= 0.5 * upper_shadow

Direction (bullish vs bearish body) is allowed either way — context
is the strategy's job.

Edge cases per Phase 1 contract: same as :mod:`hammer`.
"""

from __future__ import annotations

from collections.abc import Sequence


def shooting_star(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    body_ratio: float = 0.3,
    shadow_ratio: float = 0.6,
) -> list[float | None]:
    """Detect shooting-star bars."""
    if not (0 < body_ratio < 1):
        raise ValueError(f"body_ratio must be in (0, 1); got {body_ratio!r}.")
    if not (0 < shadow_ratio < 1):
        raise ValueError(f"shadow_ratio must be in (0, 1); got {shadow_ratio!r}.")
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
            body <= rng * body_ratio
            and upper >= rng * shadow_ratio
            and lower <= upper * 0.5
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


__all__ = ["shooting_star"]
