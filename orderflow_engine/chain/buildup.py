"""Price × OI buildup matrix (Module R5).

Classic 4-way classification over a window, per instrument:

    price up   + OI up    -> long_buildup
    price down + OI up    -> short_buildup
    price up   + OI down  -> short_covering
    price down + OI down  -> long_unwinding
    (either flat)         -> neutral

The LABEL is descriptive (functional, sign-based). A ``significant`` flag only
fires when BOTH moves exceed their magnitude thresholds — INERT at 0 (so the flag
is off until calibrated), per doctrine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Buildup:
    label: str
    price_change_pct: float
    oi_change_pct: float
    significant: bool


def classify_buildup(price_start: float, price_end: float,
                     oi_start: int, oi_end: int,
                     price_threshold_pct: float = 0.0,
                     oi_threshold_pct: float = 0.0) -> Buildup:
    dp = ((price_end - price_start) / price_start * 100.0) if price_start else 0.0
    doi = ((oi_end - oi_start) / oi_start * 100.0) if oi_start else 0.0
    if dp > 0 and doi > 0:
        label = "long_buildup"
    elif dp < 0 and doi > 0:
        label = "short_buildup"
    elif dp > 0 and doi < 0:
        label = "short_covering"
    elif dp < 0 and doi < 0:
        label = "long_unwinding"
    else:
        label = "neutral"
    # significance gate: INERT unless BOTH thresholds are set (>0)
    significant = (price_threshold_pct > 0 and oi_threshold_pct > 0
                   and abs(dp) >= price_threshold_pct and abs(doi) >= oi_threshold_pct)
    return Buildup(label, round(dp, 4), round(doi, 4), significant)
