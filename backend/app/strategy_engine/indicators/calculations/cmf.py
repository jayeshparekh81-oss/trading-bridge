"""Chaikin Money Flow (Chaikin, 1980s).

Definition::

    MFM[i] = ((close - low) - (high - close)) / (high - low)         # money flow multiplier
                                                                      # 0 if high == low (flat bar)
    MFV[i] = MFM[i] * volume[i]                                       # money flow volume
    CMF    = sum(MFV over period) / sum(volume over period)

The multiplier ranges -1 (close at low) to +1 (close at high). CMF
itself ranges roughly -1 to +1; values consistently above zero indicate
buying pressure, below zero selling pressure.

Output length equals input length. Indices ``0 .. period - 2`` are
``None``; from ``period - 1`` onward the value is filled in.

Edge cases per Phase 1 contract:
    * Empty input or mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > len(highs)`` -> ``[]``.
    * ``sum(volume_window) == 0`` -> the bar's CMF is 0 (no flow).
"""

from __future__ import annotations

from collections.abc import Sequence


def cmf(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Chaikin Money Flow over a rolling ``period``-bar window."""
    _check_period(period)
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(volumes):
        raise ValueError(
            "highs, lows, closes, volumes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(volumes)}."
        )
    if n == 0 or period > n:
        return []

    mfv = [0.0] * n
    for i in range(n):
        rng = highs[i] - lows[i]
        if rng == 0:
            mfv[i] = 0.0
        else:
            mfm = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / rng
            mfv[i] = mfm * volumes[i]

    out: list[float | None] = [None] * (period - 1)
    for i in range(period - 1, n):
        v_sum = sum(volumes[i - period + 1 : i + 1])
        m_sum = sum(mfv[i - period + 1 : i + 1])
        out.append(0.0 if v_sum == 0 else m_sum / v_sum)
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["cmf"]
