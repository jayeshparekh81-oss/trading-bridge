"""Supertrend V2 — adaptive-multiplier Supertrend variant.

Distinct from the existing ``supertrend`` (which uses a fixed
ATR multiplier). V2 scales the multiplier with the current
volatility regime: when ATR percent is in the upper quartile
of its trailing distribution, the bands widen (multiplier ↑);
when in the lower quartile, the bands tighten (multiplier ↓).

This reduces the classic Supertrend whipsaw problem in low-
volatility chop while still capturing trends in high-volatility
markets.

Definition::

    base_mult                = atr_mult
    regime[i]                = volatility_regime(period=lookback)[i]
                                # 0=Calm, 1=Normal, 2=Elevated, 3=Extreme
    effective_mult[i]        = base_mult * (0.7 + 0.2 * regime[i])
                                # 0.7x, 0.9x, 1.1x, 1.3x of base
    upper[i] = (high + low)/2 + effective_mult[i] * ATR[i]
    lower[i] = (high + low)/2 - effective_mult[i] * ATR[i]
    Supertrend[i] = upper[i] if downtrend else lower[i]

We expose the *line* (the active band) as the primary output;
direction switching follows the standard Supertrend convention.

Defaults ``period = 10``, ``atr_mult = 3.0``,
``volatility_lookback = 100`` (passed to volatility_regime).

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Insufficient bars -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr
from app.strategy_engine.indicators.calculations.volatility_regime import (
    volatility_regime,
)


def supertrend_v2(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 10,
    atr_mult: float = 3.0,
    volatility_lookback: int = 100,
) -> list[float | None]:
    """Adaptive-multiplier Supertrend line."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if not isinstance(atr_mult, (int, float)) or isinstance(atr_mult, bool):
        raise ValueError(f"atr_mult must be a number; got {atr_mult!r}.")
    if atr_mult <= 0:
        raise ValueError(f"atr_mult must be > 0; got {atr_mult}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return []

    atr_series = atr(highs, lows, closes, period)
    regime = volatility_regime(highs, lows, closes, volatility_lookback, period)
    if not atr_series:
        return [None] * n

    out: list[float | None] = [None] * n
    direction = 1  # 1 = uptrend (use lower band); -1 = downtrend
    prev_upper = 0.0
    prev_lower = 0.0
    for i in range(period, n):
        a = atr_series[i]
        if a is None:
            continue
        # Default to "Normal" (1.0) when regime hasn't warmed up yet.
        r = regime[i] if i < len(regime) and regime[i] is not None else 1.0
        # Rebuild the explicit float — narrowing across the
        # mixed list[float | None] is opaque to mypy.
        eff_mult = atr_mult * (0.7 + 0.2 * float(r))  # type: ignore[arg-type]
        mid = (highs[i] + lows[i]) / 2.0
        upper = mid + eff_mult * a
        lower = mid - eff_mult * a
        # Standard Supertrend band-tightening rule: never let the
        # active band widen against an existing trend.
        if i > period:
            if direction == 1 and lower < prev_lower:
                lower = prev_lower
            if direction == -1 and upper > prev_upper:
                upper = prev_upper
        if closes[i] > prev_upper and direction == -1:
            direction = 1
        elif closes[i] < prev_lower and direction == 1:
            direction = -1
        out[i] = lower if direction == 1 else upper
        prev_upper = upper
        prev_lower = lower
    return out


__all__ = ["supertrend_v2"]
