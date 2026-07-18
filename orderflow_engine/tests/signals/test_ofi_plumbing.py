"""R1 depth OFI plumbing into the signal context (2026-07-15).

Per-bar `ofi` must reach ctx.book_ofi and drive ofi_flip when
depth.ofi_enabled — and stay inert (None / False, the old stub) when off.
"""

from __future__ import annotations

from datetime import date

from chain.config import ChainConfig
from chain.engine import ChainEngine
from levels.config import LevelsConfig
from levels.engine import LevelsEngine
from signals.config import SignalConfig
from signals.engine import SignalEngine
from tape.config import TapeConfig
from tape.engine import TapeEngine

SID = 61088
META = {SID: {"symbol": "BANKNIFTY_FUT", "kind": "future", "index": "BANKNIFTY",
              "right": None, "strike": None, "expiry": ""}}


def _sig(ofi_enabled: bool) -> SignalEngine:
    tape = TapeEngine(TapeConfig({"depth": {"ofi_enabled": ofi_enabled},
                                  "bars": {"tick_bar_size": 2}}), {SID: "BANKNIFTY_FUT"})
    lv = LevelsEngine(LevelsConfig({}), {SID: "BANKNIFTY_FUT"}, date="2026-07-13")
    ch = ChainEngine(ChainConfig({}), {}, date(2026, 7, 13))
    return SignalEngine(SignalConfig({}), tape, lv, ch, META, date(2026, 7, 13))


def _bar(ofi: float, qi: float | None = None) -> dict:
    return {"close": 100.0, "delta": 0, "high": 100.0, "low": 100.0, "cvd_slope": 0.0,
            "velocity_spike": False, "velocity_ratio": 1.0, "ofi": ofi, "queue_imbalance": qi}


def test_book_ofi_flows_to_context_when_enabled():
    ctx = _sig(True)._build_context(SID, _bar(42.0), 1_000_000_000)
    assert ctx.book_ofi == 42.0


def test_book_ofi_none_when_disabled():
    ctx = _sig(False)._build_context(SID, _bar(42.0), 1_000_000_000)
    assert ctx.book_ofi is None                 # inert stub preserved


def test_queue_imbalance_flows_to_context_when_enabled():
    ctx = _sig(True)._build_context(SID, _bar(0.0, 0.3), 1_000_000_000)
    assert ctx.queue_imbalance == 0.3           # plumbed value reaches the context


def test_queue_imbalance_none_when_disabled():
    ctx = _sig(False)._build_context(SID, _bar(0.0, 0.3), 1_000_000_000)
    assert ctx.queue_imbalance is None          # depth features off -> inert stub


def test_ofi_flip_derived_when_enabled():
    sig = _sig(True)
    # side-aware: negative OFI is AGAINST a long, WITH a short
    assert sig._flow_flags(SID, _bar(-5.0), "long")["ofi_flip"] is True    # flow against long
    assert sig._flow_flags(SID, _bar(+5.0), "long")["ofi_flip"] is False   # positive flow -> no flip
    assert sig._flow_flags(SID, _bar(-5.0), "short")["ofi_flip"] is False  # winning short -> no flip
    assert sig._flow_flags(SID, _bar(+5.0), "short")["ofi_flip"] is True   # flow against short


def test_ofi_flip_inert_when_disabled():
    sig = _sig(False)
    # OFI off -> ofi_flip is OMITTED (not emitted False), so it can't be counted
    assert "ofi_flip" not in sig._flow_flags(SID, _bar(-5.0), "long")
