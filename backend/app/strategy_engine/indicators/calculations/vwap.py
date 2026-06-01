"""Volume Weighted Average Price — session-anchored when timestamps supplied.

Definition (per session, anchored at first bar of each IST trading day):

    typical[i]   = (high[i] + low[i] + close[i]) / 3
    cum_pv[i]    = sum over current session of typical[k] * volume[k]
    cum_vol[i]   = sum over current session of volume[k]
    VWAP[i]      = cum_pv[i] / cum_vol[i]   when cum_vol[i] > 0
                 = None                      otherwise

Session boundary detection (when ``timestamps`` is provided):
    A new session begins on the first bar whose IST calendar date
    differs from the prior bar's IST date. Accumulators reset to zero
    on that bar before consuming it. Naive timestamps are assumed to
    already be in IST.

NaN-volume handling:
    Bars whose volume is NaN are skipped — they do not poison
    ``cum_vol`` (the bug surfaced in QUEUE_VV_TRIPLE_IMPL_AUDIT §5).
    The output at a NaN-volume bar is the prior bar's VWAP (or ``None``
    if the session has no defined value yet).

Backward compatibility:
    Calling ``vwap(highs, lows, closes, volumes)`` without ``timestamps``
    preserves the legacy anchored-at-start cumulative behavior — every
    call site predating this fix continues to compile and run.

Edge cases:
    * Empty input -> ``[]``.
    * Mismatched OHLCV lengths -> ``ValueError``.
    * ``timestamps`` length mismatch -> ``ValueError``.
    * Output length always equals input length.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")


def _is_nan(value: float) -> bool:
    """True if ``value`` is a float NaN. Safe for ints (returns False)."""
    return isinstance(value, float) and math.isnan(value)


def vwap(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    timestamps: Sequence[datetime] | None = None,
) -> list[float | None]:
    """Session-anchored VWAP when ``timestamps`` provided; legacy cumulative
    behavior when ``timestamps`` is ``None``.
    """
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(volumes):
        raise ValueError(
            "highs, lows, closes, volumes must have the same length; got "
            f"{n}, {len(lows)}, {len(closes)}, {len(volumes)}."
        )
    if timestamps is not None and len(timestamps) != n:
        raise ValueError(
            f"timestamps length ({len(timestamps)}) must match OHLCV length ({n})."
        )
    if n == 0:
        return []

    out: list[float | None] = []
    cum_pv = 0.0
    cum_vol = 0.0
    prev_date = None
    for i in range(n):
        vol_i = volumes[i]
        if _is_nan(vol_i):
            out.append(out[-1] if out else None)
            continue

        if timestamps is not None:
            ts_i = timestamps[i]
            date_i = ts_i.date() if ts_i.tzinfo is None else ts_i.astimezone(_IST).date()
            if prev_date is not None and date_i != prev_date:
                cum_pv = 0.0
                cum_vol = 0.0
            prev_date = date_i

        typical = (highs[i] + lows[i] + closes[i]) / 3
        cum_pv += typical * vol_i
        cum_vol += vol_i
        if cum_vol > 0:
            out.append(cum_pv / cum_vol)
        else:
            out.append(None)
    return out


__all__ = ["vwap"]
