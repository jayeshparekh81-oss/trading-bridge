"""Exit-engine MVP (2026-07-16) — the four corrections.

The exit simulator produces every R outcome the calibration will ever read, and it
was broken in four ways: momentum-death was side-BLIND (a winning short was killed
when its thesis worked), velocity_die was true ~94% of bars (always-on), three of
five death flags were hardcoded dead (so "2-of-5" was a lie), and stops filled at
the exact stop price (no slippage). These regressions lock the fixes both ways.
"""

from __future__ import annotations

from types import SimpleNamespace

from signals.config import SignalConfig
from signals.engine import momentum_flow_flags
from signals.exits import ExitPlan, SimBar, SimPosition, build_exit_plan

MD = {"conditions_required": 2, "cvd_flip": True, "ofi_flip": True}


def _plan(**kw):
    base = dict(side="long", entry=100.0, stop=98.0, r_value=2.0, target_1r=102.0,
                partial_fraction=0.5, chandelier_k=3.0, sleeper_ns=10 ** 18,
                momentum_required=2, stop_source="test")
    base.update(kw)
    return ExitPlan(**base)


# ---- 1. side-aware momentum-death ------------------------------------------------

def test_cvd_flip_side_aware_winning_short_not_flagged():
    # falling CVD: AGAINST a long, WITH a short (short's thesis working)
    assert momentum_flow_flags(MD, "long", -5.0, None, False)["cvd_flip"] is True
    assert momentum_flow_flags(MD, "short", -5.0, None, False)["cvd_flip"] is False   # winning short
    assert momentum_flow_flags(MD, "short", +5.0, None, False)["cvd_flip"] is True    # losing short
    assert momentum_flow_flags(MD, "long", +5.0, None, False)["cvd_flip"] is False


def test_ofi_flip_side_aware_and_only_when_enabled():
    assert "ofi_flip" not in momentum_flow_flags(MD, "long", 0.0, -100.0, False)   # OFI off -> omitted
    assert momentum_flow_flags(MD, "long", 0.0, -100.0, True)["ofi_flip"] is True   # down OFI vs long
    assert momentum_flow_flags(MD, "short", 0.0, -100.0, True)["ofi_flip"] is False  # favours short


def test_winning_short_survives_the_flow_bar():
    """End-to-end: a short in a falling market (its thesis) must NOT momentum-die."""
    plan = _plan(side="short", stop=102.0, target_1r=98.0)
    pos = SimPosition(plan, entry_ts_ns=0)
    # bar takes the 1R target (low<=98) without touching the stop (high<102)
    pos.step(SimBar(1, high=101.0, low=98.0, close=98.5))
    # winning-short flow for a FALLING market: cvd_slope<0 -> cvd_flip False for short
    ff = momentum_flow_flags(MD, "short", -5.0, None, False)
    out = pos.step(SimBar(2, high=99.0, low=97.0, close=97.5, flow=ff))
    assert out is None or out.exit_reason != "momentum_death"


# ---- 2 & 3. dropped flags + honest denominator -----------------------------------

def test_dead_flags_not_emitted():
    ff = momentum_flow_flags(MD, "long", 1.0, None, False)
    for gone in ("velocity_die", "big_print_opposite", "level_reject"):
        assert gone not in ff


def test_conditions_required_matches_live_flag_count():
    md = SignalConfig({}).exits["momentum_death"]
    live = [k for k in ("cvd_flip", "ofi_flip") if md.get(k)]
    assert md.get("conditions_required") == len(live) == 2      # 2-of-2, no phantom flags


def test_momentum_death_dormant_when_only_cvd_live():
    """OFI off -> only cvd_flip can fire (1) < required (2) -> no death."""
    pos = SimPosition(_plan(), entry_ts_ns=0)
    pos.step(SimBar(1, high=102, low=100, close=101))                    # partial taken
    out = pos.step(SimBar(2, high=103, low=101, close=101.5, flow={"cvd_flip": True}))
    assert out is None


def test_momentum_death_fires_when_two_flags_live():
    pos = SimPosition(_plan(), entry_ts_ns=0)
    pos.step(SimBar(1, high=102, low=100, close=101))
    out = pos.step(SimBar(2, high=103, low=101, close=101.5,
                          flow={"cvd_flip": True, "ofi_flip": True}))
    assert out.exit_reason == "momentum_death"


# ---- 4. stop slippage ------------------------------------------------------------

def test_stop_fills_worse_than_stop_level():
    cfg = SignalConfig({})                          # stop_slippage_ticks 2 * tick_size 0.05 = 0.10
    # explicit atr so the plan geometry is deterministic regardless of level/floor
    ctx = SimpleNamespace(price=24000.0, registry=None, atr=20.0)
    plan = build_exit_plan(ctx, cfg, "long")
    assert abs(plan.stop_slip - 0.10) < 1e-12
    pos = SimPosition(plan, entry_ts_ns=0)
    out = pos.step(SimBar(1, high=24000.0, low=plan.stop - 1, close=23990.0))   # stop hit
    assert out.exit_reason == "stop"
    exact_stop_r = (plan.stop - plan.entry) / plan.r_value              # -1R at the exact stop
    assert out.realized_r < exact_stop_r                                # strictly worse (slipped)
    # slipped fill = stop - stop_slip -> exactly stop_slip/r worse than the exact stop
    # (realized_r is rounded to 6 dp in _close, so compare at 1e-5)
    assert abs(out.realized_r - (exact_stop_r - plan.stop_slip / plan.r_value)) < 1e-5


def test_zero_slippage_default_still_fills_at_stop():
    """A plan with no slip (default 0.0) is unchanged — back-compat for old fixtures."""
    pos = SimPosition(_plan(), entry_ts_ns=0)       # stop_slip defaults 0.0
    out = pos.step(SimBar(1, high=100, low=97, close=98))
    assert out.exit_reason == "stop" and out.realized_r == -1.0
