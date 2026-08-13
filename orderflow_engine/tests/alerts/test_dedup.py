"""Dedup + spam guards + state-file rerun suppression (Module R7)."""

from __future__ import annotations

from alerts.config import AlertsConfig
from alerts.dedup import Deduper


def _cfg(**kw):
    base = {"cooldown_sec": 300, "min_gap_sec": 10, "max_alerts_per_day": 20,
            "persist_state": True}
    base.update(kw)
    return AlertsConfig({"alerts": base})


def test_exact_duplicate_suppressed():
    d = Deduper(_cfg())
    assert d.should_send("NIFTY_FUT", "long", 1000, 1000.0)[0] is True
    d.record("NIFTY_FUT", "long", 1000, 1000.0)
    ok, reason = d.should_send("NIFTY_FUT", "long", 1000, 1500.0)
    assert ok is False and reason == "exact_dup"


def test_cooldown_per_instrument_side():
    d = Deduper(_cfg())
    d.record("NIFTY_FUT", "long", 1, 1000.0)
    # different bar_ts, same (inst,side), 100s later < 300 cooldown -> blocked
    assert d.should_send("NIFTY_FUT", "long", 2, 1100.0) == (False, "cooldown")
    # after cooldown -> allowed
    assert d.should_send("NIFTY_FUT", "long", 3, 1400.0)[0] is True


def test_min_gap_between_any_sends():
    d = Deduper(_cfg())
    d.record("NIFTY_FUT", "long", 1, 1000.0)
    # a DIFFERENT instrument 5s later < 10s min_gap -> blocked
    assert d.should_send("BANKNIFTY_FUT", "short", 2, 1005.0) == (False, "min_gap")
    assert d.should_send("BANKNIFTY_FUT", "short", 3, 1015.0)[0] is True


def test_max_alerts_per_day():
    d = Deduper(_cfg(max_alerts_per_day=2, cooldown_sec=0, min_gap_sec=0))
    d.record("A", "long", 1, 1000.0)
    d.record("B", "long", 2, 2000.0)
    ok, reason = d.should_send("C", "long", 3, 3000.0)
    assert ok is False and reason == "max_per_day"


def test_state_file_rerun_suppresses(tmp_path):
    sp = tmp_path / "alerts_state.json"
    d1 = Deduper(_cfg(), state_path=sp)
    d1.record("NIFTY_FUT", "long", 1000, 1000.0)
    assert sp.exists()
    # a fresh Deduper the same evening loads state -> exact dup suppressed
    d2 = Deduper(_cfg(), state_path=sp)
    assert d2.should_send("NIFTY_FUT", "long", 1000, 9999.0) == (False, "exact_dup")
    assert d2.sent_count == 1


def test_no_persist_when_disabled(tmp_path):
    sp = tmp_path / "alerts_state.json"
    d = Deduper(_cfg(persist_state=False), state_path=sp)
    d.record("NIFTY_FUT", "long", 1, 1000.0)
    assert not sp.exists()
