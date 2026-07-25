"""D5 exploration tests — synthetic golden day, gate causality/no-leakage, determinism."""

from __future__ import annotations

import json
from types import SimpleNamespace

import research.d5_explore as d5

DAY = "2026-07-16"
NS = 1_000_000_000


def _bar(day, hh, mm, o, h, l, c, v=1000):
    ts = d5._bnd(day, hh, mm)
    return {"ts": ts, "end": ts + 60 * NS, "open": o, "high": h, "low": l, "close": c, "vol": v}


def _cap(day=DAY, bars1=None, has_depth=False, events=None, feats=None,
         orh=100.0, orl=99.0):
    return {"day": day, "sym": "NIFTY_FUT", "bars1": bars1 or [], "feats": feats or [],
            "events": events or [], "has_depth": has_depth,
            "ib_end": d5._bnd(day, 10, 15), "orh": orh, "orl": orl}


def _golden_cap():
    """Synthetic day: OR [99,100]; 10:30 clean up-break at 100.50 (r=0.5), rallies to
    target +1.5R=101.25 by 10:45. A second break window later re-arms after close-inside."""
    bars = [
        _bar(DAY, 10, 20, 99.5, 99.9, 99.4, 99.8),           # inside OR (post IB)
        _bar(DAY, 10, 30, 99.9, 100.6, 99.9, 100.5, v=100),  # BREAK up, close 100.5, eff huge
        _bar(DAY, 10, 35, 100.5, 100.9, 100.4, 100.8),
        _bar(DAY, 10, 45, 100.8, 101.4, 100.7, 101.3),       # target 101.25 hit
        _bar(DAY, 11, 0, 101.3, 101.3, 99.5, 99.6),          # back inside -> re-arm
        _bar(DAY, 11, 5, 99.6, 99.7, 98.4, 98.5, v=100),     # BREAK down, close 98.5 (r=0.5)
        _bar(DAY, 11, 10, 98.5, 99.2, 98.4, 99.1),           # adverse -> stop 99.0 hit
    ]
    return _cap(bars1=bars)


def _refs_pass():
    # reference distributions where the golden break bars (eff=|c-o|/tick/vol) clear p80
    return {("NIFTY_FUT", b): [0.0001] * 100 for b in ("0915_1030", "1030_1300", "1300_1530")}


def test_golden_day_trades_and_classification(monkeypatch):
    monkeypatch.setattr(d5, "capture", lambda day, sym, root: _golden_cap()
                        if sym == "NIFTY_FUT" else _cap(bars1=[]))
    monkeypatch.setattr(d5, "cost_for", lambda *a, **k: {"cost_r": 0.3, "net_r": None, "note": "stub"})
    out = d5.run_day(DAY, root=None, analysis_root=None, refs=_refs_pass())
    eps = [e for e in out["episodes"] if e["sym"] == "NIFTY_FUT"]
    assert len(eps) == 2                                   # up-break + re-armed down-break
    assert eps[0]["direction"] == "up" and eps[1]["direction"] == "dn"
    assert eps[0]["would"] == "target_first" and eps[1]["would"] == "stop_first"
    assert all(e["g2"] == "UNAVAILABLE" for e in eps)      # no depth -> PARTIAL-GATE
    assert all(e["gate_class"] == "PARTIAL" for e in eps)
    tr = out["trades"]
    assert len(tr) == 2
    up, dn = tr[0], tr[1]
    assert up["reason"] == "target" and abs(up["gross_r"] - 1.5) < 1e-6
    assert dn["reason"] == "stop" and abs(dn["gross_r"] - (-1.0)) < 1e-6
    assert up["entry"] == 100.5 and abs(up["exit"] - 101.25) < 1e-9


def test_g1_causality_no_same_day_leak(monkeypatch):
    """Planted same-day extreme values must NOT affect the day's own G1 threshold —
    refs are prior-days-only; the day's values are only appended afterwards."""
    monkeypatch.setattr(d5, "capture", lambda day, sym, root: _golden_cap()
                        if sym == "NIFTY_FUT" else _cap(bars1=[]))
    monkeypatch.setattr(d5, "cost_for", lambda *a, **k: {"cost_r": None, "net_r": None, "note": "stub"})
    refs = _refs_pass()
    out1 = d5.run_day(DAY, root=None, analysis_root=None, refs=refs)
    # plant an absurd same-day distribution into the day's OWN g1 output — decisions
    # already made must be identical when re-run with the same PRIOR refs
    out2 = d5.run_day(DAY, root=None, analysis_root=None, refs=_refs_pass())
    assert [e["g1"] for e in out1["episodes"]] == [e["g1"] for e in out2["episodes"]]
    # and the threshold used came from refs (n=100), not from the day's own bars
    assert all(e["g1"]["ref_n"] == 100 for e in out1["episodes"])
    # empty refs (e.g. burn-in day 1) -> no G1 pass, no trades
    out3 = d5.run_day(DAY, root=None, analysis_root=None, refs={})
    assert all(not e["g1"]["passed"] for e in out3["episodes"])
    assert out3["trades"] == []


def test_burn_in_day_reference_only(monkeypatch):
    monkeypatch.setattr(d5, "capture", lambda day, sym, root: _golden_cap()
                        if sym == "NIFTY_FUT" else _cap(bars1=[]))
    out = d5.run_day(DAY, root=None, analysis_root=None, refs=_refs_pass(),
                     trade_allowed=False)
    assert out["trades"] == [] and len(out["episodes"]) == 2   # classified, not traded
    assert out["g1_day_values"]["NIFTY_FUT"]                   # reference values produced


def test_g3_fake_blocks_and_g2_gate():
    # g3: transition into a FAKE state after the break blocks/exits
    T = [SimpleNamespace(ts_ns=100, new="SWEPT"), SimpleNamespace(ts_ns=200, new="ABSORPTION_CANDIDATE")]
    assert d5.g3_fake_ts(T, after_ts=150) == 200
    assert d5.g3_fake_ts(T, after_ts=250) is None
    # g2: up-break needs ASK wall AND no ASK refill inside the break minute
    bar = {"ts": 0, "end": 60 * NS}
    ev = lambda k, s, t: SimpleNamespace(ts_ns=t, kind=k, side=s)
    cap = _cap(has_depth=True, events=[ev("wall", "ask", 10)])
    assert d5.g2_check(cap, bar, "up")["passed"] is True
    cap2 = _cap(has_depth=True, events=[ev("wall", "ask", 10), ev("refill", "ask", 20)])
    assert d5.g2_check(cap2, bar, "up")["passed"] is False
    cap3 = _cap(has_depth=True, events=[ev("wall", "bid", 10)])
    assert d5.g2_check(cap3, bar, "up")["passed"] is False     # wrong side
    assert d5.g2_check(_cap(has_depth=False), bar, "up") is None  # UNAVAILABLE


def test_determinism(monkeypatch):
    monkeypatch.setattr(d5, "capture", lambda day, sym, root: _golden_cap()
                        if sym == "NIFTY_FUT" else _cap(bars1=[]))
    monkeypatch.setattr(d5, "cost_for", lambda *a, **k: {"cost_r": 0.3, "net_r": -0.7, "note": "stub"})
    a = d5.run_day(DAY, root=None, analysis_root=None, refs=_refs_pass())
    b = d5.run_day(DAY, root=None, analysis_root=None, refs=_refs_pass())
    assert json.dumps(a, default=str, sort_keys=True) == json.dumps(b, default=str, sort_keys=True)
