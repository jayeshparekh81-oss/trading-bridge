"""FAN-OUT Module B+ — PIECE 1: master emergency halt (tier-3, founder-locked).

PURE, TESTABLE unit. ``master_emergency_halt`` takes the current open positions
(owner + subscriber) + active subscribers and returns a halt-PLAN:
  * sets a platform-wide halt flag (injectable in-process store; durable Redis/DB
    backing + webhook enforcement = SACRED wiring, later);
  * close-all plan (positions_to_close) — intended list; actual dispatch = later;
  * forces ALL subscribers to MANUAL (subscribers_forced_manual);
  * notify payloads + a full audit_entry.
No broker is ever built or called (asserted).
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.master_emergency import (
    InProcessHaltStore,
    is_platform_halted,
    master_emergency_halt,
)

_FIXED = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


def _pos(pid, *, symbol="NIFTY", side="buy", qty=100, sub=None, status="open"):
    return SimpleNamespace(id=pid, symbol=symbol, side=side,
                           remaining_quantity=qty, subscription_id=sub,
                           status=status)


def _sub(sid, *, mode="auto"):
    return SimpleNamespace(subscription_id=sid, execution_mode=mode)


def test_platform_not_halted_by_default():
    assert is_platform_halted(store=InProcessHaltStore()) is False


def test_halt_closes_all_forces_manual_sets_flag_audits_notifies():
    store = InProcessHaltStore()
    assert is_platform_halted(store=store) is False

    positions = [
        _pos("owner-1", sub=None, status="open"),        # owner (subscription None)
        _pos("sub-1", sub="S1", status="open"),          # AUTO subscriber position
        _pos("sub-2", sub="S2", status="partial"),       # MANUAL subscriber position
        _pos("sub-3-closed", sub="S3", status="closed"), # closed → excluded
    ]
    subscribers = [_sub("S1", mode="auto"), _sub("S2", mode="manual")]

    plan = master_emergency_halt(
        positions=positions, subscribers=subscribers,
        reason="broker outage", store=store, now=_FIXED)

    # halt flag is set + exposed
    assert plan.halted is True
    assert is_platform_halted(store=store) is True

    # close-all: every OPEN position (owner + 2 subs); the closed one excluded
    assert len(plan.positions_to_close) == 3
    assert {p["position_id"] for p in plan.positions_to_close} == {
        "owner-1", "sub-1", "sub-2"}
    assert sum(1 for p in plan.positions_to_close if p["owner"]) == 1
    assert sum(1 for p in plan.positions_to_close if not p["owner"]) == 2

    # ALL subscribers forced to MANUAL (from their current mode)
    assert {s["subscription_id"] for s in plan.subscribers_forced_manual} == {
        "S1", "S2"}
    assert all(s["to_mode"] == "manual" for s in plan.subscribers_forced_manual)
    assert any(s["from_mode"] == "auto" for s in plan.subscribers_forced_manual)

    # full audit entry
    assert plan.audit_entry["event"] == "master_emergency_halt"
    assert plan.audit_entry["reason"] == "broker outage"
    assert plan.audit_entry["halted"] is True
    assert plan.audit_entry["positions_to_close"] == 3
    assert plan.audit_entry["subscribers_forced_manual"] == 2

    # notifications: 1 master CRITICAL + 1 per forced-manual subscriber
    assert plan.notifications[0]["level"] == "CRITICAL"
    per_sub = [n for n in plan.notifications if n.get("subscription_id")]
    assert {n["subscription_id"] for n in per_sub} == {"S1", "S2"}


def test_halt_with_no_positions_or_subscribers_is_safe_but_still_halts():
    store = InProcessHaltStore()
    plan = master_emergency_halt(
        positions=[], subscribers=[], reason="drill", store=store, now=_FIXED)

    assert plan.halted is True
    assert is_platform_halted(store=store) is True
    assert plan.positions_to_close == []
    assert plan.subscribers_forced_manual == []
    # audit present + the master notification still emitted
    assert plan.audit_entry["event"] == "master_emergency_halt"
    assert plan.audit_entry["positions_to_close"] == 0
    assert plan.notifications and plan.notifications[0]["level"] == "CRITICAL"


def test_halt_never_calls_a_broker(monkeypatch):
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)

    master_emergency_halt(
        positions=[_pos("owner-1"), _pos("s", sub="S1")],
        subscribers=[_sub("S1")], reason="x",
        store=InProcessHaltStore(), now=_FIXED)

    spy.assert_not_called()
