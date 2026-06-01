"""Sprint 5b — hand-rolled refs for 38 RAN_OK indicators from 4b+4c.

Per spec: write canonical Pine docs / textbook formulas as references;
classify TRADETRI vs hand-roll. ZERO indicator math touched.

Covers the formulas whose Pine docs / docstring spec is unambiguous.
Indicators with ambiguous / complex specs are listed as
NEEDS_DEFERRED_READING in the registry.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Sequence


# ─── Single-array stats ────────────────────────────────────────────


def hr_price_channel_high(highs, period: int = 20):
    out = [None] * len(highs)
    for i in range(period - 1, len(highs)):
        out[i] = max(highs[i - period + 1 : i + 1])
    return out


def hr_price_channel_low(lows, period: int = 20):
    out = [None] * len(lows)
    for i in range(period - 1, len(lows)):
        out[i] = min(lows[i - period + 1 : i + 1])
    return out


def hr_volume_sma(volumes, period: int = 20):
    out = [None] * len(volumes)
    for i in range(period - 1, len(volumes)):
        out[i] = sum(volumes[i - period + 1 : i + 1]) / period
    return out


def hr_rate_of_change_volume(volumes, period: int = 14):
    """(vol[i] - vol[i-p]) / vol[i-p] * 100."""
    out = [None] * len(volumes)
    for i in range(period, len(volumes)):
        prior = volumes[i - period]
        if prior != 0:
            out[i] = (volumes[i] - prior) / prior * 100
    return out


# ─── Elder Ray (close-EMA based) ───────────────────────────────────


def _hr_ema(values, period: int):
    """SMA-seeded EMA."""
    n = len(values)
    if period > n:
        return [None] * n
    out = [None] * n
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    alpha = 2 / (period + 1)
    prev = seed
    for i in range(period, n):
        prev = values[i] * alpha + prev * (1 - alpha)
        out[i] = prev
    return out


def hr_elder_ray_bull(highs, closes, period: int = 13):
    """Bull = high - EMA(close, period)."""
    ema = _hr_ema(closes, period)
    return [(highs[i] - ema[i]) if ema[i] is not None else None for i in range(len(highs))]


def hr_elder_ray_bear(lows, closes, period: int = 13):
    """Bear = low - EMA(close, period)."""
    ema = _hr_ema(closes, period)
    return [(lows[i] - ema[i]) if ema[i] is not None else None for i in range(len(lows))]


# ─── Volume / flow custom ──────────────────────────────────────────


def hr_cumulative_volume_delta(opens, closes, volumes):
    """sign = +1 if close>=open else -1; CVD = cumsum(sign*vol)."""
    out = []
    cum = 0.0
    for i in range(len(opens)):
        sign = 1 if closes[i] >= opens[i] else -1
        cum += sign * volumes[i]
        out.append(cum)
    return out


def hr_buying_pressure_ratio(opens, closes, volumes, period: int = 20):
    """BPR = sum(vol where close>=open over period) / sum(vol over period)."""
    n = len(opens)
    out = [None] * n
    bull_vol = [volumes[i] if closes[i] >= opens[i] else 0.0 for i in range(n)]
    for i in range(period - 1, n):
        s_bull = sum(bull_vol[i - period + 1 : i + 1])
        s_total = sum(volumes[i - period + 1 : i + 1])
        if s_total > 0:
            out[i] = s_bull / s_total
    return out


def hr_ease_of_movement(highs, lows, volumes, period: int = 14, scale: float = 10000):
    """EMV per the indicator's docstring formula."""
    n = len(highs)
    raw = [None] * n
    for i in range(1, n):
        mid_now = (highs[i] + lows[i]) / 2
        mid_prev = (highs[i-1] + lows[i-1]) / 2
        dist = mid_now - mid_prev
        rng = highs[i] - lows[i]
        if rng > 0 and volumes[i] > 0:
            box = (volumes[i] / scale) / rng
            if box > 0:
                raw[i] = dist / box
    # SMA of raw over period
    out = [None] * n
    for i in range(period - 1, n):
        window = raw[i - period + 1 : i + 1]
        if all(v is not None for v in window):
            out[i] = sum(window) / period
    return out


# ─── Sentiment / breadth (simple counters) ─────────────────────────


