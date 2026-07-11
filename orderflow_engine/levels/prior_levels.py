"""Prior-period levels + gap context (Module R4) — pure functions on daily bars.

  * prior-day levels: PDH / PDL / PDC (high/low/close of the most recent
    completed day before the session date)
  * prior-week levels: PWH / PWL (high/low across the prior calendar week's bars)
  * gap classification: today's open vs prior close, banded by gap_threshold_pct
    (descriptive context — ships functional; not a trade-firing signal)
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from levels.ohlcv import Bar

IST_OFFSET_S = 5 * 3600 + 30 * 60   # Asia/Kolkata is UTC+5:30, no DST


def _ist_date(ts: int) -> date:
    return datetime.fromtimestamp(ts + IST_OFFSET_S, tz=timezone.utc).date()


def prior_day_levels(prior_bar: Bar) -> dict:
    return {"PDH": prior_bar.high, "PDL": prior_bar.low, "PDC": prior_bar.close}


def prior_week_levels(week_bars: list[Bar]) -> dict:
    if not week_bars:
        return {}
    return {"PWH": max(b.high for b in week_bars),
            "PWL": min(b.low for b in week_bars)}


def classify_gap(today_open: float, prior_close: float, threshold_pct: float) -> dict:
    """Classify the open vs prior close: gap up / down / flat within +/- threshold%."""
    if prior_close == 0:
        return {"gap": "flat", "gap_pct": 0.0}
    gap_pct = (today_open - prior_close) / prior_close * 100.0
    if gap_pct > threshold_pct:
        g = "up"
    elif gap_pct < -threshold_pct:
        g = "down"
    else:
        g = "flat"
    return {"gap": g, "gap_pct": round(gap_pct, 4)}


def split_prior_context(daily_bars: list[Bar], session_date: date) -> dict:
    """From a chronological list of daily bars, pick the prior-day bar and the
    prior calendar-week's bars relative to ``session_date`` (all in IST).

    Returns {"prior_day": Bar|None, "prior_week_bars": [Bar,...]}.
    """
    prior = [b for b in daily_bars if _ist_date(b.ts) < session_date]
    if not prior:
        return {"prior_day": None, "prior_week_bars": []}
    prior.sort(key=lambda b: b.ts)
    prior_day = prior[-1]
    # ISO week of the prior trading day; collect that week's bars
    py, pw, _ = _ist_date(prior_day.ts).isocalendar()
    week_bars = [b for b in prior if _ist_date(b.ts).isocalendar()[:2] == (py, pw)]
    return {"prior_day": prior_day, "prior_week_bars": week_bars}
