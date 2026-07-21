"""Join-tool tests (i)..(vi) — synthetic analysis roots, deterministic."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from research.join_features import join_day

DAY = "2026-07-15"
NS = 1_000_000_000
TS = [100 * NS, 200 * NS, 300 * NS]                     # three candidate bars


def _signals(day_dir: Path, *, legacy: bool = False, insts=("NIFTY_FUT",)):
    n = len(TS) * len(insts)
    cols = {
        "ts_ns": [t for _ in insts for t in TS],
        "index": ["NIFTY"] * n, "instrument": [i for i in insts for _ in TS],
        "side": ["long"] * n, "price": [100.0] * n, "score": [40.0] * n,
        "threshold": [40.0] * n, "base_threshold": [40.0] * n, "fired": [False] * n,
        "gate_reason": [""] * n, "regime_direction": ["bull"] * n,
        "regime_vol_band": ["normal"] * n, "breakdown": ["{}"] * n,
        "entry": [None] * n, "stop": [None] * n, "target": [None] * n,
        "r_value": [None] * n, "exit_reason": [None] * n, "realized_r": [None] * n,
    }
    if not legacy:
        cols.update({"cost_r": [None] * n, "realized_r_net": [None] * n,
                     "lots": [None] * n, "risk_inr": [None] * n})
    day_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({k: pa.array(v) for k, v in cols.items()}),
                   str(day_dir / "signals.parquet"))


def _bars(day_dir: Path, inst="NIFTY_FUT"):
    pq.write_table(pa.table({"end_ts_ns": pa.array(TS), "bar_type": pa.array(["tick"] * 3)}),
                   str(day_dir / f"{inst}_61093.bars.parquet"))


def _p5(day_dir: Path, inst="NIFTY_FUT"):
    rows = [{"up": 0.1 * (i + 1), "dn": 0.0, "up_w": 0.05 * (i + 1), "dn_w": 0.01,
             "n_in_window": i + 1} for i in range(3)]
    (day_dir / f"price_efficiency_{inst}.json").write_text(json.dumps(
        {"day": DAY, "symbol": inst, "rows": rows}))


def _p6(day_dir: Path, inst="NIFTY_FUT"):
    rows = [{"start_ts_ns": t - NS, "end_ts_ns": t, "bid_refills": i, "bid_refill_ratio": None,
             "bid_cancel_qty": 10.0 * i, "bid_walls": 0, "ask_refills": 0,
             "ask_refill_ratio": None, "ask_cancel_qty": 0.0, "ask_walls": 0,
             "bid_cancel_qty_w": 10.0 * i, "bid_refills_w": i, "bid_walls_w": 0,
             "ask_cancel_qty_w": 0.0, "ask_refills_w": 0, "ask_walls_w": 0}
            for i, t in enumerate(TS)]
    (day_dir / f"depth_proxies_{inst}.json").write_text(json.dumps(
        {"day": DAY, "symbol": inst, "rows": rows}))


def _p8(day_dir: Path, inst="NIFTY_FUT"):
    (day_dir / f"bar_quality_{inst}.json").write_text(json.dumps(
        {"day": DAY, "symbol": inst, "quality": {
            "n_bars": 3, "flat_bar_rate": 0.1,
            "duration_s": {"q50": 200.0, "q90_q10_ratio": 3.0},
            "range_pts": {"median": 20.0}, "volume": {"median": 1000.0},
            "trades_per_bar": {"median": 100.0}}}))


def _lar(day_dir: Path, inst="NIFTY_FUT"):
    (day_dir / f"lar_study_{inst}.json").write_text(json.dumps(
        {"day": DAY, "symbol": inst, "levels": {
            "PDL": {"level": "PDL", "price": 99.0, "final_state": "FAILED",
                    "transitions": [
                        {"ts_ns": 150 * NS, "old": "FAR", "new": "APPROACHING", "reason": "r1"},
                        {"ts_ns": 250 * NS, "old": "APPROACHING", "new": "TOUCHED", "reason": "r2"}]},
            "PDH": {"level": "PDH", "price": 101.0, "final_state": "FAR", "transitions": []}}}))


def _read(day_dir: Path):
    t = pq.read_table(str(day_dir / "candidate_features.parquet"))
    return {c: t.column(c).to_pylist() for c in t.column_names}


# (i) golden day — all four sources
def test_i_golden_all_sources(tmp_path):
    d = tmp_path / DAY
    _signals(d); _bars(d); _p5(d); _p6(d); _p8(d); _lar(d)
    rep = join_day(DAY, tmp_path)
    assert rep["rows"] == 3 and rep["p5"] == {"NIFTY_FUT": "ok"}
    import pytest
    c = _read(d)
    assert c["p5_join"] == ["ok"] * 3
    assert c["p5_up"] == pytest.approx([0.1, 0.2, 0.3])
    assert c["p6_join"] == ["ok"] * 3 and c["p6_bid_refills"] == [0, 1, 2]
    assert c["p8_join"] == ["session_level"] * 3 and c["p8_flat_bar_rate"] == [0.1] * 3
    assert c["lar_join"] == ["ok"] * 3
    # LAR as-of: ts 100 -> FAR (before first), 200 -> APPROACHING, 300 -> TOUCHED
    assert c["lar_state_PDL"] == ["FAR", "APPROACHING", "TOUCHED"]
    assert c["lar_final_PDL"] == ["FAILED"] * 3 and c["lar_state_PDH"] == ["FAR"] * 3


# (ii) a source missing entirely -> nulls + reason, zero row loss
def test_ii_missing_source_nulls_no_row_loss(tmp_path):
    d = tmp_path / DAY
    _signals(d); _bars(d); _p5(d); _p8(d); _lar(d)       # NO P6 file
    rep = join_day(DAY, tmp_path)
    c = _read(d)
    assert rep["rows"] == 3 and len(c["ts_ns"]) == 3     # nothing dropped
    assert c["p6_join"] == ["no_file"] * 3
    assert c["p6_bid_refills"] == [None] * 3


# (iii) P5 with no bars spine -> no_ts_spine, never guessed
def test_iii_p5_without_spine(tmp_path):
    d = tmp_path / DAY
    _signals(d); _p5(d)                                   # NO bars.parquet
    join_day(DAY, tmp_path)
    c = _read(d)
    assert c["p5_join"] == ["no_ts_spine"] * 3 and c["p5_up"] == [None] * 3
    # spine/rows length mismatch -> schema_mismatch (also not guessed)
    _bars(d)
    (d / "price_efficiency_NIFTY_FUT.json").write_text(json.dumps(
        {"day": DAY, "symbol": "NIFTY_FUT", "rows": [{"up": 1}]}))   # 1 row vs 3-bar spine
    join_day(DAY, tmp_path)
    assert _read(d)["p5_join"] == ["schema_mismatch"] * 3


# (iv) LAR as-of causality on a hand-built sequence (no future leakage)
def test_iv_lar_asof_no_future_leak(tmp_path):
    d = tmp_path / DAY
    _signals(d); _lar(d)
    join_day(DAY, tmp_path)
    c = _read(d)
    assert c["lar_state_PDL"][0] == "FAR"                # ts 100 < first transition 150
    assert c["lar_state_PDL"][1] == "APPROACHING"        # 150 <= 200 < 250 — never TOUCHED early
    assert c["lar_state_PDL"][2] == "TOUCHED"


# (v) legacy 19-col signals passthrough
def test_v_legacy_19col_passthrough(tmp_path):
    d = tmp_path / DAY
    _signals(d, legacy=True)
    rep = join_day(DAY, tmp_path)
    assert rep["legacy_schema"] is True
    c = _read(d)
    assert c["signals_schema"] == ["legacy_19col"] * 3
    assert c["cost_r"] == [None] * 3 and c["lots"] == [None] * 3   # padded nulls


# (vi) idempotency — run twice, byte-identical output
def test_vi_idempotent(tmp_path):
    d = tmp_path / DAY
    _signals(d); _bars(d); _p5(d); _p6(d); _p8(d); _lar(d)
    join_day(DAY, tmp_path)
    b1 = (d / "candidate_features.parquet").read_bytes()
    join_day(DAY, tmp_path)
    b2 = (d / "candidate_features.parquet").read_bytes()
    assert b1 == b2
    # and source files were never touched
    assert json.loads((d / "depth_proxies_NIFTY_FUT.json").read_text())["day"] == DAY
