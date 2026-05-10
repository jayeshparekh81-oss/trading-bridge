"""Money Flow Index.

Volume-weighted RSI variant. Definition (matches Pine ``ta.mfi``):

    TP[i]     = (high[i] + low[i] + close[i]) / 3
    MF[i]     = TP[i] * volume[i]

    Positive MF = MF[i] when TP[i] > TP[i - 1] else 0
    Negative MF = MF[i] when TP[i] < TP[i - 1] else 0

    Sum positive / negative MF over the last ``period`` bars.

    MFR[i] = sum_pos / sum_neg
    MFI[i] = 100 - 100 / (1 + MFR[i])

Output range is ``[0, 100]``. Readings > 80 / < 20 commonly flag
overbought / oversold with a volume confirmation.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period >= len(values)`` -> ``[]``.
    * ``sum_neg == 0`` (all up bars in window) -> 100.0.
    * ``sum_pos == 0`` (all down bars in window) -> 0.0.
"""

from __future__ import annotations

from collections.abc import Sequence


def mfi(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Money Flow Index over ``period`` bars."""
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(highs)
    if not (n == len(lows) == len(closes) == len(volumes)):
        raise ValueError(
            f"highs, lows, closes, volumes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(volumes)}."
        )
    if n == 0 or period >= n:
        return []

    tp = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(n)]
    pos_mf = [0.0] * n
    neg_mf = [0.0] * n
    for i in range(1, n):
        flow = tp[i] * volumes[i]
        if tp[i] > tp[i - 1]:
            pos_mf[i] = flow
        elif tp[i] < tp[i - 1]:
            neg_mf[i] = flow

    out: list[float | None] = [None] * n
    for i in range(period, n):
        sum_pos = sum(pos_mf[i - period + 1 : i + 1])
        sum_neg = sum(neg_mf[i - period + 1 : i + 1])
        if sum_neg == 0.0:
            out[i] = 100.0
        elif sum_pos == 0.0:
            out[i] = 0.0
        else:
            mfr = sum_pos / sum_neg
            out[i] = 100.0 - 100.0 / (1.0 + mfr)
    return out


__all__ = ["mfi"]
