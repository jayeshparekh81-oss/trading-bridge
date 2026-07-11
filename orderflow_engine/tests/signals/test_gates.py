"""Entry gates, each isolated (Module R6)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from signals.config import SignalConfig
from signals.events import Event
from signals.gates import GateState, apply_gates
from tests.signals.fixtures import make_ctx

IST = timezone(timedelta(hours=5, minutes=30))
CFG = SignalConfig({})


def _ts(h, m):
    return int(datetime(2026, 7, 13, h, m, tzinfo=IST).timestamp() * 1e9)


def _ctx(ts, **kw):
    return make_ctx(ts_ns=ts, **kw)


def _state(**kw):
    base = dict(session_start_ns=_ts(9, 15))
    base.update(kw)
    return GateState(**base)


def test_first_minutes_no_entry():
    allow, reason = apply_gates(_ctx(_ts(9, 17)), _state(), CFG)      # 2 min in
    assert not allow and reason.startswith("first_5min")
    allow, _ = apply_gates(_ctx(_ts(9, 30)), _state(), CFG)           # 15 min in
    assert allow


def test_session_cutoff():
    allow, reason = apply_gates(_ctx(_ts(14, 50)), _state(), CFG)
    assert not allow and "session_cutoff" in reason


def test_max_trades_per_day():
    allow, reason = apply_gates(_ctx(_ts(11, 0)), _state(trades_today=3), CFG)
    assert not allow and reason == "max_trades_per_day"


def test_one_open_position():
    allow, reason = apply_gates(_ctx(_ts(11, 0)), _state(has_open_position=True), CFG)
    assert not allow and reason == "one_open_position"


def test_cooldown():
    st = _state(last_signal_ts_ns=_ts(11, 0))
    allow, reason = apply_gates(_ctx(_ts(11, 2)), st, CFG)            # 2 min < 5 min cooldown
    assert not allow and reason == "cooldown"
    allow, _ = apply_gates(_ctx(_ts(11, 10)), st, CFG)
    assert allow


def test_event_window():
    ev = Event(date(2026, 7, 13), time(9, 15), time(12, 30), "RBI MPC", "high_vol")
    allow, reason = apply_gates(_ctx(_ts(10, 0)), _state(events=[ev]), CFG)
    assert not allow and reason.startswith("event_window:")


def test_expiry_theta_guard_blocks_non_momentum_after_time():
    st = _state(is_expiry_day=True)
    # after 14:00 on expiry day, non-momentum -> blocked
    allow, reason = apply_gates(_ctx(_ts(14, 10), velocity_spike=False), st, CFG)
    assert not allow and reason == "expiry_theta_guard_momentum_only"
    # momentum (velocity spike) is allowed through
    allow, _ = apply_gates(_ctx(_ts(14, 10), velocity_spike=True), st, CFG)
    assert allow


def test_all_gates_pass_midsession():
    allow, reason = apply_gates(_ctx(_ts(11, 0)), _state(), CFG)
    assert allow and reason is None
