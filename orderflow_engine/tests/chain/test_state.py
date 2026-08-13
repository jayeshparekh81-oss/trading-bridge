"""Chain state reconstruction + ΔOI windows (Module R5)."""

from __future__ import annotations

from chain.state import ChainState, StrikeState

NS = 1_000_000_000


def test_strike_running_fields():
    st = StrikeState([60, 300])
    st.update(0, oi=1000, volume=50, ltp=10.0)
    st.update(30 * NS, oi=1100, volume=80, ltp=11.0)
    assert st.oi == 1100 and st.volume == 80 and st.ltp == 11.0


def test_delta_oi_windows():
    st = StrikeState([60, 300, 900])
    st.update(0, oi=1000, volume=0, ltp=10.0)
    st.update(60 * NS, oi=1100, volume=0, ltp=10.0)
    st.update(120 * NS, oi=1250, volume=0, ltp=10.0)
    # 60s window at t=120s: base = oi at t<=60s = 1100 -> 150
    assert st.delta_oi(120 * NS, 60 * NS) == 150
    # 300s window reaches before session start -> base = earliest 1000 -> 250
    assert st.delta_oi(120 * NS, 300 * NS) == 250


def test_chain_snapshot_shape():
    c = ChainState("NIFTY", [60, 300, 900])
    c.update("2026-07-14", "CE", 23700, 0, oi=1000, volume=10, ltp=120.0)
    c.update("2026-07-14", "PE", 23700, 0, oi=2000, volume=20, ltp=110.0)
    c.update("2026-07-14", "CE", 23700, 60 * NS, oi=1200, volume=15, ltp=125.0)
    rows = c.snapshot(60 * NS)
    assert len(rows) == 2
    ce = next(r for r in rows if r["right"] == "CE")
    assert ce["oi"] == 1200 and ce["ltp"] == 125.0
    assert ce["doi_60s"] == 200          # 1200 - 1000
    assert "doi_300s" in ce and "doi_900s" in ce
