"""Sprint 6a — hand-rolled refs for 16 deferred complex-pivot / session-aware
indicators from Sprint 5b's deferred list.

Per spec: Pine convention as primary reference. ZERO indicator math touched.
For indicators with no Pine-equivalent reference (TRADETRI-custom composites),
classify as NEEDS_TRADETRI_TEST_VECTOR and document.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, date as Date, time as Time
from typing import Sequence


# ─── Pivot-distance indicators (clear formula) ─────────────────────


def _group_by_date(timestamps):
    """Return list of (date, [bar_indices]) preserving order."""
    by_date = {}
    order = []
    for i, ts in enumerate(timestamps):
        if ts is None:
            continue
        d = ts.date()
        if d not in by_date:
            by_date[d] = []
            order.append(d)
        by_date[d].append(i)
    return [(d, by_date[d]) for d in order]


def hr_daily_pivot_distance(highs, lows, closes, timestamps):
    """(close - prior_day_pivot) / prior_day_pivot * 100, prior_day_pivot = (H+L+C)/3."""
    n = len(highs)
    out = [None] * n
    days = _group_by_date(timestamps)
    prior_pivot = None
    for day_idx, (day, indices) in enumerate(days):
        if prior_pivot is not None and prior_pivot != 0:
            for i in indices:
                out[i] = (closes[i] - prior_pivot) / prior_pivot * 100
        # Compute this day's pivot for use tomorrow
        day_h = max(highs[i] for i in indices)
        day_l = min(lows[i] for i in indices)
        day_c = closes[indices[-1]]
        prior_pivot = (day_h + day_l + day_c) / 3
    return out


def hr_weekly_pivot_close(highs, lows, closes, timestamps, weeks_back: int = 1):
    """Same pattern as daily but grouped by ISO week."""
    n = len(highs)
    out = [None] * n
    # Group by (year, week)
    by_week = {}
    order = []
    for i, ts in enumerate(timestamps):
        if ts is None: continue
        iso = ts.isocalendar()
        key = (iso.year, iso.week)
        if key not in by_week:
            by_week[key] = []
            order.append(key)
        by_week[key].append(i)
    # Compute each week's pivot
    week_pivot = {}
    for key in order:
        idxs = by_week[key]
        w_h = max(highs[i] for i in idxs)
        w_l = min(lows[i] for i in idxs)
        w_c = closes[idxs[-1]]
        week_pivot[key] = (w_h + w_l + w_c) / 3
    # For each bar in each week, look up the (weeks_back)-th prior week's pivot
    for w_idx, key in enumerate(order):
        if w_idx < weeks_back: continue
        prior_key = order[w_idx - weeks_back]
        pp = week_pivot[prior_key]
        if pp == 0: continue
        for i in by_week[key]:
            out[i] = (closes[i] - pp) / pp * 100
    return out


def hr_monthly_pivot_distance(highs, lows, closes, timestamps, months_back: int = 1):
    """Same pattern as weekly but grouped by (year, month)."""
    n = len(highs)
    out = [None] * n
    by_month = {}
    order = []
    for i, ts in enumerate(timestamps):
        if ts is None: continue
        key = (ts.year, ts.month)
        if key not in by_month:
            by_month[key] = []
            order.append(key)
        by_month[key].append(i)
    month_pivot = {}
    for key in order:
        idxs = by_month[key]
        m_h = max(highs[i] for i in idxs)
        m_l = min(lows[i] for i in idxs)
        m_c = closes[idxs[-1]]
        month_pivot[key] = (m_h + m_l + m_c) / 3
    for m_idx, key in enumerate(order):
        if m_idx < months_back: continue
        prior_key = order[m_idx - months_back]
        pp = month_pivot[prior_key]
        if pp == 0: continue
        for i in by_month[key]:
            out[i] = (closes[i] - pp) / pp * 100
    return out


# ─── Session-aware ────────────────────────────────────────────────


def hr_opening_gap_size(opens, closes, timestamps):
    """(open - prior_session_close) / prior_session_close * 100, constant per day."""
    n = len(opens)
    out = [None] * n
    days = _group_by_date(timestamps)
    prior_close = None
    for day_idx, (day, indices) in enumerate(days):
        if prior_close is not None and prior_close != 0:
            session_open = opens[indices[0]]
            gap_pct = (session_open - prior_close) / prior_close * 100
            for i in indices:
                out[i] = gap_pct
        prior_close = closes[indices[-1]]
    return out


def hr_opening_range_breakout(highs, lows, closes, timestamps, range_minutes: int = 15):
    """+1 if close>orb_high, -1 if close<orb_low, 0 inside, None before orb completes."""
    n = len(highs)
    out = [None] * n
    days = _group_by_date(timestamps)
    for day, indices in days:
        if not indices: continue
        day_start_ts = timestamps[indices[0]]
        orb_end_ts = day_start_ts + timedelta(minutes=range_minutes)
        orb_high = None
        orb_low = None
        for i in indices:
            if timestamps[i] < orb_end_ts:
                # Inside the ORB window
                orb_high = highs[i] if orb_high is None else max(orb_high, highs[i])
                orb_low = lows[i] if orb_low is None else min(orb_low, lows[i])
                out[i] = None
            else:
                if orb_high is None or orb_low is None:
                    out[i] = None
                elif closes[i] > orb_high:
                    out[i] = 1.0
                elif closes[i] < orb_low:
                    out[i] = -1.0
                else:
                    out[i] = 0.0
    return out


def hr_first_hour_range(highs, lows, timestamps, minutes: int = 60):
    """High-low of first `minutes` of session, constant after."""
    n = len(highs)
    out = [None] * n
    days = _group_by_date(timestamps)
    for day, indices in days:
        if not indices: continue
        day_start_ts = timestamps[indices[0]]
        window_end_ts = day_start_ts + timedelta(minutes=minutes)
        window_high = None
        window_low = None
        # Pass 1: compute window high/low
        for i in indices:
            if timestamps[i] < window_end_ts:
                window_high = highs[i] if window_high is None else max(window_high, highs[i])
                window_low = lows[i] if window_low is None else min(window_low, lows[i])
        # Pass 2: emit constant range for bars after the window
        if window_high is not None and window_low is not None:
            rng = window_high - window_low
            for i in indices:
                if timestamps[i] >= window_end_ts:
                    out[i] = rng
    return out


def hr_last_hour_momentum(closes, timestamps, minutes: int = 60,
                          market_close_hour: int = 15, market_close_min: int = 30):
    """% change of close vs anchor-close where anchor = first bar in last `minutes`."""
    n = len(closes)
    out = [None] * n
    days = _group_by_date(timestamps)
    for day, indices in days:
        # last-hour window start
        close_time = Time(market_close_hour, market_close_min)
        anchor_idx = None
        anchor_close = None
        for i in indices:
            ts = timestamps[i]
            mins_from_close = (close_time.hour * 60 + close_time.minute) - (ts.hour * 60 + ts.minute)
            if 0 < mins_from_close <= minutes:
                if anchor_idx is None:
                    anchor_idx = i
                    anchor_close = closes[i]
                    out[i] = 0.0  # baseline
                else:
                    if anchor_close != 0:
                        out[i] = (closes[i] - anchor_close) / anchor_close * 100
    return out


def hr_minutes_to_close(timestamps, market_close_hour: int = 15, market_close_min: int = 30):
    """Minutes from bar's timestamp to market close that day."""
    out = []
    for ts in timestamps:
        if ts is None:
            out.append(None); continue
        close_dt = ts.replace(hour=market_close_hour, minute=market_close_min,
                              second=0, microsecond=0)
        delta = (close_dt - ts).total_seconds() / 60
        out.append(delta)
    return out


