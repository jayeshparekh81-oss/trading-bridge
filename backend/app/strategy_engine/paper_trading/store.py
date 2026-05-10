"""DB-backed CRUD for paper sessions and trades.

Phase 8B-1 discovery exposed that the streaming engine in
:mod:`app.strategy_engine.paper_trading.engine` keeps state in the
``_RECORDS`` module-level dict — process restart wipes the 7-session
counter the live-orders SafetyChain relies on. This module is the
durable side of the same data: every function takes an
:class:`~sqlalchemy.ext.asyncio.AsyncSession` and writes/reads the
``paper_sessions`` and ``paper_trades`` tables added in migration 010.

Sequencing (locked by Phase 8B-1):
    * ``engine.py`` keeps its sync API + in-memory ``_RECORDS`` so the
      existing test suite passes unchanged.
    * The live-orders SafetyChain (next phase) calls
      :func:`get_completed_sessions_count` directly — the engine is no
      longer the source of truth for the 7-session gate.
    * Production callers that want the audit trail also call
      :func:`record_trade` whenever the engine closes a paper trade,
      and :func:`complete_session` when the engine ends a session.

The module deliberately exposes one thin function per persistence
operation rather than a Service object — keeps the public surface
discoverable and matches the existing ``app/services/`` style.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.paper_session import PaperSession as PaperSessionRow
from app.db.models.paper_trade import PaperTrade as PaperTradeRow


class DuplicatePaperSessionError(RuntimeError):
    """Raised when a session for ``(user_id, strategy_id, session_date)``
    already exists.

    The unique constraint enforces "one session per strategy per trading
    day" so a count of completed sessions corresponds to distinct days.
    Callers (the engine, the API layer) decide whether a duplicate is a
    re-attach to the existing row or a hard reject.
    """


# ─── Sessions ──────────────────────────────────────────────────────────


async def create_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
    engine_strategy_id: str,
    session_date: date,
    started_at: datetime | None = None,
) -> PaperSessionRow:
    """Insert a new paper-session row.

    Raises :class:`DuplicatePaperSessionError` if the unique constraint
    on ``(user_id, strategy_id, session_date)`` fires — callers that
    want "get-or-create" semantics should catch that and call
    :func:`get_session_by_date` instead.
    """
    row = PaperSessionRow(
        user_id=user_id,
        strategy_id=strategy_id,
        engine_strategy_id=engine_strategy_id,
        session_date=session_date,
        started_at=started_at or datetime.now(UTC),
        is_complete=False,
        total_trades=0,
        total_pnl=Decimal("0"),
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicatePaperSessionError(
            f"Paper session already exists for user={user_id} "
            f"strategy={strategy_id} date={session_date.isoformat()}"
        ) from exc
    return row


async def complete_session(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    total_trades: int,
    total_pnl: Decimal,
    completed_at: datetime | None = None,
) -> PaperSessionRow:
    """Mark a session complete, stamping totals and the completion time.

    Idempotent — calling on an already-complete row is a no-op for
    ``is_complete``/``completed_at`` and overwrites the totals with the
    latest values supplied. The engine should be the only caller; the
    API layer never marks a session complete on its own.
    """
    row = await db.get(PaperSessionRow, session_id)
    if row is None:
        raise LookupError(f"PaperSession {session_id} not found.")

    row.total_trades = total_trades
    row.total_pnl = total_pnl
    if not row.is_complete:
        row.is_complete = True
        row.completed_at = completed_at or datetime.now(UTC)
    await db.flush()
    return row


async def get_session(
    db: AsyncSession, session_id: uuid.UUID
) -> PaperSessionRow | None:
    """Return one session row by id, or ``None`` if absent."""
    return await db.get(PaperSessionRow, session_id)


async def get_session_by_date(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
    session_date: date,
) -> PaperSessionRow | None:
    """Return the at-most-one session for ``(user, strategy, day)``."""
    stmt = select(PaperSessionRow).where(
        PaperSessionRow.user_id == user_id,
        PaperSessionRow.strategy_id == strategy_id,
        PaperSessionRow.session_date == session_date,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
) -> list[PaperSessionRow]:
    """Return every session row for ``(user, strategy)``, oldest first.

    Order is by ``session_date`` ascending — matches the order the
    engine's ``compute_readiness`` walks sessions, so ports between the
    in-memory and DB-backed paths produce identical reports.
    """
    stmt = (
        select(PaperSessionRow)
        .where(
            PaperSessionRow.user_id == user_id,
            PaperSessionRow.strategy_id == strategy_id,
        )
        .order_by(PaperSessionRow.session_date.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_completed_sessions_count(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
) -> int:
    """Return the count of completed paper sessions for ``(user, strategy)``.

    The live-orders SafetyChain calls this to enforce the
    ``MIN_COMPLETED_SESSIONS = 7`` gate. Counts at the DB so the value
    survives engine restarts.
    """
    stmt = (
        select(func.count())
        .select_from(PaperSessionRow)
        .where(
            PaperSessionRow.user_id == user_id,
            PaperSessionRow.strategy_id == strategy_id,
            PaperSessionRow.is_complete.is_(True),
        )
    )
    return int((await db.execute(stmt)).scalar_one())


# ─── Trades ────────────────────────────────────────────────────────────


async def record_trade(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    entry_at: datetime,
    exit_at: datetime | None,
    symbol: str,
    side: str,
    quantity: int,
    entry_price: Decimal,
    exit_price: Decimal | None,
    pnl: Decimal | None,
    exit_reason: str | None,
) -> PaperTradeRow:
    """Insert one closed paper-trade row attached to ``session_id``."""
    row = PaperTradeRow(
        session_id=session_id,
        entry_at=entry_at,
        exit_at=exit_at,
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        exit_price=exit_price,
        pnl=pnl,
        exit_reason=exit_reason,
    )
    db.add(row)
    await db.flush()
    return row


async def list_trades(
    db: AsyncSession, *, session_id: uuid.UUID
) -> list[PaperTradeRow]:
    """Return trades for one session, oldest first."""
    stmt = (
        select(PaperTradeRow)
        .where(PaperTradeRow.session_id == session_id)
        .order_by(PaperTradeRow.entry_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


__all__ = [
    "DuplicatePaperSessionError",
    "complete_session",
    "create_session",
    "get_completed_sessions_count",
    "get_session",
    "get_session_by_date",
    "list_sessions",
    "list_trades",
    "record_trade",
]
