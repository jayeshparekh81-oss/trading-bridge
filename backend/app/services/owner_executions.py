"""Owner-scoped executions and priced positions — the ONE query behind every
customer-facing trade surface (the /trades page, its CSV export, the analytics
page and its CSV) so a file a customer downloads can never disagree with the
page they downloaded it from.

Executions are user-scoped via their signal (join through) and
``subscription_id IS NULL`` excludes fan-out subscriber rows — a subscriber's
copy of a signal belongs to the subscriber's own view, not the author's.

Round-trip P&L does NOT live on executions (a leg has no P&L). It lives on
``strategy_positions.final_pnl`` and is only meaningful under a PRICED
attribution tag (``bot_only`` / ``account_flat`` — the founder's exit rule);
``human_interfered`` rows stay NULL and are surfaced as such, never as zero.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.sql import Select

from app.core.tracking_epoch import (
    executions_in_record,
    positions_in_record,
)
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.domains.pnl_reconciler.attribution import TAG_ACCOUNT_FLAT, TAG_BOT_ONLY

#: The tags under which ``final_pnl`` is a real, attributable number.
PRICED_ATTRIBUTION_TAGS: frozenset[str] = frozenset({TAG_BOT_ONLY, TAG_ACCOUNT_FLAT})

#: Columns in the executions CSV, in order. These are the fields the /trades
#: page shows plus the ids needed to reconcile against a broker statement.
#: Deliberately NOT ``broker_response`` (a raw JSON blob per row) and NOT
#: ``broker_credential_id`` (an internal key that means nothing to a customer).
EXPORT_COLUMNS: tuple[str, ...] = (
    "id",
    "signal_id",
    "leg_number",
    "leg_role",
    "symbol",
    "side",
    "quantity",
    "order_type",
    "price",
    "broker_order_id",
    "broker_status",
    "error_code",
    "error_message",
    "placed_at",
    "completed_at",
)

#: Hard ceiling on rows per export. Well above any real account today and low
#: enough that the whole file is built in memory without thought. Raise
#: deliberately, not silently.
EXPORT_MAX_ROWS = 10_000


def owner_executions_query(user_id: UUID, signal_id: UUID | None = None) -> Select[tuple[StrategyExecution]]:
    """Every execution the owner placed for their OWN strategies, newest first.

    Scoped to the tracking record (see :mod:`app.core.tracking_epoch`). This
    builder backs five customer surfaces — the trades list, its CSV export, the
    trades stats block, and both signal-execution views — so the cut-off is
    applied ONCE here rather than re-spelled at each of them.
    """
    stmt = (
        select(StrategyExecution)
        .join(
            StrategySignal,
            StrategySignal.id == StrategyExecution.signal_id,
        )
        .where(
            StrategySignal.user_id == user_id,
            StrategyExecution.subscription_id.is_(None),
            # The tracking cut-off. Anchored on placed_at — an order belongs to
            # when it was SENT. Pre-cut orders stay in the table untouched;
            # they are simply not part of the record this platform reports.
            executions_in_record(),
        )
        .order_by(StrategyExecution.placed_at.desc())
    )
    if signal_id is not None:
        stmt = stmt.where(StrategyExecution.signal_id == signal_id)
    return stmt


def owner_closed_positions_query(user_id: UUID) -> Select[tuple[StrategyPosition]]:
    """Every CLOSED round trip of the owner's own strategies, oldest first
    (the order an equity curve is drawn in). Priced or not — the caller reads
    ``pnl_attribution`` to tell them apart; nothing here invents a zero."""
    return (
        select(StrategyPosition)
        .where(
            StrategyPosition.user_id == user_id,
            StrategyPosition.subscription_id.is_(None),
            StrategyPosition.status == "closed",
            # Anchored on opened_at, NOT closed_at — a trade belongs to when it
            # was ENTERED. Zero straddlers exist today so the two agree; the
            # rule is written down in app/core/tracking_epoch.py so the first
            # one that spans a cut-off is decided by rule, not by instinct.
            positions_in_record(),
        )
        .order_by(StrategyPosition.closed_at.asc().nulls_last(), StrategyPosition.opened_at.asc())
    )


def csv_cell(value: object) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    return str(value)


#: Broker statuses we will print. Anything else is unknown and renders as a
#: dash — never "pending", which is a claim about the order's state.
def broker_status_of(e: StrategyExecution) -> str | None:
    """The broker's own status for this leg, or ``None`` when unknown.

    ⚠️ THIS EXISTS SO THE RAW BROKER PAYLOAD NEVER LEAVES THE SERVER.
    ``strategy_executions.broker_response`` holds Dhan's verbatim reply —
    including ``dhanClientId``, ``exchangeOrderId``, ``securityId`` — and it
    was being serialised straight to the browser by
    ``GET /api/strategies/executions``. The status is the only part of it a
    customer needs, so it is extracted HERE and the payload stays behind.

    ``broker_status`` the column is NULL on every LIVE row: it is written only
    on the paper path (strategy_executor.py, direct_exit.py — both frozen, so
    this is read at serialisation time rather than fixed at source). The
    broker's answer is in the response body, under ``status`` or
    ``raw.orderStatus``.

    Returns None rather than a guess. The UI renders a dash for None; it must
    never print "pending" for an order whose state we have not read.
    """
    if e.broker_status:
        return str(e.broker_status)
    raw = e.broker_response
    if not isinstance(raw, dict):
        return None
    for path in (("status",), ("raw", "orderStatus"), ("orderStatus",)):
        node: object = raw
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, str) and node.strip():
            return node.strip().upper()
    return None


def execution_row(e: StrategyExecution) -> dict[str, object]:
    """One execution as the analytics/trades surfaces render it."""
    return {
        "id": str(e.id),
        "signal_id": str(e.signal_id),
        "leg_number": e.leg_number,
        "leg_role": e.leg_role,
        "symbol": e.symbol,
        "side": e.side,
        "quantity": e.quantity,
        "order_type": e.order_type,
        "price": str(e.price) if e.price is not None else None,
        "broker_order_id": e.broker_order_id,
        "broker_status": broker_status_of(e),
        "error_code": e.error_code,
        "error_message": e.error_message,
        "placed_at": e.placed_at.isoformat() if e.placed_at else None,
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
    }


__all__ = [
    "EXPORT_COLUMNS",
    "EXPORT_MAX_ROWS",
    "PRICED_ATTRIBUTION_TAGS",
    "broker_status_of",
    "csv_cell",
    "execution_row",
    "owner_closed_positions_query",
    "owner_executions_query",
]