# ─── Statistical / other ──────────────────────────────────────────


def hr_correlation_coefficient(values_a, values_b, period: int = 20):
    """Pearson r over rolling period window."""
    n = len(values_a)
    out = [None] * n
    for i in range(period - 1, n):
        wa = values_a[i - period + 1 : i + 1]
        wb = values_b[i - period + 1 : i + 1]
        ma = sum(wa) / period
        mb = sum(wb) / period
        num = sum((wa[k] - ma) * (wb[k] - mb) for k in range(period))
        sa = math.sqrt(sum((wa[k] - ma) ** 2 for k in range(period)))
        sb = math.sqrt(sum((wb[k] - mb) ** 2 for k in range(period)))
        if sa > 0 and sb > 0:
            out[i] = num / (sa * sb)
    return out


def hr_alma(values, period: int = 9, sigma: float = 6.0, offset: float = 0.85):
    """Arnaud Legoux MA — Gaussian-weighted window MA.

    weight[k] = exp(-(k - m)^2 / (2 * s^2))  where m = offset * (period - 1), s = period / sigma
    ALMA[i] = sum(values[i-p+1..i] * w) / sum(w)
    """
    n = len(values)
    out = [None] * n
    if period > n: return out
    m = offset * (period - 1)
    s = period / sigma
    weights = [math.exp(-((k - m) ** 2) / (2 * s ** 2)) for k in range(period)]
    sum_w = sum(weights)
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        out[i] = sum(window[k] * weights[k] for k in range(period)) / sum_w
    return out


