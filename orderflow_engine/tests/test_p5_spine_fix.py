"""P5 spine fix — golden reproduction of the 07-15 off-by-one (trailing partial bar).

Pre-fix: P5's CLI read tape.bar_rows WITHOUT finalize() -> the real trailing partial bar
(e.g. 07-15 NIFTY bar#81, 19 trades) was dropped -> N-1 rows vs the pipeline spine ->
join schema_mismatch on every day. Post-fix the CLI finalizes (the pipeline's own path):
row count matches the spine 1:1 AND the recovered partial bar's efficiency VALUES are
exactly right (up-ticks / aggressor buy qty from its real trades).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.price_efficiency import main as p5_main
from tape.config import TapeConfig
from tape.engine import TapeEngine
from tests.replayer import fixtures as RF

NS = 1_000_000_000
SID = 61093
DAY = "2026-07-15"


def _tick(ts, vol, ltp):
    return {"ts_recv_ns": ts, "volume": vol, "ltp": ltp, "ltq": 0,
            "bid_price_1": ltp - 0.05, "ask_price_1": ltp + 0.05, "ltt": ts // NS}


def _build_day(tmp_path: Path) -> Path:
    """5 volume-advancing ticks. Default tick_bar_size=100 -> ZERO full bars close during
    replay; ALL trades sit in the trailing partial bar — the exact off-by-one shape
    (pre-fix P5 rows = 0, spine/finalized rows = 1)."""
    day = tmp_path / "data" / DAY
    RF.write_instrument(day, "NIFTY_FUT", SID, [
        _tick(1 * NS, 1000, 100.00),                     # seed (no trade)
        _tick(2 * NS, 1010, 100.10),                     # +10 BUY  @100.10
        _tick(3 * NS, 1030, 100.20),                     # +20 BUY  @100.20
        _tick(4 * NS, 1045, 100.10),                     # +15 SELL @100.10
        _tick(5 * NS, 1060, 100.50),                     # +15 BUY  @100.50 (close)
    ])
    RF.write_events(day, [{"ts_ns": 0, "kind": "SESSION", "detail": "start", "value_num": None}])
    (day / "manifest.json").write_text(json.dumps({"instruments": [
        {"symbol": "NIFTY_FUT", "security_id": SID, "kind": "future",
         "exchange_segment": "NSE_FNO", "gap_check": True, "expiry": ""}]}))
    return day


def _finalized_bar_truth(day: Path):
    """The pipeline-spine truth: replay + finalize (exactly what bars.parquet holds)."""
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource
    eng = TapeEngine(TapeConfig({}), {SID: "NIFTY_FUT"})   # default tick_bar_size=100
    ReplayEngine(ReplaySource(day)).drive(eng, speed="max")
    pre = len([b for b in eng.bar_rows if b["bar_type"] == "tick"])
    eng.finalize()
    bars = [b for b in eng.bar_rows if b["bar_type"] == "tick"]
    return pre, bars


def test_golden_off_by_one_recovered_with_exact_values(tmp_path):
    day = _build_day(tmp_path)
    # 1) reproduce the bug shape: un-finalized rows = N-1 of the spine
    pre, bars = _finalized_bar_truth(day)
    assert pre == 0 and len(bars) == 1                   # the exact 80-vs-81 shape, minimally
    spine_bar = bars[0]
    assert spine_bar["trade_count"] == 4                 # real trades in the partial bar
    # 2) run the FIXED CLI end-to-end
    rc = p5_main(["prog", "--date", DAY, "--root", str(tmp_path)])
    assert rc == 0
    out = json.loads((tmp_path / "analysis" / DAY / "price_efficiency_NIFTY_FUT.json").read_text())
    rows = out["rows"]
    assert len(rows) == len(bars) == 1                   # row count matches the spine 1:1
    # 3) the recovered bar's VALUES are exactly right:
    #    open=100.10 (first trade), close=100.50 -> up = 0.40/0.05 = 8 ticks, dn = 0
    #    buy_vol = 10+20+15 = 45, sell_vol = 15  ->  up_eff = 8/45, dn_eff = 0
    assert spine_bar["open"] == pytest.approx(100.10)
    assert spine_bar["close"] == pytest.approx(100.50)
    assert spine_bar["buy_vol"] == 45 and spine_bar["sell_vol"] == 15
    assert rows[0]["up"] == pytest.approx(8 / 45, abs=1e-6)
    assert rows[0]["dn"] == 0.0
    assert rows[0]["up_w"] == pytest.approx(8 / 45, abs=1e-6)   # window of 1
    assert rows[0]["n_in_window"] == 1
