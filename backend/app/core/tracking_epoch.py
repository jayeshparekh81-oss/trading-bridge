"""The ONE owner of the tracking cut-off — where the platform's record begins.

⚠️ READ BEFORE IMPORTING THIS MODULE ANYWHERE.

WHAT THIS IS
────────────
The founder's BSE python and CDSL only began running properly in September
2026. On 2026-09-09 he set a TRACKING CUT-OFF at **1 September 2026 00:00
IST**: everything before it is ARCHIVED — hidden from what the platform counts
and shows — and everything from it onward is the record.

NOTHING IS DELETED. Every pre-cut row stays in the database exactly as it is.
These are real broker orders held for tax and audit; the cut-off is a
REPORTING boundary and nothing else. Reversing it is one edit to one constant,
because no row was ever written to.

⛔ THIS MODULE MUST NEVER BE IMPORTED BY AN EXECUTION MODULE ⛔
──────────────────────────────────────────────────────────────
Not by strategy_executor, direct_exit, position_manager, position_lookup,
order_service, futures_expiry_backstop, kill_switch_service, the position or
reconciliation loops, the webhooks, or marketplace_fanout. Nor may they read
``settings.tracking_epoch`` directly.

This is not style. A cut-off filter on any of the five kill-switch selects
would leave a REAL open Dhan position that the brake silently skips — and the
endpoint would still report success. The same filter on the reconciliation loop
would recreate the phantom-BUY-800 blindness on an age axis: a live broker leg
with no visible DB counterpart and ``db_only`` silently empty. On
``position_lookup`` it would not even error: the webhook logs
``exit_no_open_position`` and returns success on purpose (to stop TradingView
retry storms), so an expiry-day exit would simply never happen.

``tests/integration/test_tracking_epoch_isolation.py`` asserts this, and pins
the never-filter list by INJECTING the filter and watching the guard fail —
ADR 0001 §7: a rule that has never been proven to fail is not enforcement.

⛔ AND NOT THE P&L RECONCILER ⛔
``app/domains/pnl_reconciler/service.py`` already has a ``since`` parameter its
own docstring calls "the GOING-FORWARD boundary". It is a scan window for
pricing recently-closed trips — a DIFFERENT fact that happens to share a shape.
Wiring this epoch into it because the names rhyme would stop the reconciler
pricing new trades, and would hide the historical trips the founder prices by
hand from his own CLI. The archive must still be priceable; that is the whole
point of keeping it.

THE ANCHOR RULE (founder's decision, 2026-09-09)
────────────────────────────────────────────────
Each table is anchored to exactly ONE column, decided once and written down
here so a future straddler is handled by a rule and not by a guess:

    strategy_positions   → opened_at     (a trade belongs to when it was ENTERED)
    strategy_executions  → placed_at     (an order belongs to when it was SENT)
    strategy_signals     → received_at   (a signal belongs to when it ARRIVED)
    trade_markers        → timestamp_utc

There are ZERO straddlers today (no position opened before the cut-off and
closed after it), so ``opened_at`` and ``closed_at`` currently agree. They will
not agree the first time a position spans a future cut-off — and on that day
this rule, not the next contributor's instinct, decides. Callers ask for a
predicate by TABLE; they never spell a column themselves.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ColumnElement, true

from app.core.config import get_settings

__all__ = [
    "executions_in_record",
    "markers_in_record",
    "positions_in_record",
    "signals_in_record",
    "tracking_epoch",
]


def tracking_epoch() -> datetime | None:
    """The instant the record begins, or ``None`` when no cut-off is set.

    ``None`` means "show everything" — the platform's behaviour before this
    existed. It is never a silent default to some other date.
    """
    return get_settings().tracking_epoch


def _at_or_after(column: ColumnElement[datetime | None]) -> ColumnElement[bool]:
    """``column >= epoch``, or an always-true predicate when unset.

    Returning ``true()`` rather than ``None`` means every reporting call site
    can write ``.where(positions_in_record())`` unconditionally. A caller that
    has to remember an ``if`` is a caller that will one day forget it.
    """
    epoch = tracking_epoch()
    if epoch is None:
        return true()
    # Compare in UTC. On Postgres (timestamptz) this changes nothing — the
    # server normalises either way. On the sqlite test engine it changes
    # everything: SQLAlchemy strips tzinfo when binding, so an IST-aware epoch
    # would be compared as the naive wall-clock "2026-09-01 00:00" against
    # UTC-stored values — a silent 5h30m skew that only shows up on rows
    # within half a day of the boundary. Normalising here keeps the tests
    # faithful to production instead of subtly wrong near the line.
    return column >= epoch.astimezone(UTC)


def positions_in_record() -> ColumnElement[bool]:
    """Positions ENTERED on or after the cut-off. Anchor: ``opened_at``."""
    from app.db.models.strategy_position import StrategyPosition

    return _at_or_after(StrategyPosition.opened_at)


def executions_in_record() -> ColumnElement[bool]:
    """Broker orders SENT on or after the cut-off. Anchor: ``placed_at``."""
    from app.db.models.strategy_execution import StrategyExecution

    return _at_or_after(StrategyExecution.placed_at)


def signals_in_record() -> ColumnElement[bool]:
    """Signals RECEIVED on or after the cut-off. Anchor: ``received_at``."""
    from app.db.models.strategy_signal import StrategySignal

    return _at_or_after(StrategySignal.received_at)


def markers_in_record() -> ColumnElement[bool]:
    """Chart/trade markers at or after the cut-off. Anchor: ``timestamp_utc``."""
    from app.db.models.trade_marker import TradeMarker

    return _at_or_after(TradeMarker.timestamp_utc)
