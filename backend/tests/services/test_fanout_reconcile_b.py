"""FAN-OUT Module B+ — PIECE 2: subscriber-inclusive reconcile LOGIC.

PURE, TESTABLE unit (``reconcile_owner_and_subscribers``): given owner + open
subscriber positions + the active subscriptions, detect:
  * orphan — subscriber position OPEN but owner FLAT on that strategy;
  * gap    — owner OPEN but an active subscriber has NO mirrored position.
Wiring this into the live/sacred ``reconciliation_loop`` (owner-only today) is
a SEPARATE gated step. No DB, no broker here.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.marketplace_fanout import reconcile_owner_and_subscribers


def _op(strategy_id, *, symbol="NIFTY", side="buy", status="open", sub=None):
    return SimpleNamespace(strategy_id=strategy_id, symbol=symbol, side=side,
                           status=status, subscription_id=sub)


def _active(sub_id, strategy_id):
    return SimpleNamespace(subscription_id=sub_id, strategy_id=strategy_id)


def test_orphan_detected_sub_open_owner_flat():
    """Subscriber open but owner flat → orphan (must be closed)."""
    rep = reconcile_owner_and_subscribers(
        owner_positions=[],                                   # owner FLAT
        subscriber_positions=[_op("STRAT1", sub="S1", status="open")],
        active_subscriptions=[_active("S1", "STRAT1")])

    assert len(rep.orphans) == 1
    assert rep.orphans[0].kind == "orphan"
    assert rep.orphans[0].subscription_id == "S1"
    assert rep.gaps == []
    assert rep.clean is False


def test_gap_detected_owner_open_sub_missing():
    """Owner open but active subscriber has no mirror → gap."""
    rep = reconcile_owner_and_subscribers(
        owner_positions=[_op("STRAT1", status="open")],
        subscriber_positions=[],                              # sub MISSING
        active_subscriptions=[_active("S1", "STRAT1")])

    assert len(rep.gaps) == 1
    assert rep.gaps[0].kind == "gap"
    assert rep.gaps[0].subscription_id == "S1"
    assert rep.orphans == []
    assert rep.clean is False


def test_clean_when_owner_and_subscriber_both_open():
    rep = reconcile_owner_and_subscribers(
        owner_positions=[_op("STRAT1", status="open")],
        subscriber_positions=[_op("STRAT1", sub="S1", status="open")],
        active_subscriptions=[_active("S1", "STRAT1")])

    assert rep.clean is True
    assert rep.orphans == [] and rep.gaps == []
    assert rep.matched == 1


def test_reconcile_is_pure_never_calls_broker(monkeypatch):
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)

    reconcile_owner_and_subscribers(
        owner_positions=[], subscriber_positions=[], active_subscriptions=[])

    spy.assert_not_called()
