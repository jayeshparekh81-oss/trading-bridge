"""Sprint 4d — hand-rolled reference implementations for 30 custom indicators.

Each handroll is the canonical closed-form formula matching Pine docs / TA
textbook definitions. ~5-15 LOC per indicator. Used as the reference
oracle in `verify_handroll()` against the TRADETRI impl.

Per spec: handrolls are mathematical REFERENCES, not fixes. TRADETRI's
indicator math is never touched.

Selection criteria (priority order):
    1. Active-template referenced (9): supertrend, inside_bar,
       bullish_engulfing, doji, cmf, hull_ma, heikin_ashi,
       camarilla_pivots, pivot_swing
    2. Common candlestick patterns (additional ~10)
    3. Trend / volatility customs (~5)
    4. Pivots (~4)
    5. Custom oscillators (~2)

Total: 30.
"""

from __future__ import annotations

import math
from typing import Sequence


# ─── Candlestick patterns (boolean / score outputs) ────────────────


def hr_inside_bar(o, h, l, c) -> list[float | None]:
    """Inside Bar: current high/low entirely within prior bar's range."""
    out = [None]
    for i in range(1, len(o)):
        out.append(1.0 if (h[i] < h[i-1] and l[i] > l[i-1]) else 0.0)
    return out


def hr_bullish_engulfing(o, h, l, c) -> list[float | None]:
    """Bullish Engulfing: bearish prior + bullish current that engulfs body."""
    out = [None]
    for i in range(1, len(o)):
        prior_bear = c[i-1] < o[i-1]
        cur_bull = c[i] > o[i]
        engulf = o[i] < c[i-1] and c[i] > o[i-1]
        out.append(1.0 if (prior_bear and cur_bull and engulf) else 0.0)
    return out


def hr_bearish_engulfing(o, h, l, c) -> list[float | None]:
    out = [None]
    for i in range(1, len(o)):
        prior_bull = c[i-1] > o[i-1]
        cur_bear = c[i] < o[i]
        engulf = o[i] > c[i-1] and c[i] < o[i-1]
        out.append(1.0 if (prior_bull and cur_bear and engulf) else 0.0)
    return out


def hr_doji(o, h, l, c, threshold_pct: float = 0.1) -> list[float | None]:
    """Doji: body/range ratio below threshold (default 10%)."""
    out = []
    for i in range(len(o)):
        rng = h[i] - l[i]
        body = abs(c[i] - o[i])
        out.append(1.0 if (rng > 0 and (body / rng) < threshold_pct) else 0.0)
    return out


def hr_hammer(o, h, l, c) -> list[float | None]:
    """Hammer: small body in upper third + long lower wick."""
    out = []
    for i in range(len(o)):
        rng = h[i] - l[i]
        body = abs(c[i] - o[i])
        body_top = max(o[i], c[i])
        body_bottom = min(o[i], c[i])
        upper_wick = h[i] - body_top
        lower_wick = body_bottom - l[i]
        ok = rng > 0 and (body / rng < 0.33) and (lower_wick >= 2 * body) and (upper_wick < body)
        out.append(1.0 if ok else 0.0)
    return out


def hr_shooting_star(o, h, l, c) -> list[float | None]:
    """Shooting Star: small body in lower third + long upper wick."""
    out = []
    for i in range(len(o)):
        rng = h[i] - l[i]
        body = abs(c[i] - o[i])
        body_top = max(o[i], c[i])
        body_bottom = min(o[i], c[i])
        upper_wick = h[i] - body_top
        lower_wick = body_bottom - l[i]
        ok = rng > 0 and (body / rng < 0.33) and (upper_wick >= 2 * body) and (lower_wick < body)
        out.append(1.0 if ok else 0.0)
    return out


def hr_hanging_man(o, h, l, c) -> list[float | None]:
    """Hanging Man: same shape as hammer but appears at uptrend top."""
    # Without trend context, identical shape detection to hammer.
    return hr_hammer(o, h, l, c)


def hr_spinning_top(o, h, l, c) -> list[float | None]:
    """Spinning Top: small body, wicks on both sides."""
    out = []
    for i in range(len(o)):
        rng = h[i] - l[i]
        body = abs(c[i] - o[i])
        body_top = max(o[i], c[i])
        body_bottom = min(o[i], c[i])
        upper_wick = h[i] - body_top
        lower_wick = body_bottom - l[i]
        ok = rng > 0 and (body / rng < 0.33) and upper_wick > body and lower_wick > body
        out.append(1.0 if ok else 0.0)
    return out


