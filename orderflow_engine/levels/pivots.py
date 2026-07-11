"""Classic floor pivots (Module R4) — pure function of prior-day OHLC.

    P  = (H + L + C) / 3
    R1 = 2P - L      S1 = 2P - H
    R2 = P + (H - L) S2 = P - (H - L)
    R3 = H + 2(P - L) S3 = L - 2(H - P)
"""

from __future__ import annotations


def classic_pivots(high: float, low: float, close: float) -> dict:
    h, l, c = float(high), float(low), float(close)
    p = (h + l + c) / 3.0
    rng = h - l
    return {
        "PIVOT_P": p,
        "PIVOT_R1": 2 * p - l,
        "PIVOT_S1": 2 * p - h,
        "PIVOT_R2": p + rng,
        "PIVOT_S2": p - rng,
        "PIVOT_R3": h + 2 * (p - l),
        "PIVOT_S3": l - 2 * (h - p),
    }
