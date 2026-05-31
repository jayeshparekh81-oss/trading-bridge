"""Sprint 5a — triangulate Aroon + CMO conventions against TRADETRI.

For each of the 5 unresolved D-tier indicators write 3 candidate
hand-rolled refs (different conventions) and compare against TRADETRI.
The closest match identifies which convention TRADETRI implements; if
no convention matches within tolerance, the indicator is flagged as
REAL_MATH_BUG.

Per spec: triangulation only. ZERO indicator math touched.
"""

from __future__ import annotations

from collections.abc import Sequence


# ─── Aroon — 3 candidate conventions ──────────────────────────────


def aroon_conv_first(highs: Sequence[float], lows: Sequence[float],
                     period: int) -> tuple[list, list, list]:
    """Convention 1 (TRADETRI claim): window = period+1 bars,
    argmax = FIRST occurrence (oldest extreme wins on tie)."""
    n = len(highs)
    up = [None] * n; down = [None] * n; osc = [None] * n
    if period >= n: return up, down, osc
    for i in range(period, n):
        wh = highs[i - period : i + 1]
        wl = lows[i - period : i + 1]
        # First occurrence
        best_h = 0
        for k in range(1, len(wh)):
            if wh[k] > wh[best_h]: best_h = k
        best_l = 0
        for k in range(1, len(wl)):
            if wl[k] < wl[best_l]: best_l = k
        bars_since_high = period - best_h
        bars_since_low = period - best_l
        up_v = 100.0 * (period - bars_since_high) / period
        dn_v = 100.0 * (period - bars_since_low) / period
        up[i] = up_v; down[i] = dn_v; osc[i] = up_v - dn_v
    return up, down, osc


def aroon_conv_last(highs: Sequence[float], lows: Sequence[float],
                    period: int) -> tuple[list, list, list]:
    """Convention 2 (talib-style): window = period+1 bars,
    argmax = LAST occurrence (most recent extreme wins on tie)."""
    n = len(highs)
    up = [None] * n; down = [None] * n; osc = [None] * n
    if period >= n: return up, down, osc
    for i in range(period, n):
        wh = highs[i - period : i + 1]
        wl = lows[i - period : i + 1]
        # Last occurrence — search from end
        best_h = len(wh) - 1
        for k in range(len(wh) - 2, -1, -1):
            if wh[k] > wh[best_h]: best_h = k
        best_l = len(wl) - 1
        for k in range(len(wl) - 2, -1, -1):
            if wl[k] < wl[best_l]: best_l = k
        bars_since_high = period - best_h
        bars_since_low = period - best_l
        up_v = 100.0 * (period - bars_since_high) / period
        dn_v = 100.0 * (period - bars_since_low) / period
        up[i] = up_v; down[i] = dn_v; osc[i] = up_v - dn_v
    return up, down, osc


def aroon_conv_window_n(highs: Sequence[float], lows: Sequence[float],
                        period: int) -> tuple[list, list, list]:
    """Convention 3: window = period bars (NOT period+1). Some
    implementations interpret 'last n bars' as a flat n-bar window."""
    n = len(highs)
    up = [None] * n; down = [None] * n; osc = [None] * n
    if period > n: return up, down, osc
    for i in range(period - 1, n):
        wh = highs[i - period + 1 : i + 1]
        wl = lows[i - period + 1 : i + 1]
        best_h = 0
        for k in range(1, len(wh)):
            if wh[k] > wh[best_h]: best_h = k
        best_l = 0
        for k in range(1, len(wl)):
            if wl[k] < wl[best_l]: best_l = k
        bars_since_high = period - 1 - best_h
        bars_since_low = period - 1 - best_l
        up_v = 100.0 * (period - bars_since_high) / period
        dn_v = 100.0 * (period - bars_since_low) / period
        up[i] = up_v; down[i] = dn_v; osc[i] = up_v - dn_v
    return up, down, osc


