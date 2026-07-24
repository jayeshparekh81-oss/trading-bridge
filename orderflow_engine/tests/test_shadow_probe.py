"""Shadow-probe tests — golden join, shuffled-labels null sanity, scratch-config isolation."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
import yaml

from research.shadow_probe import (
    COMPONENTS, component_table, perm_percentile, probe_capture_day, spearman,
)
from tape.config import HERE as ENGINE_ROOT
from tests.replayer import fixtures as RF

NS = 1_000_000_000
SID = 61093
T0 = 1000 * NS
DAY = "2026-06-01"


# ---------- golden join on a hand-built fixture ----------
def _write_day(root: Path):
    d = root / "data" / DAY
    ticks = [{"ts_recv_ns": T0, "volume": 1000, "ltp": 100.00, "ltq": 0,
              "bid_price_1": 99.95, "ask_price_1": 100.05, "ltt": T0 // NS}]
    px = [100.05, 100.10, 100.00, 100.20, 100.10, 100.30]
    for i, p in enumerate(px):
        ts = T0 + (360 + i) * NS
        ticks.append({"ts_recv_ns": ts, "volume": 1000 + 50 * (i + 1), "ltp": p, "ltq": 0,
                      "bid_price_1": p - 0.05, "ask_price_1": p + 0.05, "ltt": ts // NS})
    RF.write_instrument(d, "NIFTY_FUT", SID, ticks)
    RF.write_events(d, [{"ts_ns": 0, "kind": "SESSION", "detail": "start", "value_num": None}])
    (d / "manifest.json").write_text(json.dumps({"instruments": [
        {"symbol": "NIFTY_FUT", "security_id": SID, "kind": "future",
         "exchange_segment": "NSE_FNO", "gap_check": True, "expiry": ""}]}))


def _scratch_cfg(root: Path, size=2, ofi=True) -> Path:
    cfg = yaml.safe_load((ENGINE_ROOT / "tape_config.yaml").read_text())
    cfg["tape"]["bars"]["tick_bar_size"] = size
    cfg["tape"].setdefault("depth", {})["ofi_enabled"] = ofi
    p = root / "probe_cfg.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def test_golden_join_activations_align_with_candidates(tmp_path):
    _write_day(tmp_path)
    cap, acts = probe_capture_day(DAY, root=tmp_path, config_path=_scratch_cfg(tmp_path))
    assert cap.candidates, "expected candidates on the fixture"
    # every candidate row has a matching activation record with EXACTLY the 3 components
    for c in cap.candidates:
        a = acts[(c["sid"], c["ts_ns"], c["side"])]
        assert set(a) == set(COMPONENTS)
        for v in a.values():
            assert v is not None
    # pricing flag forced False regardless of the scratch yaml's ofi_enabled: true
    assert cap.depth_ofi_enabled is False


# ---------- shuffled labels -> rho ~ 0 sanity ----------
def test_shuffled_labels_rho_near_zero():
    rng = random.Random(1)
    x = [rng.random() for _ in range(200)]
    y = [rng.random() for _ in range(200)]              # independent -> rho ~ 0
    s = perm_percentile(x, y, n=500, seed=42)
    assert s is not None and abs(s["rho"]) < 0.15
    assert 2.0 < s["null_pct"] < 98.0                   # comfortably inside the null body
    # and a perfectly monotone pair pins the tails
    z = list(range(50))
    s2 = perm_percentile([float(v) for v in z], [float(v) for v in z], n=500, seed=42)
    assert s2["rho"] == 1.0 and s2["null_pct"] >= 99.0


def test_component_table_flags_always_zero():
    rows = [{"net": float(i), "book_ofi_act": 0.0, "queue_imbalance_act": 0.0,
             "pain_map_act": 0.1 * (i % 2)} for i in range(20)]
    tab = component_table({"NIFTY_FUT": rows})
    by = {(r["instrument"], r["component"]): r for r in tab}
    ofi = by[("NIFTY_FUT", "book_ofi")]
    assert ofi["nonzero_pct"] == 0.0 and ofi["rho"] is None
    assert "cannot rank" in ofi["note"]                 # plain statement, no fake rho
    pm = by[("NIFTY_FUT", "pain_map")]
    assert pm["rho"] is not None                        # varies -> real rho computed


# ---------- scratch-config isolation ----------
def test_scratch_config_isolation(tmp_path):
    committed = (ENGINE_ROOT / "tape_config.yaml").read_bytes()
    _write_day(tmp_path)
    probe_capture_day(DAY, root=tmp_path, config_path=_scratch_cfg(tmp_path))
    assert (ENGINE_ROOT / "tape_config.yaml").read_bytes() == committed   # untouched
    assert yaml.safe_load((ENGINE_ROOT / "tape_config.yaml").read_text())[
        "tape"]["depth"]["ofi_enabled"] is False        # committed fence still off
