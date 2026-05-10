"""TTM Squeeze Pro - 4-level squeeze tightness using two KC widths.

Carter's "Pro" extension grades how compressed the Bollinger-inside-
Keltner squeeze is by checking against two Keltner widths:

    * tight squeeze  - BB inside narrow-KC  (multiplier = low_volatility_mult)
    * normal squeeze - BB inside mid-KC   (multiplier = (low + high) / 2)
    * loose squeeze  - BB inside wide-KC  (multiplier = high_volatility_mult)
    * no squeeze     - BB outside all three

Output line:
    3.0 = tight squeeze (highest compression, biggest expected pop)
    2.0 = normal squeeze
    1.0 = loose squeeze
    0.0 = no squeeze

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``low_volatility_mult >= high_volatility_mult`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.bollinger_bands import (
    bollinger_bands,
)
from app.strategy_engine.indicators.calculations.keltner_channel import (
    keltner_channel,
)


def ttm_squeeze_pro(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    bb_period: int = 20,
    kc_period: int = 20,
    low_volatility_mult: float = 1.0,
    high_volatility_mult: float = 2.0,
) -> list[float | None]:
    """0..3 graded-squeeze line."""
    if not isinstance(bb_period, int) or isinstance(bb_period, bool) or bb_period < 2:
        raise ValueError(f"bb_period must be int >= 2; got {bb_period!r}.")
    if not isinstance(kc_period, int) or isinstance(kc_period, bool) or kc_period < 2:
        raise ValueError(f"kc_period must be int >= 2; got {kc_period!r}.")
    if low_volatility_mult <= 0 or high_volatility_mult <= 0:
        raise ValueError("KC multipliers must be > 0.")
    if low_volatility_mult >= high_volatility_mult:
        raise ValueError(
            f"low_volatility_mult must be < high_volatility_mult; "
            f"got {low_volatility_mult!r} >= {high_volatility_mult!r}."
        )
    n = len(closes)
    if n != len(highs) or n != len(lows):
        raise ValueError(
            f"highs/lows/closes must match in length; "
            f"got {len(highs)}, {len(lows)}, {n}."
        )
    if n == 0:
        return []

    mid_mult = (low_volatility_mult + high_volatility_mult) / 2.0

    bb_u, _bb_m, bb_l = bollinger_bands(closes, bb_period, 2.0)
    kc_low_u, _, kc_low_l = keltner_channel(highs, lows, closes, kc_period, low_volatility_mult)
    kc_mid_u, _, kc_mid_l = keltner_channel(highs, lows, closes, kc_period, mid_mult)
    kc_high_u, _, kc_high_l = keltner_channel(highs, lows, closes, kc_period, high_volatility_mult)
    if not bb_u or not kc_low_u or not kc_mid_u or not kc_high_u:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        bu = bb_u[i]
        bl = bb_l[i]
        klu = kc_low_u[i]
        kll = kc_low_l[i]
        kmu = kc_mid_u[i]
        kml = kc_mid_l[i]
        khu = kc_high_u[i]
        khl = kc_high_l[i]
        if (
            bu is None or bl is None
            or klu is None or kll is None
            or kmu is None or kml is None
            or khu is None or khl is None
        ):
            continue
        if bu < klu and bl > kll:
            out[i] = 3.0
        elif bu < kmu and bl > kml:
            out[i] = 2.0
        elif bu < khu and bl > khl:
            out[i] = 1.0
        else:
            out[i] = 0.0
    return out


__all__ = ["ttm_squeeze_pro"]
