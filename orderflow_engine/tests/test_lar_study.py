"""P7 LAR state-machine tests (t1..t6) — deterministic scripted synthetic bars."""

from __future__ import annotations

from research.lar_study import STUDY_CONFIG, LevelMachine, forward_r
from tape.config import TapeConfig
from tape.engine import TapeEngine

NS = 1_000_000_000
L = 100.0                      # the reference level (support tests use PDL)


def bar(ts, o, h, lo, c, *, atr=10.0, vol=100.0, med=100.0, delta=0, ofi=None,
        effu=0.5, effd=0.5, p25=0.05, rb=0, ra=0, depth=True):
    return {"ts": ts * NS, "open": o, "high": h, "low": lo, "close": c, "atr": atr,
            "vol": vol, "vol_med20": med, "delta": delta, "book_ofi": ofi,
            "eff_up_w": effu, "eff_dn_w": effd, "eff_p25_aligned": p25,
            "refills_w_bid": rb, "refills_w_ask": ra, "has_depth": depth}


def _states(m):
    return [(t.old, t.new) for t in m.transitions]


# t1) clean sweep -> absorption -> flip -> reclaim -> ARMED -> TRIGGERED, exact sequence
def test_t1_clean_lar_path_exact_sequence():
    m = LevelMachine("PDL", L)
    m.on_bar(bar(1, 104.5, 105, 104, 104))                       # FAR -> APPROACHING (dist 4 <= 5)
    m.on_bar(bar(2, 104, 104, 100.0, 100.05))                    # -> TOUCHED (within 2 ticks)
    m.on_bar(bar(3, 100, 100.1, 99.80, 99.9, vol=200, effd=0.02))  # pierce 0.2 -> SWEPT
    m.on_bar(bar(4, 99.9, 100.0, 99.85, 99.9, vol=200, effd=0.02))  # low-eff + elevated -> ABSORPTION
    m.on_bar(bar(5, 99.9, 100.2, 99.9, 100.1, delta=+500))       # delta flip -> FLOW_FLIPPED
    m.on_bar(bar(6, 100.1, 100.3, 100.05, 100.2))                # close>L run 1
    m.on_bar(bar(7, 100.2, 100.4, 100.1, 100.3))                 # run 2
    m.on_bar(bar(8, 100.3, 100.5, 100.2, 100.4))                 # run 3 -> RECLAIMED
    m.on_bar(bar(9, 100.4, 100.6, 100.1, 100.5))                 # low>=L holds -> ARMED (swing 100.6)
    m.on_bar(bar(10, 100.5, 100.7, 100.4, 100.65))               # high>=100.65 trigger -> TRIGGERED
    assert _states(m) == [("FAR", "APPROACHING"), ("APPROACHING", "TOUCHED"),
                          ("TOUCHED", "SWEPT"), ("SWEPT", "ABSORPTION_CANDIDATE"),
                          ("ABSORPTION_CANDIDATE", "FLOW_FLIPPED"),
                          ("FLOW_FLIPPED", "RECLAIMED"), ("RECLAIMED", "ARMED"),
                          ("ARMED", "TRIGGERED")]
    assert [t.ts_ns // NS for t in m.transitions] == [1, 2, 3, 4, 5, 8, 9, 10]  # hand-checked
    assert m.outcome["side"] == "long" and m.outcome["stop"] == 99.80
    assert m.outcome["trigger_price"] == 100.65                  # swing 100.6 + 1 tick
    assert m.outcome["r_unit"] == round(100.65 - 99.80, 2)


# t2) efficient break (high efficiency, no absorption evidence) -> FAILED, never ABSORPTION
def test_t2_efficient_break_fails_before_absorption():
    m = LevelMachine("PDL", L)
    m.on_bar(bar(1, 104, 105, 104, 104))
    m.on_bar(bar(2, 104, 104, 100.0, 100.0))
    m.on_bar(bar(3, 100, 100, 99.5, 99.6, effd=0.90))            # SWEPT, efficient move down
    for i in range(4, 16):                                       # > sweep_to_absorption_bars
        m.on_bar(bar(i, 99.6, 99.7, 99.5, 99.6, effd=0.90))
    assert m.state == "FAILED"
    assert all(t.new != "ABSORPTION_CANDIDATE" for t in m.transitions)
    assert "no absorption" in m.transitions[-1].reason


# t3) touch without sweep -> EXPIRED via timer, no false SWEPT
def test_t3_touch_without_sweep_no_false_swept():
    m = LevelMachine("PDL", L)
    m.on_bar(bar(1, 104, 105, 104, 104))
    m.on_bar(bar(2, 104, 104, 100.05, 100.05))                   # TOUCHED, never pierces 2 ticks
    for i in range(3, 25):
        m.on_bar(bar(i, 100.2, 100.4, 100.06, 100.3))            # hovers above, pierce < 0.10
    assert m.state == "EXPIRED"
    assert all(t.new != "SWEPT" for t in m.transitions)


# t4) causality: feeding MORE bars never rewrites already-recorded transitions
def test_t4_causal_no_rewrite():
    m = LevelMachine("PDL", L)
    m.on_bar(bar(1, 104, 105, 104, 104))
    m.on_bar(bar(2, 104, 104, 100.0, 100.05))
    frozen = [(t.ts_ns, t.old, t.new, t.reason) for t in m.transitions]
    m.on_bar(bar(3, 50, 200, 10, 60, vol=9999))                  # absurd future bar
    assert [(t.ts_ns, t.old, t.new, t.reason) for t in m.transitions][:len(frozen)] == frozen


# t5) expiry timers per stage
def test_t5_expiry_timers():
    cfg = dict(STUDY_CONFIG)
    # ARMED expiry
    m = LevelMachine("PDL", L)
    for b in [bar(1, 104, 105, 104, 104), bar(2, 104, 104, 100.0, 100.05),
              bar(3, 100, 100.1, 99.8, 99.9, vol=200, effd=0.02),
              bar(4, 99.9, 100, 99.85, 99.9, vol=200, effd=0.02),
              bar(5, 99.9, 100.2, 99.9, 100.1, delta=500),
              bar(6, 100.1, 100.3, 100.05, 100.2), bar(7, 100.2, 100.3, 100.1, 100.25),
              bar(8, 100.25, 100.3, 100.2, 100.28), bar(9, 100.3, 100.6, 100.1, 100.4)]:
        m.on_bar(b)
    assert m.state == "ARMED"
    for i in range(10, 10 + cfg["armed_expiry_bars"] + 2):       # no trigger, holds level
        m.on_bar(bar(i, 100.3, 100.4, 100.1, 100.3))
    assert m.state == "EXPIRED" and "armed_expiry" in m.transitions[-1].reason
    # approach zone hover: the documented NON-terminal reset cycles APPROACHING<->FAR
    m2 = LevelMachine("PDL", L)
    m2.on_bar(bar(1, 104, 105, 104, 104))
    for i in range(2, 2 + cfg["approach_expiry_bars"] + 3):
        m2.on_bar(bar(i, 103, 103.5, 102.5, 103))                # in zone, never touches
    assert any(t.old == "APPROACHING" and t.new == "FAR" for t in m2.transitions)
    assert not m2.terminal()                                     # reset, not terminal
    # total expiry: post-touch sequence exceeding total_expiry_bars -> EXPIRED
    m3 = LevelMachine("PDL", L, cfg={**STUDY_CONFIG, "total_expiry_bars": 5,
                                     "approach_expiry_bars": 50})
    m3.on_bar(bar(1, 104, 105, 104, 104))
    m3.on_bar(bar(2, 104, 104, 100.0, 100.05))                   # TOUCHED
    for i in range(3, 10):
        m3.on_bar(bar(i, 100.2, 100.3, 100.06, 100.25))          # hovers, seq grows past 5
    assert m3.state == "EXPIRED" and "total_expiry" in m3.transitions[-1].reason


# forward_r marks
def test_forward_r_marks():
    outcome = {"trigger_price": 100.65, "stop": 99.8, "side": "long", "r_unit": 0.85}
    bars = [bar(i, 100, 101, 100, 100.65 + 0.85 * (i - 10)) for i in range(30)]
    fr = forward_r(outcome, bars, 10, [5, 10])
    assert fr["r_5b"] == 5.0 and fr["r_10b"] == 10.0             # +1R per bar by construction


# t6) OFF by default — pipeline bars untouched, no LAR keys
def test_t6_flag_off_pipeline_untouched():
    def run_bars():
        eng = TapeEngine(TapeConfig({"bars": {"tick_bar_size": 2}}), {61093: "NIFTY_FUT"})
        vol = 1000
        for i in range(1, 7):
            vol += 10
            eng.on_packet({"is_tick": True, "security_id": 61093, "ts_recv_ns": i * NS,
                           "volume": vol, "ltp": 100.0 + i * 0.1, "ltq": 0,
                           "bid_price_1": 99.9, "ask_price_1": 100.1, "ltt": i}, i * NS)
        return eng.bar_rows
    rows = run_bars()
    assert rows and all("lar" not in str(sorted(r)).lower() for r in rows)
    import research.lar_study  # noqa: F401
    assert run_bars() == rows
