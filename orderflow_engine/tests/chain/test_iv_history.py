"""Daily ATM-IV history + percentile scaffolding (Module R5)."""

from __future__ import annotations

from chain.iv_history import append_daily, iv_percentile, load_history


def test_append_and_load(tmp_path):
    append_daily(tmp_path, "NIFTY", "2026-07-01", 0.20)
    append_daily(tmp_path, "NIFTY", "2026-07-02", 0.25)
    hist = dict(load_history(tmp_path, "NIFTY"))
    assert hist == {"2026-07-01": 0.20, "2026-07-02": 0.25}


def test_append_idempotent_per_date(tmp_path):
    append_daily(tmp_path, "NIFTY", "2026-07-01", 0.20)
    append_daily(tmp_path, "NIFTY", "2026-07-01", 0.22)   # same date -> replace
    assert dict(load_history(tmp_path, "NIFTY")) == {"2026-07-01": 0.22}


def test_percentile_insufficient_until_min_days(tmp_path):
    for i, iv in enumerate([0.20, 0.25, 0.30]):
        append_daily(tmp_path, "NIFTY", f"2026-07-0{i+1}", iv)
    r = iv_percentile(tmp_path, "NIFTY", 0.28, min_days=5)
    assert r["insufficient"] is True and r["percentile"] is None and r["days"] == 3


def test_percentile_computed_when_enough(tmp_path):
    for i, iv in enumerate([0.20, 0.25, 0.30]):
        append_daily(tmp_path, "NIFTY", f"2026-07-0{i+1}", iv)
    r = iv_percentile(tmp_path, "NIFTY", 0.28, min_days=3)
    # 2 of 3 historical values (0.20, 0.25) are <= 0.28 -> 66.67%
    assert r["insufficient"] is False
    assert r["percentile"] == 66.67
