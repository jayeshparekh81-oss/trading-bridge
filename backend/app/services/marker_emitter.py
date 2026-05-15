"""Marker emitter service — write-side of the Phase A trade-markers stack.

Five public coroutines:

    * :func:`emit_entry_marker`    — single entry-row write.
    * :func:`emit_exit_marker`     — single exit-row write, optionally
                                     linked to a prior entry.
    * :func:`bulk_emit_markers`    — N-row batch write (backtest path).
    * :func:`get_markers_by_strategy` — read path with filters +
                                       pagination + total count.
    * :func:`get_strategy_summary` — aggregate stats (trade_count,
                                     total_pnl, win_rate, avg_pnl).

All are async over :class:`AsyncSession`. Idempotency is enforced at
the DB layer by the partial unique index over
``(strategy_id, side, price, date_trunc('second', timestamp_utc))``;
this module catches :class:`IntegrityError` and returns the
already-persisted row instead of raising.

Logging
    Every WARN/ERROR is one structured ``_logger.warning(event_name,
    **fields)`` call — no per-item logs inside a loop. Field names are
    standardised (``user_id``, ``strategy_id``, ``mode``, ``count``,
    ``sample_errors``) so downstream log search works.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.trade_marker import (
    MarkerExitReason,
    MarkerMode,
    MarkerSide,
    TradeMarker,
)
from app.schemas.trade_marker import (
    SignalMetadata,
    TradeMarkerCreate,
    TradeMarkerSummary,
)


_logger = get_logger("services.marker_emitter")


# ─── Internal helpers ──────────────────────────────────────────────────


def _coerce_metadata(
    metadata: SignalMetadata | dict[str, Any] | None,
) -> dict[str, Any]:
    """Normalise the JSONB column input to a plain dict.

    Accepts :class:`SignalMetadata`, raw ``dict``, or ``None``. ``None``
    becomes ``{}`` to match the column's NOT NULL + ``server_default``.
    """
    if metadata is None:
        return {}
    if isinstance(metadata, SignalMetadata):
        return metadata.model_dump(exclude_none=False)
    return dict(metadata)


async def _find_dedup_row(
    db: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    side: MarkerSide | str,
    price: Decimal,
    timestamp_utc: datetime,
) -> TradeMarker | None:
    """Look up an existing row that would collide on the partial
    unique index.

    The DB-side index uses ``date_trunc('second', timestamp_utc)`` which
    SQLite doesn't have; this Python-side lookup bracketed by
    ``[ts_floor, ts_floor + 1s)`` reproduces the dedup window on both
    engines.

    Used in two places:
        1. On :class:`IntegrityError` to return the canonical row.
        2. In ``bulk_emit_markers`` to short-circuit before insert
           (cuts O(N) IntegrityErrors → O(N) selects, both linear but
           the latter has no rollback cost).
    """
    side_str = str(side.value) if isinstance(side, MarkerSide) else str(side)
    ts_floor = timestamp_utc.replace(microsecond=0)
    ts_ceil = ts_floor.replace(microsecond=999999)
    stmt = (
        select(TradeMarker)
        .where(
            TradeMarker.strategy_id == strategy_id,
            TradeMarker.side == side_str,
            TradeMarker.price == price,
            TradeMarker.timestamp_utc >= ts_floor,
            TradeMarker.timestamp_utc <= ts_ceil,
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _build_orm_row(payload: TradeMarkerCreate) -> TradeMarker:
    """Map ``TradeMarkerCreate`` → ORM row with string-coerced enums."""
    return TradeMarker(
        strategy_id=payload.strategy_id,
        user_id=payload.user_id,
        symbol=payload.symbol.upper(),
        exchange=payload.exchange.upper(),
        side=payload.side.value,
        price=payload.price,
        quantity=payload.quantity,
        timestamp_utc=payload.timestamp_utc,
        mode=payload.mode.value,
        linked_marker_id=payload.linked_marker_id,
        pnl=payload.pnl,
        exit_reason=(
            payload.exit_reason.value
            if payload.exit_reason is not None
            else None
        ),
        signal_metadata=_coerce_metadata(payload.signal_metadata),
    )


# ─── Public emitters ───────────────────────────────────────────────────


async def emit_entry_marker(
    db: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    user_id: uuid.UUID,
    symbol: str,
    exchange: str,
    side: MarkerSide,
    price: Decimal,
    quantity: int,
    timestamp_utc: datetime,
    mode: MarkerMode,
    metadata: SignalMetadata | dict[str, Any] | None = None,
) -> TradeMarker:
    """Persist one ENTRY-side marker.

    Raises ``ValueError`` if ``side`` is an exit-side (defensive — the
    type system already prevents this for callers using the enum
    correctly, but enforce at runtime for dict-shaped boundary code).

    Idempotent: if a row already exists within the 1-second dedup
    window, returns the existing row instead of writing a duplicate.
    """
    if not MarkerSide.is_entry(side):
        raise ValueError(
            f"emit_entry_marker called with non-entry side: {side!r}"
        )

    payload = TradeMarkerCreate(
        strategy_id=strategy_id,
        user_id=user_id,
        symbol=symbol,
        exchange=exchange,
        side=side,
        price=price,
        quantity=quantity,
        timestamp_utc=timestamp_utc,
        mode=mode,
        signal_metadata=(
            metadata
            if isinstance(metadata, SignalMetadata) or metadata is None
            else SignalMetadata.model_validate(metadata)
        ),
    )
    return await _insert_one(db, payload)


async def emit_exit_marker(
    db: AsyncSession,
    *,
    entry_marker_id: uuid.UUID | None,
    strategy_id: uuid.UUID,
    user_id: uuid.UUID,
    symbol: str,
    exchange: str,
    side: MarkerSide,
    price: Decimal,
    quantity: int,
    timestamp_utc: datetime,
    mode: MarkerMode,
    pnl: Decimal,
    exit_reason: MarkerExitReason,
    metadata: SignalMetadata | dict[str, Any] | None = None,
) -> TradeMarker:
    """Persist one EXIT-side marker, optionally linked to an entry row.

    ``entry_marker_id`` may be ``None`` for orphan exits (rare — e.g.
    a partial-write recovery where the entry row was never persisted).
    The DB FK on ``linked_marker_id`` is ``ON DELETE SET NULL`` so this
    column degrades gracefully if the entry row is later deleted.
    """
    if not MarkerSide.is_exit(side):
        raise ValueError(
            f"emit_exit_marker called with non-exit side: {side!r}"
        )

    payload = TradeMarkerCreate(
        strategy_id=strategy_id,
        user_id=user_id,
        symbol=symbol,
        exchange=exchange,
        side=side,
        price=price,
        quantity=quantity,
        timestamp_utc=timestamp_utc,
        mode=mode,
        linked_marker_id=entry_marker_id,
        pnl=pnl,
        exit_reason=exit_reason,
        signal_metadata=(
            metadata
            if isinstance(metadata, SignalMetadata) or metadata is None
            else SignalMetadata.model_validate(metadata)
        ),
    )
    return await _insert_one(db, payload)


async def bulk_emit_markers(
    db: AsyncSession,
    *,
    markers: list[TradeMarkerCreate],
) -> list[TradeMarker]:
    """Insert N markers in a single round-trip (backtest path).

    Dedup behaviour: each row is pre-checked against the 1-second
    window; existing rows are returned in place of fresh inserts. The
    return list mirrors the input order so callers can pair input ↔
    output by index.

    Empty input → empty output. No DB hit.

    All-or-nothing within a single ``flush`` — if the DB rejects any
    row, the entire batch rolls back; callers should re-emit individual
    rows in that path so dedup can isolate the offender. The structured
    log records ``count`` + ``sample_errors`` so post-mortems can spot
    which strategy is mis-emitting.
    """
    if not markers:
        return []

    out: list[TradeMarker] = []
    fresh_payloads: list[tuple[int, TradeMarkerCreate]] = []
    fresh_rows: list[TradeMarker] = []

    # Pre-scan for dedup. Order matters — we keep the input ordering
    # in the output by tracking the original index.
    for idx, payload in enumerate(markers):
        existing = await _find_dedup_row(
            db,
            strategy_id=payload.strategy_id,
            side=payload.side,
            price=payload.price,
            timestamp_utc=payload.timestamp_utc,
        )
        if existing is not None:
            out.append(existing)
        else:
            row = _build_orm_row(payload)
            fresh_payloads.append((idx, payload))
            fresh_rows.append(row)
            out.append(row)

    if not fresh_rows:
        return out

    db.add_all(fresh_rows)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        sample = [
            {
                "strategy_id": str(p.strategy_id),
                "side": p.side.value,
                "ts": p.timestamp_utc.isoformat(),
            }
            for _idx, p in fresh_payloads[:5]
        ]
        _logger.warning(
            "marker.bulk_emit.integrity_error",
            count=len(fresh_rows),
            sample_errors=sample,
            error=type(exc).__name__,
        )
        raise

    return out


async def _insert_one(
    db: AsyncSession,
    payload: TradeMarkerCreate,
) -> TradeMarker:
    """Common path for the two single-row emitters.

    Tries the insert; on :class:`IntegrityError` (dedup hit), rolls
    back and returns the existing row.
    """
    existing = await _find_dedup_row(
        db,
        strategy_id=payload.strategy_id,
        side=payload.side,
        price=payload.price,
        timestamp_utc=payload.timestamp_utc,
    )
    if existing is not None:
        _logger.info(
            "marker.emit.dedup_hit",
            strategy_id=str(payload.strategy_id),
            side=payload.side.value,
            mode=payload.mode.value,
            existing_id=str(existing.id),
        )
        return existing

    row = _build_orm_row(payload)
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        # A racing insert won the partial-unique index. Roll back and
        # return the row the other writer landed.
        await db.rollback()
        existing = await _find_dedup_row(
            db,
            strategy_id=payload.strategy_id,
            side=payload.side,
            price=payload.price,
            timestamp_utc=payload.timestamp_utc,
        )
        if existing is None:
            _logger.warning(
                "marker.emit.integrity_error_no_dedup",
                strategy_id=str(payload.strategy_id),
                side=payload.side.value,
                mode=payload.mode.value,
                error=type(exc).__name__,
            )
            raise
        return existing

    return row


# ─── Public readers ────────────────────────────────────────────────────


async def get_markers_by_strategy(
    db: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    mode: MarkerMode,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    symbol: str | None = None,
    side: MarkerSide | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[TradeMarker], int]:
    """Filtered, paginated list of markers for one strategy + mode.

    Returns ``(rows, total)`` where ``total`` is the unpaginated count
    (so the frontend can render a page indicator without a second
    round-trip).

    ``mode`` is REQUIRED — the persistent table is the union of
    backtest, paper and live markers; the caller MUST disambiguate.
    """
    base = select(TradeMarker).where(
        TradeMarker.strategy_id == strategy_id,
        TradeMarker.mode == mode.value,
    )
    if from_ts is not None:
        base = base.where(TradeMarker.timestamp_utc >= from_ts)
    if to_ts is not None:
        base = base.where(TradeMarker.timestamp_utc <= to_ts)
    if symbol is not None:
        base = base.where(TradeMarker.symbol == symbol.upper())
    if side is not None:
        base = base.where(TradeMarker.side == side.value)

    total_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_stmt)).scalar_one() or 0

    page_stmt = (
        base.order_by(TradeMarker.timestamp_utc.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(page_stmt)).scalars().all()
    return list(rows), int(total)


async def get_strategy_summary(
    db: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    mode: MarkerMode,
) -> TradeMarkerSummary:
    """Aggregate stats over EXIT rows for one strategy + mode.

    Computed over EXIT rows only because:
        * ``pnl`` is NULL on entries (DB CHECK enforces).
        * A "trade" is one closed leg → one EXIT row.
        * Open positions don't contribute until they close.

    ``win_rate`` is the fraction of EXIT rows where ``pnl > 0``.
    Returns ``0.0`` for the rate (and ``Decimal('0')`` for the avg)
    when ``trade_count == 0`` so the frontend never has to handle
    ``None`` / ``NaN``.
    """
    exit_filter = TradeMarker.side.in_(
        (MarkerSide.LONG_EXIT.value, MarkerSide.SHORT_EXIT.value)
    )

    count_stmt = select(func.count()).where(
        TradeMarker.strategy_id == strategy_id,
        TradeMarker.mode == mode.value,
        exit_filter,
    )
    trade_count = int(
        (await db.execute(count_stmt)).scalar_one() or 0
    )

    if trade_count == 0:
        return TradeMarkerSummary(
            strategy_id=strategy_id,
            mode=mode,
            trade_count=0,
            total_pnl=Decimal("0"),
            win_rate=0.0,
            avg_pnl=Decimal("0"),
        )

    sum_stmt = select(func.coalesce(func.sum(TradeMarker.pnl), 0)).where(
        TradeMarker.strategy_id == strategy_id,
        TradeMarker.mode == mode.value,
        exit_filter,
    )
    total_pnl_raw = (await db.execute(sum_stmt)).scalar_one()
    total_pnl = Decimal(total_pnl_raw) if total_pnl_raw is not None else Decimal("0")

    wins_stmt = select(func.count()).where(
        TradeMarker.strategy_id == strategy_id,
        TradeMarker.mode == mode.value,
        exit_filter,
        TradeMarker.pnl > 0,
    )
    wins = int((await db.execute(wins_stmt)).scalar_one() or 0)

    win_rate = wins / trade_count
    avg_pnl = total_pnl / Decimal(trade_count)

    return TradeMarkerSummary(
        strategy_id=strategy_id,
        mode=mode,
        trade_count=trade_count,
        total_pnl=total_pnl,
        win_rate=win_rate,
        avg_pnl=avg_pnl,
    )


__all__ = [
    "bulk_emit_markers",
    "emit_entry_marker",
    "emit_exit_marker",
    "get_markers_by_strategy",
    "get_strategy_summary",
]