# ─── Single-symbol breadth proxies (TRADETRI-specific composite logic) ─────


def hr_breadth_thrust(opens, closes, period: int = 10, ema_period: int = 10):
    """EMA of (advancing count / total count) over rolling window.

    advancing = bars where close > open within window.
    """
    n = len(opens)
    ratios = [None] * n
    for i in range(period - 1, n):
        window_advs = sum(1 for k in range(i - period + 1, i + 1) if closes[k] > opens[k])
        ratios[i] = window_advs / period
    # EMA over ratios
    out = [None] * n
    alpha = 2 / (ema_period + 1)
    seed = None
    for i in range(period - 1, n):
        if ratios[i] is None: continue
        if seed is None:
            seed = ratios[i]; out[i] = seed
        else:
            seed = ratios[i] * alpha + seed * (1 - alpha); out[i] = seed
    return out


def hr_advance_decline_proxy(opens, closes, period: int = 10):
    """Rolling (advancing - declining) count over period.
    advancing = bars where close > open; declining = close < open."""
    n = len(opens)
    out = [None] * n
    for i in range(period - 1, n):
        adv = sum(1 for k in range(i - period + 1, i + 1) if closes[k] > opens[k])
        dec = sum(1 for k in range(i - period + 1, i + 1) if closes[k] < opens[k])
        out[i] = adv - dec
    return out


HANDROLL_6A_REGISTRY = {
    # Pivot-distance (timestamp-aware, clear formula)
    "daily_pivot_distance":      ("hr_daily_pivot_distance",      "HLC_TS"),
    "weekly_pivot_close":        ("hr_weekly_pivot_close",        "HLC_TS"),
    "monthly_pivot_distance":    ("hr_monthly_pivot_distance",    "HLC_TS"),
    # Session-aware
    "opening_gap_size":          ("hr_opening_gap_size",          "OC_TS"),
    "opening_range_breakout":    ("hr_opening_range_breakout",    "HLC_TS"),
    "first_hour_range":          ("hr_first_hour_range",          "HL_TS"),
    "last_hour_momentum":        ("hr_last_hour_momentum",        "C_TS"),
    "minutes_to_close":          ("hr_minutes_to_close",          "TS"),
    # Statistical
    "correlation_coefficient":   ("hr_correlation_coefficient",   "PAIR"),
    "alma":                      ("hr_alma",                      "C"),
    # Breadth (single-symbol proxy interpretations)
    "breadth_thrust":            ("hr_breadth_thrust",            "OC"),
    "advance_decline_proxy":     ("hr_advance_decline_proxy",     "OC"),
}

#: Indicators that don't get hand-rolled this sprint (deferred to founder review).
NEEDS_TRADETRI_TEST_VECTOR = {
    "expiry_day_volatility":     "ATR-on-expiry-days; needs NSE expiry calendar + ATR convention",
    "lunch_consolidation":       "multi-condition: hour + below-avg-vol + below-avg-range; TRADETRI-specific composite",
    "mcclellan_oscillator_proxy": "EMA spread over single-symbol advance/decline proxy; ambiguous formula",
    "session_volume_pace":       "session vol vs lookback-days average; complex session boundary logic",
}


__all__ = ["HANDROLL_6A_REGISTRY", "NEEDS_TRADETRI_TEST_VECTOR"]
