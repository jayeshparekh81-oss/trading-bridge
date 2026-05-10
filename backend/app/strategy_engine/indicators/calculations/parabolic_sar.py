"""Parabolic SAR (Wilder, 1978).

Single-line trend-following indicator. Output dot stays below price
during an uptrend and above price during a downtrend; SAR flips
when price crosses it.

Definition (Wilder's original; matches the standard Pine ``ta.sar``):

    Initialise with the first two bars to determine direction:
        if close[1] >= close[0] -> long (EP=high[1], SAR=low[0])
        else                    -> short (EP=low[1], SAR=high[0])

    On each subsequent bar:
        SAR_new = SAR + AF * (EP - SAR)

    Long branch:
        SAR_new = min(SAR_new, low[i - 1], low[i - 2 if i >= 2 else 0])
        if low[i] < SAR_new -> flip short, AF reset, SAR = max EP so far
        else if high[i] > EP -> EP = high[i], AF = min(AF + step, max_step)

    Short branch (mirror): cap SAR at the max of the prior two highs;
    flip if high crosses SAR; track lows for EP.

Output length equals input length; bar 0 is ``None`` (no SAR seed
without a directional cue).

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Single bar -> ``[None]``.
    * Mismatched input lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def parabolic_sar(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    step: float = 0.02,
    max_step: float = 0.2,
) -> list[float | None]:
    """Parabolic SAR with acceleration factor ``step``, capped at ``max_step``."""
    if step <= 0 or max_step <= 0 or step > max_step:
        raise ValueError(
            f"need 0 < step <= max_step; got step={step!r}, max_step={max_step!r}."
        )
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return []
    if n == 1:
        return [None]

    out: list[float | None] = [None] * n
    long_trend = closes[1] >= closes[0]
    if long_trend:
        sar = lows[0]
        ep = highs[1]
    else:
        sar = highs[0]
        ep = lows[1]
    af = step
    out[1] = sar

    for i in range(2, n):
        sar = sar + af * (ep - sar)
        if long_trend:
            sar = min(sar, lows[i - 1], lows[i - 2])
            if lows[i] < sar:
                long_trend = False
                sar = ep
                ep = lows[i]
                af = step
            else:
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + step, max_step)
        else:
            sar = max(sar, highs[i - 1], highs[i - 2])
            if highs[i] > sar:
                long_trend = True
                sar = ep
                ep = highs[i]
                af = step
            else:
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + step, max_step)
        out[i] = sar
    return out


__all__ = ["parabolic_sar"]
