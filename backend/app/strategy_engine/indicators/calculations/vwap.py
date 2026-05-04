"""Volume Weighted Average Price — cumulative typical-price weighted by volume.

Definition (cumulative from the start of the input window):

    typical[i]    = (high[i] + low[i] + close[i]) / 3
    cum_pv[i]     = sum_{k=0..i} typical[k] * volume[k]
    cum_vol[i]    = sum_{k=0..i} volume[k]
    VWAP[i]       = cum_pv[i] / cum_vol[i]   when cum_vol[i] > 0
                  = None                      otherwise

Notes:
    * Phase 1 implements **anchored-at-start** VWAP. Session-anchored
      (intraday reset) VWAP is a Phase 2/3 concern when the backtest
      engine has access to bar timestamps; the calculation here keeps
      the registry's Phase 1 contract simple.
    * Output length equals input length. Bars where cumulative volume is
      still zero (a sequence of zero-volume bars at the start) are
      ``None`` — defined-once, defined-forever after the first non-zero
      volume.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Mismatched input lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def vwap(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
) -> list[float | None]:
    """Cumulative VWAP over the input window."""
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(volumes):
        raise ValueError(
            "highs, lows, closes, volumes must have the same length; got "
            f"{n}, {len(lows)}, {len(closes)}, {len(volumes)}."
        )
    if n == 0:
        return []

    out: list[float | None] = []
    cum_pv = 0.0
    cum_vol = 0.0
    for i in range(n):
        typical = (highs[i] + lows[i] + closes[i]) / 3
        cum_pv += typical * volumes[i]
        cum_vol += volumes[i]
        if cum_vol > 0:
            out.append(cum_pv / cum_vol)
        else:
            out.append(None)
    return out


__all__ = ["vwap"]