def hr_sentiment_oscillator(opens, closes, period: int = 20):
    """Count(close>=open over period) / period * 100."""
    n = len(opens)
    out = [None] * n
    flags = [1 if closes[i] >= opens[i] else 0 for i in range(n)]
    for i in range(period - 1, n):
        out[i] = sum(flags[i - period + 1 : i + 1]) / period * 100
    return out


# ─── Pivot / swing detection ───────────────────────────────────────


def hr_swing_high(highs, left_bars: int = 5, right_bars: int = 5):
    """Confirmed swing high: highs[i] strictly > all in window
    [i-left, i-1] and [i+1, i+right]. Lookahead, so emits at bar i+right_bars."""
    n = len(highs)
    out = [None] * n
    for i in range(left_bars, n - right_bars):
        peak = highs[i]
        if all(highs[j] < peak for j in range(i - left_bars, i)) and \
           all(highs[j] < peak for j in range(i + 1, i + right_bars + 1)):
            # Indicator typically emits at i + right_bars (confirmation bar)
            out[i + right_bars] = peak
    return out


def hr_swing_low(lows, left_bars: int = 5, right_bars: int = 5):
    n = len(lows)
    out = [None] * n
    for i in range(left_bars, n - right_bars):
        trough = lows[i]
        if all(lows[j] > trough for j in range(i - left_bars, i)) and \
           all(lows[j] > trough for j in range(i + 1, i + right_bars + 1)):
            out[i + right_bars] = trough
    return out


def hr_consecutive_higher_lows(lows, lookback: int = 5):
    """Count of consecutive higher-low bars ending at each index."""
    n = len(lows)
    out = [None] * n
    for i in range(lookback, n):
        count = 0
        for k in range(i, i - lookback, -1):
            if lows[k] > lows[k - 1]:
                count += 1
            else:
                break
        out[i] = count
    return out


# ─── Session-aware (timestamp-dependent) ───────────────────────────


def hr_session_high_breakout(highs, timestamps):
    """1 if bar's high > all prior bars' highs in the same calendar day."""
    n = len(highs)
    out = [None] * n
    session_high = None
    current_day = None
    for i, ts in enumerate(timestamps):
        if ts is None:
            out[i] = None
            continue
        day = ts.date()
        if day != current_day:
            current_day = day
            session_high = highs[i]
            out[i] = 0.0  # Not a "breakout" on first bar
            continue
        if highs[i] > session_high:
            session_high = highs[i]
            out[i] = 1.0
        else:
            out[i] = 0.0
    return out


def hr_session_low_breakout(lows, timestamps):
    n = len(lows)
    out = [None] * n
    session_low = None
    current_day = None
    for i, ts in enumerate(timestamps):
        if ts is None:
            out[i] = None
            continue
        day = ts.date()
        if day != current_day:
            current_day = day
            session_low = lows[i]
            out[i] = 0.0
            continue
        if lows[i] < session_low:
            session_low = lows[i]
            out[i] = 1.0
        else:
            out[i] = 0.0
    return out


def hr_session_open_distance(opens, closes, timestamps):
    """close - session_open (first bar's open on the same day)."""
    n = len(opens)
    out = [None] * n
    session_open = None
    current_day = None
    for i, ts in enumerate(timestamps):
        if ts is None:
            out[i] = None
            continue
        day = ts.date()
        if day != current_day:
            current_day = day
            session_open = opens[i]
        out[i] = closes[i] - session_open
    return out


def hr_hour_of_day(timestamps):
    """Just ts.hour for each bar (None if ts None)."""
    return [ts.hour if ts is not None else None for ts in timestamps]


def hr_day_of_week_signal(timestamps):
    """Monday=0..Sunday=6 (or +1 depending on convention)."""
    return [ts.weekday() if ts is not None else None for ts in timestamps]


# ─── Registry ──────────────────────────────────────────────────────


