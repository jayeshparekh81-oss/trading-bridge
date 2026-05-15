"""Strategy-tester aggregation service — Phase B read-side over ``trade_markers``.

Three public coroutines + one pure helper, all over the Phase A
:class:`app.db.models.trade_marker.TradeMarker` table:

    * :func:`aggregate_metrics`     — report-card numbers (P&L, win-rate,
                                      profit factor, drawdown, Sharpe proxy,
                                      avg/largest win/loss, expectancy).
    * :func:`build_equity_curve`    — equity-by-trade time series with
                                      drawdown at each step.
    * :func:`get_trades`            — paginated trade list (entries paired
                                      with their linked exits; open trades
                                      surface with exit fields ``None``).
    * :func:`compute_drawdown_series` — pure helper; given a list of equity
                                        values returns peak-relative drawdown
                                        percentages.

Pairing model
    Trades are anchored on entry markers (``LONG_ENTRY`` / ``SHORT_ENTRY``).
    The exit marker stores ``linked_marker_id = entry.id`` (set by
    :func:`app.services.marker_emitter.emit_exit_marker`). Open trades
    are entries with no row pointing back at them. Orphan exits
    (``linked_marker_id IS NULL``) are skipped from the trade list but
    still contribute to ``aggregate_metrics`` and ``build_equity_curve``
    because they carry realised ``pnl`` — the chart's report card
    should reflect realised P&L regardless of pairing completeness.

Decimal hygiene
    Every monetary computation stays in ``Decimal`` until a float is
    structurally required (Sharpe, drawdown%, win-rate%). One
    conversion site per metric — the rest of the pipeline is exact.

Logging
    No per-trade logs in any loop. One ``_logger.info`` at the top of
    each public coroutine with cardinality fields (``user_id``,
    ``strategy_id``, ``mode``, ``trade_count``); error paths log once.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.trade_marker import (
    MarkerExitReason,
    MarkerMode,
    MarkerSide,
    TradeMarker,
)
from app.schemas.strategy_tester import (
    EquityCurveResponse,
    EquityPoint,
    StrategyTesterMetrics,
    TradeListResponse,
    TradePagination,
    TradeRecord,
)


_logger = get_logger("services.strategy_tester")


_ENTRY_SIDES: tuple[str, str] = (
    MarkerSide.LONG_ENTRY.value,
    MarkerSide.SHORT_ENTRY.value,
)
_EXIT_SIDES: tuple[str, str] = (
    MarkerSide.LONG_EXIT.value,
    MarkerSide.SHORT_EXIT.value,
)


# ─── Pure helpers ──────────────────────────────────────────────────────


def compute_drawdown_series(equity_points: Sequence[float]) -> list[float]:
    """Return peak-relative drawdown percentage at each equity step.

    Algorithm: scan once tracking running peak; at each point emit
    ``(peak - current) / peak * 100``, clamped to non-negative. A
    non-positive peak (degenerate case — caller passed all-zeros or
    negatives) yields ``0.0`` to avoid divide-by-zero. The shape of
    the returned list matches the input shape exactly.

    The function is pure and synchronous so it can be reused in tests
    and (later) in client-side equity-recompute paths without dragging
    in the DB layer.
    """
    if not equity_points:
        return []
    out: list[float] = []
    peak = float(equity_points[0])
    for value in equity_points:
        v = float(value)
        if v > peak:
            peak = v
        if peak > 0:
            dd = max(0.0, (peak - v) / peak * 100.0)
        else:
            dd = 0.0
        out.append(dd)
    return out


# ─── Internal query helpers ────────────────────────────────────────────


def _apply_window(stmt, *, from_ts: datetime | None, to_ts: datetime | None):
    """Append ``timestamp_utc`` window clauses if either bound is set."""
    if from_ts is not None:
        stmt = stmt.where(TradeMarker.timestamp_utc >= from_ts)
    if to_ts is not None:
        stmt = stmt.where(TradeMarker.timestamp_utc <= to_ts)
    return stmt


async def _fetch_exits_in_window(
    db: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    mode: MarkerMode,
    from_ts: datetime | None,
    to_ts: datetime | None,
) -> list[TradeMarker]:
    """All EXIT rows for one strategy + mode + window, ordered ascending.

    Includes orphan exits (``linked_marker_id IS NULL``) — their pnl
    contributes to realised metrics even though they have no entry to
    pair with.
    """
    stmt = (
        select(TradeMarker)
        .where(
            TradeMarker.strategy_id == strategy_id,
            TradeMarker.mode == mode.value,
            TradeMarker.side.in_(_EXIT_SIDES),
        )
        .order_by(TradeMarker.timestamp_utc.asc())
    )
    stmt = _apply_window(stmt, from_ts=from_ts, to_ts=to_ts)
    return list((await db.execute(stmt)).scalars().all())


async def _fetch_entries_in_window(
    db: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    mode: MarkerMode,
    from_ts: datetime | None,
    to_ts: datetime | None,
    symbol_filter: str | None = None,
) -> list[TradeMarker]:
    """All ENTRY rows for one strategy + mode + window, ordered ascending."""
    stmt = (
        select(TradeMarker)
        .where(
            TradeMarker.strategy_id == strategy_id,
            TradeMarker.mode == mode.value,
            TradeMarker.side.in_(_ENTRY_SIDES),
        )
        .order_by(TradeMarker.timestamp_utc.asc())
    )
    stmt = _apply_window(stmt, from_ts=from_ts, to_ts=to_ts)
    if symbol_filter is not None:
        stmt = stmt.where(TradeMarker.symbol == symbol_filter.upper())
    return list((await db.execute(stmt)).scalars().all())


async def _fetch_exits_for_entries(
    db: AsyncSession, entry_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, TradeMarker]:
    """Map ``entry_id → exit_row`` for a batch of entry ids.

    Done as one round-trip rather than N. Skips entries with no exit.
    If somehow two exits link to the same entry (shouldn't happen by
    business rule but the FK doesn't enforce uniqueness), the latest
    one by ``timestamp_utc`` wins.
    """
    if not entry_ids:
        return {}
    stmt = (
        select(TradeMarker)
        .where(
            TradeMarker.linked_marker_id.in_(list(entry_ids)),
            TradeMarker.side.in_(_EXIT_SIDES),
        )
        .order_by(TradeMarker.timestamp_utc.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    out: dict[uuid.UUID, TradeMarker] = {}
    for row in rows:
        if row.linked_marker_id is not None:
            out[row.linked_marker_id] = row  # later overwrites earlier
    return out


# ─── Trade-record construction ─────────────────────────────────────────


def _entry_side_to_position(entry_side: str) -> str:
    """``LONG_ENTRY`` → ``LONG``; ``SHORT_ENTRY`` → ``SHORT``.

    The schema constrains the trade-list ``side`` field to
    ``LONG`` / ``SHORT``; this is the one canonical mapping.
    """
    if entry_side == MarkerSide.LONG_ENTRY.value:
        return "LONG"
    if entry_side == MarkerSide.SHORT_ENTRY.value:
        return "SHORT"
    # Defensive: callers feed only entry rows, but if a stray exit
    # leaks through we surface it loudly rather than silently mislabel.
    raise ValueError(f"_entry_side_to_position called with non-entry side: {entry_side!r}")


def _build_trade_record(
    entry: TradeMarker, exit_row: TradeMarker | None
) -> TradeRecord:
    """Glue an entry marker (and optional exit) into one ``TradeRecord``."""
    side = _entry_side_to_position(entry.side)

    if exit_row is None:
        return TradeRecord(
            entry_marker_id=entry.id,
            exit_marker_id=None,
            symbol=entry.symbol,
            side=side,
            entry_time=entry.timestamp_utc,
            exit_time=None,
            entry_price=entry.price,
            exit_price=None,
            qty=entry.quantity,
            pnl=None,
            pnl_pct=None,
            duration_minutes=None,
            exit_reason=None,
        )

    duration_minutes = (
        (exit_row.timestamp_utc - entry.timestamp_utc).total_seconds() / 60.0
    )

    pnl_pct: float | None = None
    notional = entry.price * Decimal(entry.quantity)
    if exit_row.pnl is not None and notional > 0:
        pnl_pct = float(exit_row.pnl / notional) * 100.0

    exit_reason: MarkerExitReason | None = None
    if exit_row.exit_reason is not None:
        exit_reason = MarkerExitReason(exit_row.exit_reason)

    return TradeRecord(
        entry_marker_id=entry.id,
        exit_marker_id=exit_row.id,
        symbol=entry.symbol,
        side=side,
        entry_time=entry.timestamp_utc,
        exit_time=exit_row.timestamp_utc,
        entry_price=entry.price,
        exit_price=exit_row.price,
        qty=entry.quantity,
        pnl=exit_row.pnl,
        pnl_pct=pnl_pct,
        duration_minutes=duration_minutes,
        exit_reason=exit_reason,
    )


# ─── Metric primitives ─────────────────────────────────────────────────


def _compute_max_drawdown_pct(
    starting_equity: Decimal, ordered_pnls: Sequence[Decimal]
) -> float:
    """Walk pnls chronologically, return max peak-relative drawdown %.

    Uses the pure :func:`compute_drawdown_series` helper internally so
    drawdown semantics live in one place.
    """
    if not ordered_pnls:
        return 0.0
    equity = float(starting_equity)
    points: list[float] = [equity]
    for pnl in ordered_pnls:
        equity += float(pnl)
        points.append(equity)
    return max(compute_drawdown_series(points))


def _compute_sharpe_proxy(pnls: Sequence[Decimal]) -> float | None:
    """Per-trade Sharpe proxy: ``mean(pnl) / stdev(pnl)``.

    Returns ``None`` for fewer than 2 trades or zero variance — both
    cases yield an undefined ratio and the chart should render ``—``.
    Population stdev (N), not sample (N-1) — proxy doesn't claim to be
    a true Sharpe.
    """
    if len(pnls) < 2:
        return None
    floats = [float(p) for p in pnls]
    mean = sum(floats) / len(floats)
    variance = sum((x - mean) ** 2 for x in floats) / len(floats)
    if variance <= 0:
        return None
    stdev = math.sqrt(variance)
    return mean / stdev


# ─── Public coroutines ─────────────────────────────────────────────────


async def aggregate_metrics(
    *,
    strategy_id: uuid.UUID,
    mode: MarkerMode,
    from_ts: datetime | None,
    to_ts: datetime | None,
    db: AsyncSession,
    starting_equity: Decimal = Decimal("100000"),
) -> StrategyTesterMetrics:
    """Compute the report-card metrics for one strategy + mode.

    All metrics are derived from the EXIT rows (= closed trades) in the
    selected window. ``starting_equity`` is only used for the drawdown
    walk; it does NOT bias counts or P&L.
    """
    exits = await _fetch_exits_in_window(
        db,
        strategy_id=strategy_id,
        mode=mode,
        from_ts=from_ts,
        to_ts=to_ts,
    )

    # All-zeros shape when there are no closed trades in the window.
    if not exits:
        _logger.info(
            "strategy_tester.metrics.empty",
            strategy_id=str(strategy_id),
            mode=mode.value,
        )
        return StrategyTesterMetrics(
            total_pnl=Decimal("0"),
            win_rate_pct=0.0,
            profit_factor=None,
            total_trades=0,
            profitable_trades=0,
            max_drawdown_pct=0.0,
            sharpe_ratio_proxy=None,
            avg_win=Decimal("0"),
            avg_loss=Decimal("0"),
            largest_win=Decimal("0"),
            largest_loss=Decimal("0"),
            expectancy=Decimal("0"),
        )

    pnls: list[Decimal] = [e.pnl if e.pnl is not None else Decimal("0") for e in exits]
    total_trades = len(pnls)
    total_pnl = sum(pnls, start=Decimal("0"))

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    profitable_trades = len(wins)
    win_rate_pct = (profitable_trades / total_trades) * 100.0 if total_trades > 0 else 0.0

    gross_profit = sum(wins, start=Decimal("0"))
    gross_loss_abs = sum((-p for p in losses), start=Decimal("0"))
    if gross_loss_abs > 0:
        profit_factor: float | None = float(gross_profit / gross_loss_abs)
    elif gross_profit > 0:
        # All wins, no losses — undefined; surface as None.
        profit_factor = None
    else:
        # No trades produced positive P&L either; report 0 not None so
        # the frontend can distinguish "no losses + no wins" (a flat
        # series) from "all wins" (genuinely undefined ratio).
        profit_factor = 0.0

    avg_win = (gross_profit / Decimal(len(wins))) if wins else Decimal("0")
    avg_loss = (
        (sum(losses, start=Decimal("0")) / Decimal(len(losses))) if losses else Decimal("0")
    )
    largest_win = max(wins) if wins else Decimal("0")
    largest_loss = min(losses) if losses else Decimal("0")

    # Expectancy = (win% * avg_win) − ((1 − win%) * |avg_loss|).
    win_rate = Decimal(profitable_trades) / Decimal(total_trades)
    loss_rate = Decimal("1") - win_rate
    expectancy = (win_rate * avg_win) + (loss_rate * avg_loss)
    # ^ avg_loss is already negative, so adding (loss_rate * avg_loss)
    # subtracts the expected loss contribution. Equivalent to the
    # ``(p * W) − (q * |L|)`` form spelled out above.

    max_drawdown_pct = _compute_max_drawdown_pct(starting_equity, pnls)
    sharpe = _compute_sharpe_proxy(pnls)

    _logger.info(
        "strategy_tester.metrics.computed",
        strategy_id=str(strategy_id),
        mode=mode.value,
        total_trades=total_trades,
        profitable_trades=profitable_trades,
    )

    return StrategyTesterMetrics(
        total_pnl=total_pnl,
        win_rate_pct=win_rate_pct,
        profit_factor=profit_factor,
        total_trades=total_trades,
        profitable_trades=profitable_trades,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio_proxy=sharpe,
        avg_win=avg_win,
        avg_loss=avg_loss,
        largest_win=largest_win,
        largest_loss=largest_loss,
        expectancy=expectancy,
    )


async def build_equity_curve(
    *,
    strategy_id: uuid.UUID,
    mode: MarkerMode,
    starting_equity: Decimal,
    from_ts: datetime | None,
    to_ts: datetime | None,
    db: AsyncSession,
) -> EquityCurveResponse:
    """Construct the equity-vs-time series after each closed trade.

    The first point is always the starting-equity anchor at the window's
    earliest timestamp (or the first exit's timestamp when no
    ``from_ts`` was supplied). Each subsequent point sits at an exit
    marker's ``timestamp_utc`` with ``equity = previous + pnl``.
    Drawdown at each step is peak-relative percent.
    """
    exits = await _fetch_exits_in_window(
        db,
        strategy_id=strategy_id,
        mode=mode,
        from_ts=from_ts,
        to_ts=to_ts,
    )

    points: list[EquityPoint] = []
    equities: list[float] = []

    # Anchor point — pin to from_ts if supplied so the chart's x-axis
    # has a deterministic start; else pin to the first exit's timestamp
    # (or to "now" if no exits at all, but in that empty-anchor case
    # the frontend just sees a single flat point).
    if from_ts is not None:
        anchor_ts = from_ts
    elif exits:
        anchor_ts = exits[0].timestamp_utc
    else:
        # No exits AND no from_ts → return a single anchor with caller's
        # supplied starting_equity. Better than an empty list because
        # the frontend can still render an "empty" baseline.
        anchor_ts = datetime.now(tz=UTC)

    points.append(
        EquityPoint(
            timestamp=anchor_ts,
            equity=starting_equity,
            drawdown_pct=0.0,
            trade_id_or_none=None,
        )
    )
    equities.append(float(starting_equity))

    running_equity = starting_equity
    for ex in exits:
        pnl = ex.pnl if ex.pnl is not None else Decimal("0")
        running_equity = running_equity + pnl
        equities.append(float(running_equity))
        points.append(
            EquityPoint(
                timestamp=ex.timestamp_utc,
                equity=running_equity,
                drawdown_pct=0.0,  # patched below in one pass
                trade_id_or_none=ex.id,
            )
        )

    # Single drawdown pass over the whole equity series; rebuild points
    # with the computed drawdown injected. Avoids touching the immutable
    # frozen models in place.
    drawdowns = compute_drawdown_series(equities)
    points = [
        EquityPoint(
            timestamp=p.timestamp,
            equity=p.equity,
            drawdown_pct=dd,
            trade_id_or_none=p.trade_id_or_none,
        )
        for p, dd in zip(points, drawdowns, strict=True)
    ]

    ending_equity = points[-1].equity
    equity_decimals = [p.equity for p in points]
    max_equity = max(equity_decimals)
    min_equity = min(equity_decimals)

    _logger.info(
        "strategy_tester.equity_curve.built",
        strategy_id=str(strategy_id),
        mode=mode.value,
        point_count=len(points),
        trade_count=len(exits),
    )

    return EquityCurveResponse(
        points=points,
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        max_equity=max_equity,
        min_equity=min_equity,
    )


async def get_trades(
    *,
    strategy_id: uuid.UUID,
    mode: MarkerMode,
    from_ts: datetime | None,
    to_ts: datetime | None,
    limit: int,
    offset: int,
    db: AsyncSession,
    symbol_filter: str | None = None,
) -> TradeListResponse:
    """Paginated trade list anchored on entry markers.

    Open trades (entries with no linked exit yet) appear with
    ``exit_*`` and ``pnl*`` fields set to ``None``. Pagination is over
    the entry rowset — ``total`` is the unpaginated entry count so
    the frontend can render a page indicator without a second
    round-trip.
    """
    entries = await _fetch_entries_in_window(
        db,
        strategy_id=strategy_id,
        mode=mode,
        from_ts=from_ts,
        to_ts=to_ts,
        symbol_filter=symbol_filter,
    )
    total = len(entries)

    # Slice for pagination, then resolve exits for the slice only.
    page = entries[offset : offset + limit]
    exits_by_entry = await _fetch_exits_for_entries(db, [e.id for e in page])

    trades = [
        _build_trade_record(entry, exits_by_entry.get(entry.id)) for entry in page
    ]

    _logger.info(
        "strategy_tester.trades.listed",
        strategy_id=str(strategy_id),
        mode=mode.value,
        total=total,
        returned=len(trades),
        offset=offset,
        limit=limit,
    )

    return TradeListResponse(
        trades=trades,
        pagination=TradePagination(limit=limit, offset=offset, total=total),
        mode=mode,
    )


__all__ = [
    "aggregate_metrics",
    "build_equity_curve",
    "compute_drawdown_series",
    "get_trades",
]
