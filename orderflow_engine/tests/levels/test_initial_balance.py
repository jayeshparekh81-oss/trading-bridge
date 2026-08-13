"""Initial Balance levels (Module R4 addendum)."""

from __future__ import annotations

from levels.config import LevelsConfig
from levels.engine import LevelsEngine

NS = 1_000_000_000


def _tick(ts, vol, ltp, sid=1):
    return {"is_tick": True, "security_id": sid, "ts_recv_ns": ts, "volume": vol,
            "ltp": ltp, "bid_price_1": ltp - 0.5, "ask_price_1": ltp + 0.5}


def _engine(minutes):
    return LevelsEngine(LevelsConfig({"levels": {"initial_balance": {"minutes": minutes},
                                                 "vwap": {"snapshot_every_trades": 1}}}),
                        {1: "NIFTY_FUT"}, date="2026-07-13")


def test_ib_from_first_n_minutes():
    eng = _engine(minutes=1)          # 60s IB window
    eng.on_packet(_tick(0, 1000, 100.0), 0)          # seed (no trade)
    eng.on_packet(_tick(10 * NS, 1010, 105.0), 10 * NS)   # first trade -> IB starts here
    eng.on_packet(_tick(30 * NS, 1020, 110.0), 30 * NS)   # within window -> high 110
    eng.on_packet(_tick(40 * NS, 1030, 95.0), 40 * NS)    # within window -> low 95
    eng.on_packet(_tick(90 * NS, 1040, 200.0), 90 * NS)   # AFTER window -> ignored for IB
    eng.finalize()
    st = eng.state[1]
    assert st.ib_high == 110.0 and st.ib_low == 95.0     # 200 excluded
    reg = eng.registries[1]
    types = {l.level_type: l.price for l in reg.levels()}
    assert types["IB_HIGH"] == 110.0 and types["IB_LOW"] == 95.0
    assert reg.context["ib_minutes"] == 1


def test_ib_queryable_via_distance_to_nearest():
    eng = _engine(minutes=1)
    eng.on_packet(_tick(0, 1000, 100.0), 0)
    eng.on_packet(_tick(5 * NS, 1010, 100.0), 5 * NS)
    eng.on_packet(_tick(10 * NS, 1020, 110.0), 10 * NS)
    eng.finalize()
    reg = eng.registries[1]
    near = reg.distance_to_nearest(109.0, types=["IB_HIGH", "IB_LOW"])
    assert near["level_type"] == "IB_HIGH" and near["level_price"] == 110.0


def test_summary_includes_ib():
    eng = _engine(minutes=1)
    eng.on_packet(_tick(0, 1000, 100.0), 0)
    eng.on_packet(_tick(5 * NS, 1010, 103.0), 5 * NS)
    summary = eng.finalize()
    s = summary["per_instrument"]["NIFTY_FUT"]
    assert s["ib_high"] == 103.0 and s["ib_low"] == 103.0
