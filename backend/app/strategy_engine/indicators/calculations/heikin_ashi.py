"""Heikin-Ashi candle transform — Coming-Soon → Active promotion.

Smoothed candle representation. Each input OHLC bar is converted to a
Heikin-Ashi (HA) candle that averages the input bar with the prior
HA candle. Net effect: HA candles run a clean trend signal at the
cost of obscuring the true open / close.

Formulas (canonical TradingView Pine reference):

    ha_close[i] = (open[i] + high[i] + low[i] + close[i]) / 4

    ha_open[0]  = (open[0] + close[0]) / 2                     # seed
    ha_open[i]  = (ha_open[i-1] + ha_close[i-1]) / 2           # recursive

    ha_high[i]  = max(high[i], ha_open[i], ha_close[i])
    ha_low[i]   = min(low[i],  ha_open[i], ha_close[i])

Returns a list of dicts (one per input bar) with keys
``{"open", "high", "low", "close"}``. Empty input → ``[]``.

Edge cases:
    * Empty input -> ``[]``
    * Single bar  -> single output; seed formula is used so HA candle
      is well-defined even with one input bar
    * Mismatched OHLC length -> ``ValueError``
"""

from __future__ import annotations

from collections.abc import Sequence


def heikin_ashi(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[dict[str, float] | None]:
    """Return HA candles for the input OHLC series.

    Each output element is a dict ``{"open", "high", "low", "close"}``
    or ``None`` if computation isn't possible (only happens for
    incomplete inputs).
    """
    n = len(opens)
    if not (len(highs) == len(lows) == len(closes) == n):
        raise ValueError(
            f"OHLC series length mismatch: open={n}, high={len(highs)}, "
            f"low={len(lows)}, close={len(closes)}."
        )
    if n == 0:
        return []

    out: list[dict[str, float] | None] = []
    # Seed: HA open at index 0 uses the input's own (open + close) / 2.
    ha_open_prev: float = (opens[0] + closes[0]) / 2.0
    ha_close_prev: float = (opens[0] + highs[0] + lows[0] + closes[0]) / 4.0

    for i in range(n):
        ha_close = (opens[i] + highs[i] + lows[i] + closes[i]) / 4.0
        if i == 0:
            ha_open = ha_open_prev
        else:
            ha_open = (ha_open_prev + ha_close_prev) / 2.0
        ha_high = max(highs[i], ha_open, ha_close)
        ha_low = min(lows[i], ha_open, ha_close)
        out.append(
            {
                "open": ha_open,
                "high": ha_high,
                "low": ha_low,
                "close": ha_close,
            }
        )
        ha_open_prev = ha_open
        ha_close_prev = ha_close
    return out


__all__ = ["heikin_ashi"]