def hr_marubozu(o, h, l, c, threshold_pct: float = 0.05) -> list[float | None]:
    """Marubozu: body fills almost entire range (wicks < 5%)."""
    out = []
    for i in range(len(o)):
        rng = h[i] - l[i]
        body = abs(c[i] - o[i])
        ok = rng > 0 and (body / rng) > (1 - 2*threshold_pct)
        out.append(1.0 if ok else 0.0)
    return out


# ─── Trend / MA customs ────────────────────────────────────────────


def hr_hull_ma(values: Sequence[float], period: int = 20) -> list[float | None]:
    """Hull MA = WMA(2*WMA(half) - WMA(full), sqrt(period)).

    Implementation per Pine docs reference.
    """
    def wma(vals, p):
        out = [None]*len(vals)
        denom = p*(p+1)/2
        for i in range(p-1, len(vals)):
            s = sum((j+1) * vals[i-p+1+j] for j in range(p))
            out[i] = s / denom
        return out

    half = max(2, period // 2)
    sqrt_p = max(2, int(math.sqrt(period)))
    wma_half = wma(values, half)
    wma_full = wma(values, period)
    raw = []
    for i in range(len(values)):
        if wma_half[i] is None or wma_full[i] is None:
            raw.append(None)
        else:
            raw.append(2 * wma_half[i] - wma_full[i])
    # WMA over raw (skip Nones — apply only when window is fully defined)
    out = [None]*len(values)
    for i in range(len(values)):
        window = raw[i-sqrt_p+1:i+1] if i >= sqrt_p-1 else []
        if len(window) == sqrt_p and all(v is not None for v in window):
            denom = sqrt_p*(sqrt_p+1)/2
            s = sum((j+1) * window[j] for j in range(sqrt_p))
            out[i] = s / denom
    return out


def hr_heikin_ashi_close(o, h, l, c) -> list[float | None]:
    """Heikin Ashi close = (O+H+L+C)/4 — simplest line."""
    return [(o[i] + h[i] + l[i] + c[i]) / 4 for i in range(len(o))]


def hr_supertrend(h, l, c, atr_period: int = 10, multiplier: float = 3.0) -> list[float | None]:
    """Supertrend = midpoint ± multiplier × ATR, then directional flip logic."""
    n = len(c)
    # Compute ATR (Wilder's smoothing)
    tr = [0.0]*n
    for i in range(n):
        if i == 0:
            tr[i] = h[i] - l[i]
        else:
            tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    atr = [None]*n
    if atr_period <= n:
        atr[atr_period-1] = sum(tr[:atr_period]) / atr_period
        for i in range(atr_period, n):
            atr[i] = (atr[i-1] * (atr_period-1) + tr[i]) / atr_period
    # Supertrend bands + flip logic
    st = [None]*n
    direction = 1  # 1 up, -1 down
    for i in range(atr_period-1, n):
        mid = (h[i] + l[i]) / 2
        upper = mid + multiplier * atr[i]
        lower = mid - multiplier * atr[i]
        if i == atr_period-1:
            st[i] = lower if direction == 1 else upper
            continue
        # Trailing band logic
        if direction == 1:
            if c[i] < st[i-1]:
                direction = -1
                st[i] = upper
            else:
                st[i] = max(lower, st[i-1])
        else:
            if c[i] > st[i-1]:
                direction = 1
                st[i] = lower
            else:
                st[i] = min(upper, st[i-1])
    return st


def hr_choppiness_index(h, l, c, period: int = 14) -> list[float | None]:
    """Choppiness Index: 100 * log10(sum_ATR / (max-min)) / log10(period)."""
    n = len(c)
    tr = [0.0]*n
    for i in range(n):
        if i == 0:
            tr[i] = h[i] - l[i]
        else:
            tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    out = [None]*n
    log_p = math.log10(period)
    for i in range(period-1, n):
        sum_tr = sum(tr[i-period+1:i+1])
        hh = max(h[i-period+1:i+1])
        ll = min(l[i-period+1:i+1])
        if hh > ll and sum_tr > 0:
            out[i] = 100 * math.log10(sum_tr / (hh - ll)) / log_p
    return out


# ─── Volume / flow customs ─────────────────────────────────────────


def hr_cmf(h, l, c, v, period: int = 20) -> list[float | None]:
    """Chaikin Money Flow = SMA(MFM × volume) / SMA(volume) over period.

    MFM = ((C - L) - (H - C)) / (H - L), 0 if H == L.
    """
    n = len(c)
    mfv = [0.0]*n
    for i in range(n):
        rng = h[i] - l[i]
        if rng > 0:
            mfm = ((c[i] - l[i]) - (h[i] - c[i])) / rng
            mfv[i] = mfm * v[i]
    out = [None]*n
    for i in range(period-1, n):
        sum_mfv = sum(mfv[i-period+1:i+1])
        sum_v = sum(v[i-period+1:i+1])
        if sum_v > 0:
            out[i] = sum_mfv / sum_v
    return out


def hr_accumulation_distribution(h, l, c, v) -> list[float | None]:
    """Running cumulative MFM × volume (no window)."""
    n = len(c)
    out = []
    cum = 0.0
    for i in range(n):
        rng = h[i] - l[i]
        if rng > 0:
            mfm = ((c[i] - l[i]) - (h[i] - c[i])) / rng
            cum += mfm * v[i]
        out.append(cum)
    return out


def hr_money_flow_volume(h, l, c, v) -> list[float | None]:
    """Bar-by-bar money flow volume — same as MFM × volume without cumulation."""
    out = []
    for i in range(len(c)):
        rng = h[i] - l[i]
        if rng > 0:
            mfm = ((c[i] - l[i]) - (h[i] - c[i])) / rng
            out.append(mfm * v[i])
        else:
            out.append(0.0)
    return out


# ─── Pivots (intraday/daily reference points) ──────────────────────


def hr_camarilla_pivots_h3(h, l, c) -> list[float | None]:
    """Camarilla H3 = C + (H - L) * 1.1 / 4 — the breakout resistance."""
    out = [None]
    for i in range(1, len(c)):
        out.append(c[i-1] + (h[i-1] - l[i-1]) * 1.1 / 4)
    return out


def hr_classic_pivot(h, l, c) -> list[float | None]:
    """Classic pivot = (H + L + C) / 3 from prior bar."""
    out = [None]
    for i in range(1, len(c)):
        out.append((h[i-1] + l[i-1] + c[i-1]) / 3)
    return out


def hr_fibonacci_pivot_r1(h, l, c) -> list[float | None]:
    """Fibonacci R1 = pivot + 0.382 * (H - L)."""
    out = [None]
    for i in range(1, len(c)):
        p = (h[i-1] + l[i-1] + c[i-1]) / 3
        out.append(p + 0.382 * (h[i-1] - l[i-1]))
    return out


def hr_central_pivot_range_width(h, l, c) -> list[float | None]:
    """CPR width = |TC - BC| where TC = (P + H - L)/2, BC = (P - H + L)/2."""
    out = [None]
    for i in range(1, len(c)):
        p = (h[i-1] + l[i-1] + c[i-1]) / 3
        tc = (p + h[i-1] - l[i-1]) / 2
        bc = (p - h[i-1] + l[i-1]) / 2
        out.append(abs(tc - bc))
    return out


def hr_woodies_pivot(h, l, c, o) -> list[float | None]:
    """Woodie's pivot = (H + L + 2*C) / 4."""
    out = [None]
    for i in range(1, len(c)):
        out.append((h[i-1] + l[i-1] + 2*c[i-1]) / 4)
    return out


# ─── Custom oscillators / volatility ───────────────────────────────


def hr_bollinger_percent_b(values, period: int = 20, mult: float = 2.0) -> list[float | None]:
    """%B = (price - lower) / (upper - lower), where upper/lower = SMA ± mult*stddev."""
    out = [None]*len(values)
    for i in range(period-1, len(values)):
        window = values[i-period+1:i+1]
        mean = sum(window) / period
        var = sum((v - mean) ** 2 for v in window) / period
        std = math.sqrt(var)
        upper = mean + mult * std
        lower = mean - mult * std
        if upper > lower:
            out[i] = (values[i] - lower) / (upper - lower)
    return out


def hr_bollinger_bandwidth(values, period: int = 20, mult: float = 2.0) -> list[float | None]:
    """Bandwidth = (upper - lower) / middle."""
    out = [None]*len(values)
    for i in range(period-1, len(values)):
        window = values[i-period+1:i+1]
        mean = sum(window) / period
        var = sum((v - mean) ** 2 for v in window) / period
        std = math.sqrt(var)
        upper = mean + mult * std
        lower = mean - mult * std
        if mean > 0:
            out[i] = (upper - lower) / mean
    return out


def hr_atr_percent(h, l, c, period: int = 14) -> list[float | None]:
    """ATR / close * 100 — Wilder-smoothed."""
    n = len(c)
    tr = [0.0]*n
    for i in range(n):
        if i == 0:
            tr[i] = h[i] - l[i]
        else:
            tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    out = [None]*n
    if period > n:
        return out
    atr = sum(tr[:period]) / period
    out[period-1] = (atr / c[period-1]) * 100 if c[period-1] != 0 else None
    for i in range(period, n):
        atr = (atr * (period-1) + tr[i]) / period
        out[i] = (atr / c[i]) * 100 if c[i] != 0 else None
    return out


def hr_williams_pct_r(h, l, c, period: int = 14) -> list[float | None]:
    """Williams %R = -100 * (HH - close) / (HH - LL)."""
    out = [None]*len(c)
    for i in range(period-1, len(c)):
        hh = max(h[i-period+1:i+1])
        ll = min(l[i-period+1:i+1])
        if hh > ll:
            out[i] = -100 * (hh - c[i]) / (hh - ll)
    return out


def hr_keltner_upper(c, h, l, period: int = 20, mult: float = 2.0) -> list[float | None]:
    """Keltner upper = EMA(close, p) + mult * ATR(p)."""
    n = len(c)
    # EMA
    alpha = 2 / (period + 1)
    if period > n:
        return [None]*n
    seed = sum(c[:period]) / period
    ema = [None]*n
    ema[period-1] = seed
    prev = seed
    for i in range(period, n):
        prev = c[i] * alpha + prev * (1 - alpha)
        ema[i] = prev
    # ATR
    tr = [0.0]*n
    for i in range(n):
        if i == 0:
            tr[i] = h[i] - l[i]
        else:
            tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    atr = [None]*n
    atr[period-1] = sum(tr[:period]) / period
    for i in range(period, n):
        atr[i] = (atr[i-1] * (period-1) + tr[i]) / period
    return [ema[i] + mult * atr[i] if (ema[i] is not None and atr[i] is not None) else None
            for i in range(n)]


# ─── Registry mapping module name → (hand-roll fn, input kind) ─────


HANDROLL_REGISTRY = {
    # Candlestick (OHLC)
    "inside_bar":              ("hr_inside_bar",        "OHLC"),
    "bullish_engulfing":       ("hr_bullish_engulfing", "OHLC"),
    "bearish_engulfing":       ("hr_bearish_engulfing", "OHLC"),
    "doji":                    ("hr_doji",              "OHLC"),
    "hammer":                  ("hr_hammer",            "OHLC"),
    "shooting_star":           ("hr_shooting_star",     "OHLC"),
    "hanging_man":             ("hr_hanging_man",       "OHLC"),
    "spinning_top":            ("hr_spinning_top",      "OHLC"),
    "marubozu":                ("hr_marubozu",          "OHLC"),
    # Trend / MA / volatility (HLC / C)
    "hull_ma":                 ("hr_hull_ma",                "C"),
    "heikin_ashi":             ("hr_heikin_ashi_close",      "OHLC"),
    "supertrend":              ("hr_supertrend",             "HLC"),
    "choppiness_index":        ("hr_choppiness_index",       "HLC"),
    "bollinger_percent_b":     ("hr_bollinger_percent_b",    "C"),
    "bollinger_bandwidth":     ("hr_bollinger_bandwidth",    "C"),
    "atr_percent":             ("hr_atr_percent",            "HLC"),
    "williams_pct_r":          ("hr_williams_pct_r",         "HLC"),
    "keltner_upper":           ("hr_keltner_upper",          "HLC"),
    # Volume / flow (HLCV)
    "cmf":                     ("hr_cmf",                       "HLCV"),
    "accumulation_distribution": ("hr_accumulation_distribution", "HLCV"),
    "money_flow_volume":       ("hr_money_flow_volume",         "HLCV"),
    # Pivots (HLC / OHLC)
    "camarilla_pivots":        ("hr_camarilla_pivots_h3", "HLC"),
    "classic_pivots":          ("hr_classic_pivot",       "HLC"),
    "fibonacci_pivots":        ("hr_fibonacci_pivot_r1",  "HLC"),
    "central_pivot_range":     ("hr_central_pivot_range_width", "HLC"),
    "woodies_pivots":          ("hr_woodies_pivot",       "OHLC"),
}


def get_handroll(module_name: str):
    """Return (callable, input_kind) or (None, None) if no handroll exists."""
    entry = HANDROLL_REGISTRY.get(module_name)
    if entry is None:
        return None, None
    fn_name, kind = entry
    return globals().get(fn_name), kind


__all__ = ["HANDROLL_REGISTRY", "get_handroll"]