# ─── CMO — 3 candidate conventions ────────────────────────────────


def cmo_conv_raw(values: Sequence[float], period: int) -> list:
    """Convention 1 (TRADETRI claim): raw sum of ups/downs over `period`
    bars, ratio = 100 * (sum_up - sum_down) / (sum_up + sum_down)."""
    n = len(values)
    out = [None] * n
    if period >= n: return out
    ups = [0.0] * n; downs = [0.0] * n
    for i in range(1, n):
        d = values[i] - values[i - 1]
        if d > 0: ups[i] = d
        elif d < 0: downs[i] = -d
    for i in range(period, n):
        su = sum(ups[i - period + 1 : i + 1])
        sd = sum(downs[i - period + 1 : i + 1])
        if su + sd > 0:
            out[i] = 100.0 * (su - sd) / (su + sd)
    return out


def cmo_conv_wilder(values: Sequence[float], period: int) -> list:
    """Convention 2 (talib.CMO style): Wilder-smoothed up/down sums.

    Talib's CMO seeds at index `period` with the simple sum of the first
    `period` diffs, then recurses:
        smooth_up[i] = (smooth_up[i-1] * (period-1) + up[i]) / period
        smooth_down[i] = ... same shape ...
        CMO[i] = 100 * (smooth_up - smooth_down) / (smooth_up + smooth_down)

    Note: many sources state talib doesn't smooth — it just sums. But
    empirically talib.CMO matches RSI's Wilder-smoothing pattern.
    """
    n = len(values)
    out = [None] * n
    if period >= n: return out
    ups = [0.0] * n; downs = [0.0] * n
    for i in range(1, n):
        d = values[i] - values[i - 1]
        if d > 0: ups[i] = d
        elif d < 0: downs[i] = -d
    # Seed with simple sum of first `period` diffs (indices 1..period)
    smooth_up = sum(ups[1 : period + 1]) / period
    smooth_dn = sum(downs[1 : period + 1]) / period
    denom = smooth_up + smooth_dn
    if denom > 0:
        out[period] = 100.0 * (smooth_up - smooth_dn) / denom
    for i in range(period + 1, n):
        smooth_up = (smooth_up * (period - 1) + ups[i]) / period
        smooth_dn = (smooth_dn * (period - 1) + downs[i]) / period
        denom = smooth_up + smooth_dn
        if denom > 0:
            out[i] = 100.0 * (smooth_up - smooth_dn) / denom
    return out


def cmo_conv_raw_lagged(values: Sequence[float], period: int) -> list:
    """Convention 3: raw sums but window excludes current bar's diff
    (lagged by 1). Some sources define the window as ``i-period`` to
    ``i-1`` instead of ``i-period+1`` to ``i``."""
    n = len(values)
    out = [None] * n
    if period >= n: return out
    ups = [0.0] * n; downs = [0.0] * n
    for i in range(1, n):
        d = values[i] - values[i - 1]
        if d > 0: ups[i] = d
        elif d < 0: downs[i] = -d
    for i in range(period + 1, n):
        # window of `period` diffs ending at i-1 (exclude i)
        su = sum(ups[i - period : i])
        sd = sum(downs[i - period : i])
        if su + sd > 0:
            out[i] = 100.0 * (su - sd) / (su + sd)
    return out


AROON_CANDIDATES = {
    "conv1_first_occurrence_window_n_plus_1": aroon_conv_first,
    "conv2_last_occurrence_window_n_plus_1":  aroon_conv_last,
    "conv3_first_occurrence_window_n":         aroon_conv_window_n,
}

CMO_CANDIDATES = {
    "conv1_raw_sum_window_n":      cmo_conv_raw,
    "conv2_wilder_smoothed":        cmo_conv_wilder,
    "conv3_raw_sum_lagged_window":  cmo_conv_raw_lagged,
}


__all__ = ["AROON_CANDIDATES", "CMO_CANDIDATES"]
