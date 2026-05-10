"""Twiggs Money Flow (Colin Twiggs, 2000s).

Wilder's-smoothed variant of Chaikin Money Flow that uses *true*
high/low (incorporating prior close gaps) rather than raw high/low.
This makes the indicator more robust on opening gaps — a real-world
common case on Indian retail symbols.

Definition::

    TR_high = max(high[i], close[i - 1])
    TR_low  = min(low[i],  close[i - 1])
    range   = TR_high - TR_low                                 # 0 if flat
    MFM     = ((close[i] - TR_low) - (TR_high - close[i])) / range
    MFV     = MFM * volume[i]
    EMA_MFV = EMA(MFV, period)
    EMA_V   = EMA(volume, period)
    TMF[i]  = EMA_MFV[i] / EMA_V[i]

Default ``period = 21`` (Twiggs' original recommendation).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Flat bar -> contributes 0 to MFV that bar.
    * ``period >= n`` -> ``[]``.
    * ``EMA_V[i] == 0`` -> output is 0 that bar (no flow signal).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def twiggs_money_flow(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 21,
) -> list[float | None]:
    """Twiggs Money Flow over a rolling ``period``-bar window."""
    _check_period(period)
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(volumes):
        raise ValueError(
            "highs, lows, closes, volumes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(volumes)}."
        )
    if n == 0 or period >= n:
        return []

    mfv: list[float] = [0.0] * n
    for i in range(1, n):
        prev_close = closes[i - 1]
        tr_high = max(highs[i], prev_close)
        tr_low = min(lows[i], prev_close)
        rng = tr_high - tr_low
        if rng == 0:
            mfv[i] = 0.0
            continue
        mfm = ((closes[i] - tr_low) - (tr_high - closes[i])) / rng
        mfv[i] = mfm * volumes[i]

    ema_mfv = ema(mfv, period)
    ema_vol = ema(list(volumes), period)
    if not ema_mfv or not ema_vol:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        v = ema_vol[i]
        m = ema_mfv[i]
        if v is None or m is None:
            continue
        out[i] = 0.0 if v == 0 else m / v
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["twiggs_money_flow"]
