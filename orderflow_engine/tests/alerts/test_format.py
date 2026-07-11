"""Formatter golden + truncation + HTML escaping (Module R7)."""

from __future__ import annotations

from alerts.format import (
    AlertPayload, esc, format_daily_summary, format_signal, payload_from_row,
)
from tests.alerts.fixtures import sample_row


def test_payload_from_row_maps_breakdown_and_exit():
    p = payload_from_row(sample_row(), trail_k=3.0, time_stop_min=60)
    assert p.instrument == "NIFTY_FUT" and p.side == "long" and p.score == 35.0
    assert p.components["big_print"] == (1.0, 20.0)      # (raw, weighted)
    assert p.gates_passed is True and p.gates_failed == []
    assert p.exit_plan["thesis_stop"] == 23950.0 and p.exit_plan["trail_k"] == 3.0
    assert p.signal_id.endswith(":long:" + str(sample_row()["ts_ns"]))


def test_format_signal_has_key_fields():
    msg = format_signal(payload_from_row(sample_row(), trail_k=3.0, time_stop_min=60))
    assert "LONG" in msg and "NIFTY_FUT" in msg
    assert "35.0" in msg and "big_print" in msg
    assert "<pre>" in msg and "exit" in msg
    assert sample_row()["instrument"] in msg               # signal_id footer


def test_gate_failed_shown_when_rejected():
    msg = format_signal(payload_from_row(
        sample_row(fired=False, gate_reason="cooldown"), trail_k=3.0, time_stop_min=60))
    assert "⛔" in msg and "cooldown" in msg


def test_html_escaping():
    assert esc("A<B>&C") == "A&lt;B&gt;&amp;C"
    p = payload_from_row(sample_row(instrument="A<B>&C"), trail_k=3.0, time_stop_min=60)
    msg = format_signal(p)
    assert "A&lt;B&gt;&amp;C" in msg
    assert "A<B>&C" not in msg                              # raw unescaped value never leaks


def test_truncation_under_4096():
    comps = {f"comp_{i:03d}": (0.5, float(300 - i)) for i in range(300)}   # far over 4096
    p = AlertPayload(signal_id="X:long:1", ts_ist="t", instrument="X", side="long",
                     score=99.0, fire_threshold=30.0, components=comps, gates_passed=True,
                     gates_failed=[], regime="bull/normal",
                     exit_plan={"thesis_stop": 1, "one_r_target": 2, "trail_k": 3, "time_stop_min": 60})
    msg = format_signal(p, max_chars=4096)
    assert len(msg) <= 4096
    assert msg.endswith("…truncated")
    # highest-weighted components are kept; the lowest-weighted are dropped first
    assert "comp_000" in msg and "comp_299" not in msg


def test_daily_summary_golden():
    summary = {"date": "2026-07-09", "counts": {"candidates": 42, "fired": 0},
               "net_simulated_r": 0.0, "gate_rejects": {"first_5min_no_entry": 40, "cooldown": 2},
               "top_candidates": [{"instrument": "NIFTY_FUT", "side": "long", "score": 55.0},
                                  {"instrument": "BANKNIFTY_FUT", "side": "short", "score": 40.0}]}
    msg = format_daily_summary(summary, top_n=5)
    assert "2026-07-09" in msg and "candidates: 42" in msg and "fired: 0" in msg
    assert "first_5min_no_entry=40" in msg
    assert "NIFTY_FUT" in msg and "55.0" in msg
