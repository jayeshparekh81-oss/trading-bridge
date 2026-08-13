"""Prior-day/week levels + gap classification (Module R4)."""

from __future__ import annotations

from datetime import date

from levels.prior_levels import (
    classify_gap, prior_day_levels, prior_week_levels, split_prior_context,
)
from tests.levels import fixtures as F


def test_prior_day_levels():
    b = F.bar(date(2026, 7, 8), o=100, h=112, l=95, c=108)
    assert prior_day_levels(b) == {"PDH": 112, "PDL": 95, "PDC": 108}


def test_prior_week_levels():
    bars = [F.bar(date(2026, 6, 29), 100, 110, 90, 105),
            F.bar(date(2026, 6, 30), 105, 120, 100, 118),
            F.bar(date(2026, 7, 1), 118, 119, 88, 92)]
    assert prior_week_levels(bars) == {"PWH": 120, "PWL": 88}


def test_gap_classification():
    assert classify_gap(105.0, 100.0, 0.3)["gap"] == "up"       # +5%
    assert classify_gap(99.0, 100.0, 0.3)["gap"] == "down"      # -1%
    assert classify_gap(100.2, 100.0, 0.3)["gap"] == "flat"     # +0.2% within band
    assert classify_gap(105.0, 100.0, 0.3)["gap_pct"] == 5.0


def test_split_prior_context_picks_prior_day_and_week():
    # Mon 2026-07-06 .. Fri 2026-07-10 are one ISO week; session is Mon 2026-07-13
    bars = [
        F.bar(date(2026, 7, 6), 100, 105, 99, 104),
        F.bar(date(2026, 7, 7), 104, 108, 103, 107),
        F.bar(date(2026, 7, 8), 107, 110, 100, 101),
        F.bar(date(2026, 7, 9), 101, 106, 98, 105),
        F.bar(date(2026, 7, 10), 105, 112, 104, 111),
    ]
    ctx = split_prior_context(bars, date(2026, 7, 13))
    assert ctx["prior_day"].close == 111                        # Fri 07-10
    pw = prior_week_levels(ctx["prior_week_bars"])
    assert pw == {"PWH": 112, "PWL": 98}                        # across the week
    assert len(ctx["prior_week_bars"]) == 5


def test_split_excludes_session_day_and_future():
    bars = [F.bar(date(2026, 7, 10), 105, 112, 104, 111),
            F.bar(date(2026, 7, 13), 111, 120, 110, 119)]      # session day itself
    ctx = split_prior_context(bars, date(2026, 7, 13))
    assert ctx["prior_day"].close == 111                        # not the 07-13 bar