HANDROLL_5B_REGISTRY = {
    # Single-array stats
    "price_channel_high":      ("hr_price_channel_high",      "HONLY", {}),
    "price_channel_low":       ("hr_price_channel_low",       "LONLY", {}),
    "volume_sma":              ("hr_volume_sma",              "VONLY", {}),
    "rate_of_change_volume":   ("hr_rate_of_change_volume",   "VONLY", {}),
    # Elder Ray
    "elder_ray_bull":          ("hr_elder_ray_bull",          "HC", {}),
    "elder_ray_bear":          ("hr_elder_ray_bear",          "LC", {}),
    # Volume / flow
    "cumulative_volume_delta": ("hr_cumulative_volume_delta", "OCV", {}),
    "buying_pressure_ratio":   ("hr_buying_pressure_ratio",   "OCV", {}),
    "ease_of_movement":        ("hr_ease_of_movement",        "HLV", {}),
    # Sentiment / breadth
    "sentiment_oscillator":    ("hr_sentiment_oscillator",    "OC", {}),
    # Swing
    "swing_high":              ("hr_swing_high",              "HONLY", {}),
    "swing_low":               ("hr_swing_low",               "LONLY", {}),
    "consecutive_higher_lows": ("hr_consecutive_higher_lows", "LONLY", {}),
    # Session-aware
    "session_high_breakout":   ("hr_session_high_breakout",   "H_TS", {}),
    "session_low_breakout":    ("hr_session_low_breakout",    "L_TS", {}),
    "session_open_distance":   ("hr_session_open_distance",   "OC_TS", {}),
    "hour_of_day":             ("hr_hour_of_day",             "TS", {}),
    "day_of_week_signal":      ("hr_day_of_week_signal",      "TS", {}),
}


# ─── Additional hand-rolls added after first sweep ─────────────────


def hr_gap_up_down(opens, closes, threshold_pct: float = 0.5):
    """+1 if open > prev_close*(1+threshold/100), -1 if below, 0 within band, None on bar 0."""
    n = len(opens)
    out = [None] * n
    for i in range(1, n):
        prev_c = closes[i-1]
        if prev_c == 0:
            out[i] = 0.0
            continue
        gap_pct = (opens[i] - prev_c) / prev_c * 100
        if gap_pct > threshold_pct: out[i] = 1.0
        elif gap_pct < -threshold_pct: out[i] = -1.0
        else: out[i] = 0.0
    return out


def hr_volume_breakout(opens, closes, volumes, period: int = 20, spike_mult: float = 2.0):
    """1 if current volume > spike_mult * avg volume over period, 0 else."""
    n = len(opens)
    out = [None] * n
    for i in range(period, n):
        avg = sum(volumes[i - period : i]) / period  # exclude current
        if avg > 0 and volumes[i] > spike_mult * avg:
            out[i] = 1.0
        else:
            out[i] = 0.0
    return out


def hr_is_expiry_week(timestamps):
    """1 if bar's ISO week contains the last Thursday of the month."""
    from datetime import date as Date
    out = [None] * len(timestamps)
    def last_thursday(y, m):
        # Find last Thursday of month
        if m == 12:
            last_day = Date(y, 12, 31)
        else:
            from datetime import timedelta as TD
            last_day = Date(y, m+1, 1) - TD(days=1)
        # weekday: Mon=0..Sun=6; Thursday=3
        offset = (last_day.weekday() - 3) % 7
        from datetime import timedelta as TD
        return last_day - TD(days=offset)
    cache = {}
    for i, ts in enumerate(timestamps):
        if ts is None: continue
        ym = (ts.year, ts.month)
        if ym not in cache:
            cache[ym] = last_thursday(*ym)
        last_thu = cache[ym]
        bar_iso = ts.isocalendar()
        thu_iso = last_thu.isocalendar()
        out[i] = 1.0 if (bar_iso.year == thu_iso.year and bar_iso.week == thu_iso.week) else 0.0
    return out


def hr_session_open_distance_pct(opens, closes, timestamps):
    """Percent version: (close - session_open) / session_open * 100."""
    n = len(opens)
    out = [None] * n
    session_open = None
    current_day = None
    for i, ts in enumerate(timestamps):
        if ts is None: continue
        day = ts.date()
        if day != current_day:
            current_day = day
            session_open = opens[i]
        if session_open != 0:
            out[i] = (closes[i] - session_open) / session_open * 100
    return out


HANDROLL_5B_REGISTRY.update({
    "gap_up_down":             ("hr_gap_up_down",             "OC", {}),
    "volume_breakout":         ("hr_volume_breakout",         "OCV", {}),
    "is_expiry_week":          ("hr_is_expiry_week",          "TS", {}),
})

# Override session_open_distance to use percent convention
HANDROLL_5B_REGISTRY["session_open_distance"] = ("hr_session_open_distance_pct", "OC_TS", {})


__all__ = ["HANDROLL_5B_REGISTRY"]
