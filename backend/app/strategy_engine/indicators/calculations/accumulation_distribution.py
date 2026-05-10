"""Accumulation / Distribution Line (Marc Chaikin, 1970s).

Definition::

    MFM[i] = ((close - low) - (high - close)) / (high - low)   # 0 if H==L
    MFV[i] = MFM[i] * volume[i]
    AD[i]  = AD[i - 1] + MFV[i]                                # cumulative

The line is a running total — there is no rolling window and no
warm-up gap. ``AD[0]`` is just ``MFV[0]``; subsequent bars add
their MFV to the prior total. Pine equivalent is ``ta.accdist``.

Output length equals input length. No ``None`` warm-up; the first
bar carries its own MFV.

Edge cases per Phase 1 contract:
    * Empty input or mismatched lengths -> ``[]`` / ``ValueError``.
    * Flat bar (high == low) contributes 0 to MFV (no flow signal).
"""

from __future__ import annotations

from collections.abc import Sequence


def accumulation_distribution(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
) -> list[float | None]:
    """Cumulative A/D line — no parameters."""
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(volumes):
        raise ValueError(
            "highs, lows, closes, volumes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(volumes)}."
        )
    if n == 0:
        return []

    out: list[float | None] = [0.0] * n
    running = 0.0
    for i in range(n):
        rng = highs[i] - lows[i]
        if rng == 0:
            mfv = 0.0
        else:
            mfm = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / rng
            mfv = mfm * volumes[i]
        running += mfv
        out[i] = running
    return out


__all__ = ["accumulation_distribution"]
