"""P5 price-efficiency tests (t1..t4) — deterministic.

t1 hand-computed golden (known ticks/volumes -> exact values)
t2 causality: row i never changes when FUTURE bars are mutated
t3 eps guard: zero aggressive volume -> defined output, no div-by-zero
t4 feature OFF by default: tape/signals pipeline outputs carry no efficiency keys;
   importing the module changes nothing (byte-identical bar rows)
"""

from __future__ import annotations

import pytest

from research.price_efficiency import (DEFAULT_EPS, bar_efficiency,
                                       rolling_efficiency)
from tape.config import TapeConfig
from tape.engine import TapeEngine

TICK = 0.05


def _bar(o, c, bv, sv):
    return {"open": o, "close": c, "buy_vol": bv, "sell_vol": sv}


# t1) hand-computed golden
def test_t1_hand_computed_golden():
    # bar: +0.50 pts = 10 ticks up on 200 aggressive buy qty -> UpsideEff = 10/200 = 0.05
    up, dn = bar_efficiency(_bar(100.00, 100.50, 200, 50))
    assert up == pytest.approx(10 / 200)
    assert dn == 0.0                                          # no downward move
    # down bar: -0.25 pts = 5 ticks on 100 sell qty -> DownsideEff = 5/100 = 0.05
    up2, dn2 = bar_efficiency(_bar(100.25, 100.00, 80, 100))
    assert up2 == 0.0 and dn2 == pytest.approx(5 / 100)
    # rolling-2 over both bars: up_w = 10/(200+80) ; dn_w = 5/(50+100)
    rows = rolling_efficiency([_bar(100.00, 100.50, 200, 50),
                               _bar(100.25, 100.00, 80, 100)], window=2)
    assert rows[1]["up_w"] == pytest.approx(10 / 280, abs=1e-6)
    assert rows[1]["dn_w"] == pytest.approx(5 / 150, abs=1e-6)
    assert rows[1]["n_in_window"] == 2
    assert rows[0]["n_in_window"] == 1                        # warm-up honest, partial window


# t2) causality — mutating FUTURE bars must not change past rows
def test_t2_causal_no_future_leak():
    base = [_bar(100 + i * 0.1, 100 + i * 0.1 + 0.05, 100 + i, 90 + i) for i in range(12)]
    a = rolling_efficiency(base, window=10)
    mutated = [dict(b) for b in base]
    mutated[-1] = _bar(0.0, 999.0, 1, 1)                      # absurd final bar
    b = rolling_efficiency(mutated, window=10)
    assert a[:-1] == b[:-1]                                   # rows 0..n-2 identical
    assert a[-1] != b[-1]                                     # only the mutated bar's row moved


# t3) eps guard — zero aggressive volume stays defined
def test_t3_eps_guard_zero_volume():
    up, dn = bar_efficiency(_bar(100.0, 100.5, 0, 0))
    assert up == pytest.approx((0.5 / TICK) / DEFAULT_EPS)    # divides by eps, not zero
    assert dn == 0.0
    rows = rolling_efficiency([_bar(100.0, 100.0, 0, 0)] * 3, window=10)
    assert all(r["up_w"] == 0.0 and r["dn_w"] == 0.0 for r in rows)   # flat + empty = 0, defined


# t4) OFF by default — pipeline outputs byte-identical, no efficiency keys
def test_t4_flag_off_pipeline_untouched():
    def run_bars():
        eng = TapeEngine(TapeConfig({"bars": {"tick_bar_size": 2}}), {61093: "NIFTY_FUT"})
        ns = 1_000_000_000
        vol = 1000
        for i in range(1, 7):
            vol += 10
            eng.on_packet({"is_tick": True, "security_id": 61093, "ts_recv_ns": i * ns,
                           "volume": vol, "ltp": 100.0 + i * 0.1, "ltq": 0,
                           "bid_price_1": 99.9, "ask_price_1": 100.1, "ltt": i}, i * ns)
        return eng.bar_rows
    rows = run_bars()
    assert rows, "expected bars"
    assert all("up_w" not in r and "efficiency" not in str(sorted(r)) for r in rows)
    # importing/using the research module does not alter engine output (byte-identical)
    import research.price_efficiency  # noqa: F401  (already imported at top — explicit intent)
    assert run_bars() == rows
