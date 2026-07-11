"""Brahmastra 2.0 exit simulation math (Module R6) — hand-computed R outcomes."""

from __future__ import annotations

from signals.exits import ExitPlan, SimBar, SimPosition

BIG = 10 ** 18


def _plan(**kw):
    base = dict(side="long", entry=100.0, stop=98.0, r_value=2.0, target_1r=102.0,
                partial_fraction=0.5, chandelier_k=3.0, sleeper_ns=BIG, momentum_required=2)
    base.update(kw)
    return ExitPlan(stop_source="test", **base)


def test_partial_then_trail_stop_15R():
    pos = SimPosition(_plan(), entry_ts_ns=0)
    assert pos.step(SimBar(1, high=102, low=100, close=101)) is None   # +1R partial, stop->BE 100
    assert pos.step(SimBar(2, high=110, low=101, close=109)) is None   # trail -> stop 104
    out = pos.step(SimBar(3, high=106, low=104, close=105))            # low 104 hits trail stop
    assert out.exit_reason == "stop"
    assert out.realized_r == 1.5      # 0.5 (partial) + 0.5 * (104-100)/2 = 0.5 + 1.0
    assert out.partial_taken


def test_immediate_stop_is_minus_1R():
    pos = SimPosition(_plan(), entry_ts_ns=0)
    out = pos.step(SimBar(1, high=100, low=97, close=98))             # gaps to stop
    assert out.exit_reason == "stop"
    assert out.realized_r == -1.0     # full size at stop = -1R, no partial


def test_sleeper_time_exit():
    pos = SimPosition(_plan(sleeper_ns=100), entry_ts_ns=0)
    out = pos.step(SimBar(200, high=101, low=99.5, close=100.5))      # no stop/target; time out
    assert out.exit_reason == "sleeper"
    assert out.realized_r == (100.5 - 100.0) / 2.0                    # full size at close


def test_short_side_mirror():
    pos = SimPosition(_plan(side="short", stop=102.0, target_1r=98.0), entry_ts_ns=0)
    out = pos.step(SimBar(1, high=103, low=100, close=101))           # high 103 hits stop 102
    assert out.exit_reason == "stop"
    assert out.realized_r == (100.0 - 102.0) / 2.0                    # -1R


def test_momentum_death_after_partial():
    plan = _plan(momentum_required=2)
    pos = SimPosition(plan, entry_ts_ns=0)
    pos.step(SimBar(1, high=102, low=100, close=101))                 # partial taken
    out = pos.step(SimBar(2, high=103, low=101, close=101.5,
                          flow={"cvd_flip": True, "velocity_die": True}))
    assert out.exit_reason == "momentum_death"
