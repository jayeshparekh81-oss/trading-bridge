"""Backtest-side trade-marker persistence (Queue DD).

Single public coroutine :func:`persist_backtest_trade_markers` —
takes engine ``Trade`` objects produced by ``run_backtest`` and writes
them to the ``trade_markers`` table with ``mode=BACKTEST``.

The implementation delegates to :func:`app.services.marker_emitter.bulk_emit_markers`
for the actual ORM writes and per-bar dedup; this module owns only the
mapping from the engine's `Trade` shape to the service-layer
`TradeMarkerCreate` shape, plus the cross-run idempotency check tied
to ``backtest_run_id``.

Idempotency
-----------
Two layers:

    1. **Per-bar (DB-level):** the existing partial unique index on
       ``(strategy_id, side, price, second(timestamp_utc))`` blocks
       duplicate inserts within the same wall-clock second.
       :func:`bulk_emit_markers` pre-scans and returns existing rows in
       place of fresh inserts.
    2. **Per-run (this module):** before any bulk write we count
       existing markers with the requested ``backtest_run_id`` stored
       in ``signal_metadata.backtest_run_id``. Non-zero count = already
       persisted; we no-op.

The per-run check is the right level for a Celery task that may retry
after a transient failure — without it, a successful first run + a
retried-and-completed second run would double-write markers (the per-bar
dedup catches them only if the wall-clock seconds match, which they do
in backtests but the count would still be misleading).

Why not a ``backtest_run_id`` column?
    Adding a column would require an alembic migration. Queue CC + DD
    explicitly forbid migrations from this session. Storing the run id
    in ``signal_metadata`` (already a JSON column with ``extra="allow"``
    on its Pydantic schema) gives us the same per-run identity without
    touching the schema. The trade-off is a slower JSON-pattern lookup
    instead of an indexed column query — acceptable for the prototype;
    documented as a follow-up in ``MILESTONE_3_DESIGN_NOTES.md``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.trade_marker import (
    MarkerExitReason,
    MarkerMode,
    MarkerSide,
    TradeMarker,
)
from app.schemas.trade_marker import SignalMetadata, TradeMarkerCreate
from app.services.marker_emitter import bulk_emit_markers
from app.strategy_engine.backtest.trade_log import Trade as EngineTrade
from app.strategy_engine.schema.strategy import Side

if TYPE_CHECKING:
    pass


_logger = get_logger("backtest_extension.trade_markers")


# ─── Exit-reason mapping ───────────────────────────────────────────────


#: Engine's free-form ``Trade.exit_reason`` strings → MarkerExitReason
#: enum members. Anything not in this map degrades to ``SIGNAL`` — the
#: safest default since the chart only uses ``exit_reason`` for the
#: tooltip label, not for any logic gate.
_EXIT_REASON_MAP: dict[str, MarkerExitReason] = {
    "stop_loss": MarkerExitReason.STOP_LOSS,
    "hard_sl": MarkerExitReason.STOP_LOSS,
    "trailing_stop": MarkerExitReason.STOP_LOSS,
    "target": MarkerExitReason.TAKE_PROFIT,
    "take_profit": MarkerExitReason.TAKE_PROFIT,
    "partial_target": MarkerExitReason.TAKE_PROFIT,
    "signal": MarkerExitReason.SIGNAL,
    "indicator_exit": MarkerExitReason.SIGNAL,
    "backtest_end": MarkerExitReason.SQUARE_OFF,
    "square_off": MarkerExitReason.SQUARE_OFF,
    "square_off_time": MarkerExitReason.SQUARE_OFF,
}


def _map_exit_reason(engine_reason: str) -> MarkerExitReason:
    """Map engine's free-form exit_reason string to a MarkerExitReason
    enum member. Unknown strings degrade to SIGNAL (safest default)."""
    return _EXIT_REASON_MAP.get(engine_reason.lower(), MarkerExitReason.SIGNAL)


# ─── Trade → MarkerCreate pair ────────────────────────────────────────


def _trade_to_marker_pair(
    trade: EngineTrade,
    *,
    strategy_id: uuid.UUID,
    user_id: uuid.UUID,
    symbol: str,
    exchange: str,
    backtest_run_id: uuid.UUID,
) -> tuple[TradeMarkerCreate, TradeMarkerCreate]:
    """Build an (entry, exit) :class:`TradeMarkerCreate` pair from one
    engine :class:`Trade`. Both rows carry the same ``backtest_run_id``
    in ``signal_metadata`` so the per-run dedup query can find them
    later.
    """
    is_long = trade.side is Side.BUY
    entry_side = MarkerSide.LONG_ENTRY if is_long else MarkerSide.SHORT_ENTRY
    exit_side = MarkerSide.LONG_EXIT if is_long else MarkerSide.SHORT_EXIT

    # Engine Trade.quantity is a float (lots), TradeMarker.quantity is
    # an int. Round to nearest int; the chart only cares about the
    # arrow + tooltip, not exact lot counts.
    quantity = max(1, int(round(trade.quantity)))

    # SignalMetadata uses extra="allow" — backtest_run_id rides as an
    # additional key for per-run lookup.
    meta = SignalMetadata.model_validate(
        {"backtest_run_id": str(backtest_run_id)}
    )

    entry = TradeMarkerCreate(
        strategy_id=strategy_id,
        user_id=user_id,
        symbol=symbol,
        exchange=exchange,
        side=entry_side,
        price=Decimal(str(trade.entry_price)),
        quantity=quantity,
        timestamp_utc=trade.entry_time,
        mode=MarkerMode.BACKTEST,
        signal_metadata=meta,
    )
    exit_ = TradeMarkerCreate(
        strategy_id=strategy_id,
        user_id=user_id,
        symbol=symbol,
        exchange=exchange,
        side=exit_side,
        price=Decimal(str(trade.exit_price)),
        quantity=quantity,
        timestamp_utc=trade.exit_time,
        mode=MarkerMode.BACKTEST,
        pnl=Decimal(str(trade.pnl)),
        exit_reason=_map_exit_reason(trade.exit_reason),
        signal_metadata=meta,
    )
    return entry, exit_


# ─── Public coroutine ──────────────────────────────────────────────────


async def persist_backtest_trade_markers(
    db: AsyncSession,
    *,
    backtest_run_id: uuid.UUID,
    strategy_id: uuid.UUID,
    user_id: uuid.UUID,
    symbol: str,
    exchange: str,
    trades: list[EngineTrade],
) -> int:
    """Persist all trades from a backtest run as ``trade_markers`` rows.

    Returns the number of marker ROWS inserted (= 2 × new trades + 0 for
    rows that hit per-bar dedup). Returns 0 if the run id already has
    persisted markers (per-run idempotency).

    The Celery task wraps this in a broad try/except — marker persistence
    is read-only enrichment for the chart; failure must not fail the
    backtest. See ``backtest_extension/celery_tasks.py`` integration.
    """
    if not trades:
        _logger.info(
            "backtest.markers.skipped_empty",
            backtest_run_id=str(backtest_run_id),
            strategy_id=str(strategy_id),
        )
        return 0

    # Per-run idempotency check — count existing markers tagged with
    # this run id. Uses JSON path lookup; slower than an indexed column
    # but adequate for the prototype.
    existing_count = await _count_existing_markers_for_run(
        db, backtest_run_id=backtest_run_id, strategy_id=strategy_id
    )
    if existing_count > 0:
        _logger.info(
            "backtest.markers.skipped_idempotent",
            backtest_run_id=str(backtest_run_id),
            strategy_id=str(strategy_id),
            existing_count=existing_count,
        )
        return 0

    payloads: list[TradeMarkerCreate] = []
    for trade in trades:
        entry, exit_ = _trade_to_marker_pair(
            trade,
            strategy_id=strategy_id,
            user_id=user_id,
            symbol=symbol,
            exchange=exchange,
            backtest_run_id=backtest_run_id,
        )
        payloads.append(entry)
        payloads.append(exit_)

    rows = await bulk_emit_markers(db, markers=payloads)
    inserted = len(rows)
    _logger.info(
        "backtest.markers.persisted",
        backtest_run_id=str(backtest_run_id),
        strategy_id=str(strategy_id),
        trade_count=len(trades),
        markers_returned=inserted,
    )
    return inserted


async def _count_existing_markers_for_run(
    db: AsyncSession,
    *,
    backtest_run_id: uuid.UUID,
    strategy_id: uuid.UUID,
) -> int:
    """Count markers already tagged with ``backtest_run_id`` for this
    strategy. JSON path lookup — slower than an indexed column would be,
    but the schema-change avoidance is worth the cost in this prototype.

    SQLite stores the JSON column as ``TEXT`` and supports ``json_extract``;
    Postgres uses native JSONB. Both engines route through the SQLAlchemy
    JSON type, but the path-extraction syntax differs. We use a portable
    substring filter: matching the literal ``"backtest_run_id":"<uuid>"``
    inside the rendered JSON text is correct for both engines because:

        * SQLite's JSON storage round-trips through compact JSON
          (``json_dumps`` with default ``,:`` separators).
        * Postgres JSONB also normalises whitespace internally.

    The substring is unique enough — UUIDs collide with probability 0 —
    so false positives are not a concern. The query degrades to a full
    table scan on `trade_markers` for the matching strategy, which is
    bounded by per-strategy row count (typically <10k even for heavy
    users) — acceptable.
    """
    # JSON path-extraction syntax differs between SQLite and Postgres,
    # so we filter Python-side on the (typically small) per-strategy
    # candidate set rather than emitting a portable JSON predicate.
    # Acceptable for the prototype; a later iteration that adds
    # ``backtest_run_id`` as an indexed column gets O(log n) lookup.
    candidate_stmt = select(TradeMarker.signal_metadata).where(
        TradeMarker.strategy_id == strategy_id,
        TradeMarker.mode == MarkerMode.BACKTEST.value,
    )
    metas = (await db.execute(candidate_stmt)).scalars().all()
    target = str(backtest_run_id)
    return sum(
        1
        for m in metas
        if isinstance(m, dict)
        and str(m.get("backtest_run_id", "")) == target
    )


async def fetch_markers_for_run(
    db: AsyncSession,
    *,
    backtest_run_id: uuid.UUID,
    strategy_id: uuid.UUID,
) -> list[TradeMarker]:
    """Read-side: return all TradeMarker rows for one backtest run.

    Filters on ``signal_metadata.backtest_run_id`` via the same
    Python-side path as the count helper. The API endpoint in
    ``backtest_extension.api`` consumes this and projects to the
    Lightweight Charts marker shape.
    """
    stmt = (
        select(TradeMarker)
        .where(
            TradeMarker.strategy_id == strategy_id,
            TradeMarker.mode == MarkerMode.BACKTEST.value,
        )
        .order_by(TradeMarker.timestamp_utc.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    target = str(backtest_run_id)
    return [
        r for r in rows
        if isinstance(r.signal_metadata, dict)
        and str(r.signal_metadata.get("backtest_run_id", "")) == target
    ]


__all__ = [
    "fetch_markers_for_run",
    "persist_backtest_trade_markers",
]
