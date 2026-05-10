"""Fear & Greed Index — single-symbol composite proxy.

CNN's market-wide F&G uses 7 inputs (put/call ratio, VIX,
junk-bond demand, market momentum, market volatility, stock
price strength, stock price breadth). At the single-symbol
calc-layer abstraction we don't have most of those — this is
an honest 3-factor composite from data we DO have:

    momentum (40 %)   — RSI distance from 50, mapped to 0-100
    volatility (30 %) — ATR-percent inverted (low vol = greed)
    flow (30 %)       — OBV slope sign

Output is in ``[0, 100]``. 0 = extreme fear, 100 = extreme
greed. The CNN-headline reading is a market-wide aggregate;
this is a per-symbol approximation useful as a regime filter on
the symbol you're trading.

Default ``lookback = 30`` (used for OBV slope window). Other
internals use their own conventional periods (RSI 14, ATR 14).

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``lookback >= n`` -> ``[]``.
    * Underlying RSI / ATR / OBV warmups all need to land before
      the composite has a value.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr_percent import atr_percent
from app.strategy_engine.indicators.calculations.obv import obv
from app.strategy_engine.indicators.calculations.rsi import rsi


def fear_greed_index(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    lookback: int = 30,
) -> list[float | None]:
    """3-factor composite F&G index in ``[0, 100]``."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 5:
        raise ValueError(f"lookback must be an int >= 5; got {lookback!r}.")
    n = len(closes)
    if n != len(highs) or n != len(lows) or n != len(volumes):
        raise ValueError(
            f"highs, lows, closes, volumes must have the same length; "
            f"got {len(highs)}, {len(lows)}, {n}, {len(volumes)}."
        )
    if n == 0 or lookback >= n:
        return []

    rsi_series = rsi(list(closes), 14)
    atr_pct = atr_percent(highs, lows, closes, 14)
    obv_line = obv(list(closes), list(volumes))
    if not rsi_series or not atr_pct or not obv_line:
        return [None] * n

    out: list[float | None] = [None] * n
    # Cache the rolling-window ATR distribution for the
    # "volatility percentile" component: where does today's ATR-pct
    # sit in the trailing distribution? Low percentile = greed.
    for i in range(lookback, n):
        r = rsi_series[i]
        ap = atr_pct[i]
        if r is None or ap is None:
            continue

        # Momentum (40%): RSI mapped 0..100 directly.
        momentum_score = r

        # Volatility (30%): inverted percentile of ATR-pct in the
        # trailing window. Low vol = greed (high score).
        window_atr = [v for v in atr_pct[i - lookback : i + 1] if v is not None]
        if len(window_atr) < lookback // 2:
            continue
        sorted_atr = sorted(window_atr)
        # Find the count of values >= current; convert to percentile.
        rank = sum(1 for v in sorted_atr if v <= ap)
        percentile = (rank / len(sorted_atr)) * 100.0
        volatility_score = 100.0 - percentile  # invert: low vol → high greed

        # Flow (30%): OBV slope sign over the lookback window.
        obv_now = obv_line[i]
        obv_then = obv_line[i - lookback]
        if obv_now is None or obv_then is None:
            continue
        # Positive slope → greed (100); negative → fear (0); flat → 50.
        if obv_now > obv_then:
            flow_score = 100.0
        elif obv_now < obv_then:
            flow_score = 0.0
        else:
            flow_score = 50.0

        composite = (
            0.40 * momentum_score
            + 0.30 * volatility_score
            + 0.30 * flow_score
        )
        # Clamp into [0, 100] (defensive — components are bounded
        # individually but compositing rounding could nudge).
        out[i] = max(0.0, min(100.0, composite))
    return out


__all__ = ["fear_greed_index"]
