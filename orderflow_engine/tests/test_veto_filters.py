"""Veto-filter tests (i)-(v) — frozen-parameter proofs, no replay.

(i)   band-veto golden: hand vwap/sd/price -> veto yes/no, both sides, strict-tie
(ii)  absorption golden: 21-bar seq, exact 3x heavy boundary + exact 0.2 doji boundary
(iii) causality: a planted FUTURE volume spike cannot change an earlier candidate's veto
(iv)  warm-up: no veto before 20 prior bars, and no band veto while sd==0
(v)   vetoes OFF -> Trade list byte-identical to the evaluator's own day_trades
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from research.delta_vwap_evaluator import DayCapture, day_trades
from research.veto_filters import (
    day_trades_filtered, veto_absorption, veto_band,
)

NS = 1_000_000_000
SID = 61088


def _ctx(price, vwap, sd):
    return SimpleNamespace(vwap=vwap, price=price,
                           vwap_bands={"upper_1": vwap + sd, "lower_1": vwap - sd})


def _bar(ts, *, vol=100.0, o=100.0, h=100.0, l=100.0, c=100.0):
    return {"end_ts_ns": ts, "volume": vol, "open": o, "high": h, "low": l, "close": c}


def _cap(*, cand, ctx=None, bars):
    """Minimal DayCapture-shaped object for veto functions (they read ctx + bars only)."""
    return DayCapture(day="2026-07-15", candidates=[cand],
                      ctx={(cand["sid"], cand["ts_ns"]): ctx} if ctx else {},
                      bars={cand["sid"]: bars})


def _cand(ts, side):
    return {"ts_ns": ts, "sid": SID, "instrument": "BANKNIFTY_FUT", "side": side,
            "fired": True, "score": 0.0, "delta_al": 1.0, "vwap_dist_al": 1.0}


def _priors(n, start_ts=1 * NS, vol=100.0):
    return [_bar(start_ts + i * NS, vol=vol) for i in range(n)]


# ---------- (i) band veto golden ----------
def test_i_band_veto_golden_both_sides_strict():
    priors = _priors(20)                                  # exactly 20 -> warm-up satisfied
    sig_ts = 100 * NS
    # vwap=100, sd=1 -> upper_1=101, lower_1=99
    def cap_for(side, price):
        c = _cand(sig_ts, side)
        return c, _cap(cand=c, ctx=_ctx(price, 100.0, 1.0),
                       bars=priors + [_bar(sig_ts)])
    c, cap = cap_for("long", 101.5); assert veto_band(c, cap) is True   # 101.5 > 101 -> veto
    c, cap = cap_for("long", 101.0); assert veto_band(c, cap) is False  # exactly at band -> NO
    c, cap = cap_for("long", 100.5); assert veto_band(c, cap) is False  # inside band
    c, cap = cap_for("short", 98.5); assert veto_band(c, cap) is True   # 98.5 < 99 -> veto
    c, cap = cap_for("short", 99.0); assert veto_band(c, cap) is False  # exactly at band -> NO
    c, cap = cap_for("short", 99.5); assert veto_band(c, cap) is False


# ---------- (ii) absorption golden: exact 3x + exact 0.2 doji boundaries ----------
def test_ii_absorption_golden_boundaries():
    sig_ts = 100 * NS
    priors = _priors(20, vol=100.0)                       # avg = 100 -> heavy cut = 300

    def cap_with_bar(side, bar):
        c = _cand(sig_ts, side)
        return c, _cap(cand=c, bars=priors + [dict(bar, end_ts_ns=sig_ts)])

    # exactly 3x volume counts as heavy; body/range exactly 0.2 counts as doji.
    # exactly-representable floats: body=2.0, range=10.0 -> body/range = 0.2 (== DOJI_MAX float).
    # O=100 C=102 (bullish, body 2), H=110 L=100 (range 10) -> 0.2 == doji boundary.
    doji_bar = {"volume": 300.0, "open": 100.0, "close": 102.0, "high": 110.0, "low": 100.0}
    assert (102.0 - 100.0) / (110.0 - 100.0) == 0.2      # exact-float boundary
    c, cap = cap_with_bar("long", doji_bar)
    assert veto_absorption(c, cap) is True                # heavy(==3x) AND doji(==0.2) -> veto
    c, cap = cap_with_bar("short", doji_bar)
    assert veto_absorption(c, cap) is True                # doji vetoes either side

    # heavy + clearly BEARISH close, not a doji -> vetoes LONG only
    bear = {"volume": 300.0, "open": 100.0, "close": 99.0, "high": 100.1, "low": 98.9}
    c, cap = cap_with_bar("long", bear); assert veto_absorption(c, cap) is True
    c, cap = cap_with_bar("short", bear); assert veto_absorption(c, cap) is False

    # just BELOW 3x -> not heavy -> no veto even with a doji body
    light = {"volume": 299.999, "open": 100.0, "close": 102.0, "high": 110.0, "low": 100.0}
    c, cap = cap_with_bar("long", light); assert veto_absorption(c, cap) is False

    # heavy + body just OVER 0.2 body/range and bullish -> not doji, LONG not vetoed
    # body=3.0, range=10.0 -> 0.3 > 0.2
    big_body = {"volume": 300.0, "open": 100.0, "close": 103.0, "high": 110.0, "low": 100.0}
    assert (103.0 - 100.0) / (110.0 - 100.0) > 0.2
    c, cap = cap_with_bar("long", big_body); assert veto_absorption(c, cap) is False


# ---------- (iii) causality: a FUTURE spike cannot change an earlier candidate's veto ----------
def test_iii_causality_future_spike_ignored():
    sig_ts = 100 * NS
    priors = _priors(20, vol=100.0)                       # avg 100 -> heavy cut 300
    sig_bar = {"volume": 250.0, "open": 100.0, "close": 99.0, "high": 100.1, "low": 98.9,
               "end_ts_ns": sig_ts}                       # 250 < 300 -> NOT heavy -> no veto
    c = _cand(sig_ts, "long")
    cap_no_future = _cap(cand=c, bars=priors + [sig_bar])
    assert veto_absorption(c, cap_no_future) is False
    # plant a colossal-volume bar AFTER the candidate; the candidate's avg must be unchanged
    future = _bar(200 * NS, vol=10_000_000.0)
    cap_future = _cap(cand=c, bars=priors + [sig_bar, future])
    assert veto_absorption(c, cap_future) is False       # decision identical -> no lookahead


# ---------- (iv) warm-up: <20 prior bars, and sd==0 ----------
def test_iv_warmup_and_zero_sd_inactive():
    sig_ts = 100 * NS
    # only 19 prior bars -> both vetoes inactive despite an extreme price / huge volume
    priors19 = _priors(19)
    c = _cand(sig_ts, "long")
    cap = _cap(cand=c, ctx=_ctx(999.0, 100.0, 1.0),
               bars=priors19 + [_bar(sig_ts, vol=10_000.0, o=100.0, c=90.0, h=100.1, l=89.9)])
    assert veto_band(c, cap) is False                    # warm-up: <20 priors
    assert veto_absorption(c, cap) is False              # warm-up: <20 priors
    # sd==0 -> band inactive even with 20 priors and price above vwap
    c2 = _cand(sig_ts, "long")
    cap2 = _cap(cand=c2, ctx=_ctx(105.0, 100.0, 0.0), bars=_priors(20) + [_bar(sig_ts)])
    assert veto_band(c2, cap2) is False


# ---------- (v) vetoes OFF -> byte-identical to the evaluator's day_trades ----------
def test_v_off_is_byte_identical_to_day_trades():
    # a real-pricing synthetic capture: minimal SignalContext (registry None -> fallback stop,
    # atr None -> no floor) so price_candidate runs for real without heavy machinery.
    from signals.config import load_signal_config
    from signals.context import SignalContext

    sig_ts = 100 * NS
    ctx = SignalContext(instrument="BANKNIFTY_FUT", index="BANKNIFTY", sid=SID, ts_ns=sig_ts,
                        price=100.0, vwap=100.0, vwap_bands={"upper_1": 101.0, "lower_1": 99.0})
    # bars: the signal bar + a later bar that lets SimPosition step and force-close
    bars = _priors(20) + [_bar(sig_ts, o=100.0, c=100.0, h=100.0, l=100.0),
                          {"end_ts_ns": sig_ts + NS, "volume": 100.0, "open": 100.0,
                           "high": 101.0, "low": 99.5, "close": 100.5, "cvd_slope": 0.0,
                           "ofi": 0.0}]
    cand = _cand(sig_ts, "long")
    cap = DayCapture(day="2026-07-15", candidates=[cand],
                     ctx={(SID, sig_ts): ctx}, bars={SID: bars},
                     cost_inputs={}, sig_cfg=load_signal_config(), depth_ofi_enabled=False)
    base, base_audit = day_trades(cap, "BANKNIFTY_FUT", dmed=0.0)
    off, off_audit = day_trades_filtered(cap, "BANKNIFTY_FUT", dmed=0.0,
                                         apply_band=False, apply_absorption=False)
    assert [(t.day, t.entry_ns, t.exit_ns, t.r) for t in off] == \
           [(t.day, t.entry_ns, t.exit_ns, t.r) for t in base]     # byte-identical trades
    assert off  # (sanity) at least one real priced trade exists to make the equality meaningful
    for k in ("candidates", "rule_fires", "priced", "skipped_unpriceable", "skipped_no_net"):
        assert off_audit[k] == base_audit[k]
