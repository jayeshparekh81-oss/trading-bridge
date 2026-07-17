"""G0 consecutive-clean-session counter — the holiday/no-session skip (Task #10).

The hole this closes: a weekday holiday NOT in holidays.yaml → the recorder connects on a
closed market, records ~nothing → the verifier writes a PARTIAL (0% coverage) → the OLD
G0 counter reset the streak on a day the market was simply closed. Now a no-session day
(≈0% coverage) and a LISTED holiday are both SKIPPED; only a REAL dirty session resets.
"""

from __future__ import annotations

import json
from datetime import date

from alerts.pulse import G0_START, _g0_counter, _holidays, _no_session


def _report(root, d: date, status: str, coverage_pct: float):
    p = root / "data" / d.isoformat()
    p.mkdir(parents=True, exist_ok=True)
    (p / "report.json").write_text(json.dumps(
        {"status": status, "coverage": {"coverage_pct": coverage_pct}}))


def test_clean_pass_streak_counts(tmp_path):
    _report(tmp_path, date(2026, 7, 15), "PASS", 100.5)
    _report(tmp_path, date(2026, 7, 16), "PASS", 99.3)
    assert _g0_counter(tmp_path, date(2026, 7, 16)) == 2


def test_no_session_day_does_NOT_reset_the_streak(tmp_path):
    """THE HOLE: an unlisted-holiday day (recorder connected, 0% coverage, PARTIAL) must be
    SKIPPED — not reset a live streak."""
    _report(tmp_path, date(2026, 7, 15), "PASS", 100.0)
    _report(tmp_path, date(2026, 7, 16), "PASS", 99.0)
    _report(tmp_path, date(2026, 7, 17), "PARTIAL", 0.0)     # closed weekday: empty session
    _report(tmp_path, date(2026, 7, 20), "PASS", 100.0)      # Mon
    assert _g0_counter(tmp_path, date(2026, 7, 20)) == 3     # 15,16,20 — 17 skipped, NOT reset


def test_real_dirty_session_still_resets(tmp_path):
    """A genuine dirty day (real coverage, non-PASS — e.g. the 07-13 disk crash at 84%)
    MUST still reset. The fix must not over-skip."""
    _report(tmp_path, date(2026, 7, 15), "PASS", 100.0)
    _report(tmp_path, date(2026, 7, 16), "PARTIAL", 84.0)    # real session, real problem
    assert _g0_counter(tmp_path, date(2026, 7, 16)) == 0


def test_listed_holiday_with_stray_report_is_skipped(tmp_path):
    """Belt-and-suspenders: even if a report exists on a LISTED holiday, G0 skips it."""
    hol = next(iter(sorted(h for h in _holidays() if h > G0_START)))   # a real listed holiday
    _report(tmp_path, G0_START, "PASS", 100.0)
    _report(tmp_path, hol, "PARTIAL", 0.0)                   # stray report on a listed holiday
    assert _g0_counter(tmp_path, hol) == 1                   # holiday skipped, streak intact


def test_no_session_helper():
    assert _no_session({"coverage": {"coverage_pct": 0.0}}) is True
    assert _no_session({"coverage": {"coverage_pct": 3.1}}) is True
    assert _no_session({"coverage": {"coverage_pct": 84.0}}) is False   # real dirty day
    assert _no_session({"coverage": {"coverage_pct": 100.0}}) is False
    assert _no_session({}) is False                          # no coverage info -> not skipped
