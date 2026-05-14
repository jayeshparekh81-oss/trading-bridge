"""Chart-markers service — assembles ChartMarker lists from paper-trading rows.

Day-3 sprint. The ``app.api.chart_markers`` route delegates the read
path here so the route layer stays a thin HTTP shell. Two public
entry points:

    * :func:`classify_exit` — pure function mapping a paper-trade's
      ``exit_reason`` string into the ChartMarker four-way taxonomy.
      Centralised so a future :class:`ExitType` addition only changes
      one line.
    * :func:`build_markers_for_strategy` — given ``(user_id,
      strategy_id, symbol, from_ts, to_ts)`` and an :class:`AsyncSession`,
      produce a flat ``list[ChartMarker]`` ordered by timestamp.

Module status (Day 3 prep / scaffold)
    Reachable only from :mod:`app.api.chart_markers`, which is itself
    NOT registered in ``main.py`` until Day 3 dispatch — see
    ``frontend/PATCH_INSTRUCTIONS_FRONTEND_DAY3.md``.

Read-path contract
    1. ``list_sessions(user_id, strategy_id)`` — every paper session
       the user owns for the strategy, oldest first.
    2. For each session, ``list_trades(session_id)`` — every closed
       paper trade in that session, oldest first. Open trades (the
       engine writes them with ``exit_at IS NULL``) emit only an
       ENTRY marker.
    3. Filter by symbol (engine may multiplex multiple symbols inside
       one session, though current use is single-symbol per strategy).
    4. Filter by ``from_ts <= entry_at`` and ``exit_at <= to_ts``
       (or ``entry_at <= to_ts`` for open trades).
    5. Sort the final flat list by ``timestamp`` ascending so the
       chart overlay can stream-render them left-to-right.

The trade-row → marker fan-out happens entirely in memory. Even at
the live-orders 7-session quota × ~5 trades/session × 2 markers/trade
= 70 markers per strategy, the response payload is tiny — no
streaming or cursoring needed.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.paper_trade import PaperTrade as PaperTradeRow
from app.schemas.chart_marker import ChartMarker, ChartMarkerKind
from app.strategy_engine.paper_trading.store import (
    list_sessions,
    list_trades,
)


# ─── Exit-reason vocabulary ────────────────────────────────────────────
#
# Source-of-truth: ``app.strategy_engine.engines.exit.ExitType``.
#   class ExitType(StrEnum):
#       TARGET = "target"
#       STOP_LOSS = "stop_loss"
#       TRAILING_STOP = "trailing_stop"
#       PARTIAL = "partial"
#       INDICATOR = "indicator"
#       REVERSE_SIGNAL = "reverse_signal"
#       TIME = "time"
#       SQUARE_OFF = "square_off"
#
# Backtest also writes the literal ``"backtest_end"`` (see
# ``app.strategy_engine.backtest.simulator``) for end-of-data closes.
# Anything not in the explicit lists below collapses to EXIT — the
# safe default so a future ExitType addition does not break the route.

_TP_REASONS: Final[frozenset[str]] = frozenset({"target"})
_SL_REASONS: Final[frozenset[str]] = frozenset(
    {"stop_loss", "trailing_stop"}
)


def classify_exit(exit_reason: str | None) -> ChartMarkerKind:
    """Map a ``paper_trades.exit_reason`` string to a marker kind.

    ``None`` (open trade with no exit yet) is not a valid input — the
    caller emits only the ENTRY marker for open trades and never
    invokes this. A defensive ``None`` here returns EXIT to keep the
    function total without raising.
    """
    if exit_reason is None:
        return ChartMarkerKind.EXIT
    if exit_reason in _TP_REASONS:
        return ChartMarkerKind.TP_HIT
    if exit_reason in _SL_REASONS:
        return ChartMarkerKind.SL_HIT
    return ChartMarkerKind.EXIT


def _markers_for_trade(
    trade: PaperTradeRow,
    *,
    from_ts: datetime,
    to_ts: datetime,
    symbol: str,
) -> list[ChartMarker]:
    """Fan one DB row out to its 1 or 2 markers.

    Closed trade  → [ENTRY at entry_at, <exit-kind> at exit_at]
    Open trade    → [ENTRY at entry_at]

    Trades whose entry sits outside ``[from_ts, to_ts]`` are dropped
    entirely (the chart window doesn't include their visual anchor).
    Trades whose entry is in-window but whose exit overshoots the
    upper bound are kept with the entry marker only — the chart
    overlay shows where the position opened even if the exit fell
    past the visible range.
    """
    if trade.symbol.upper() != symbol.upper():
        return []
    if trade.entry_at < from_ts or trade.entry_at > to_ts:
        return []

    entry = ChartMarker(
        kind=ChartMarkerKind.ENTRY,
        timestamp=trade.entry_at,
        price=Decimal(trade.entry_price),
        quantity=int(trade.quantity),
        side=trade.side,
        pnl=None,
        exit_reason=None,
    )
    out: list[ChartMarker] = [entry]

    # Open trade — exit_at IS NULL, no exit marker yet.
    if trade.exit_at is None or trade.exit_price is None:
        return out
    if trade.exit_at > to_ts:
        return out

    out.append(
        ChartMarker(
            kind=classify_exit(trade.exit_reason),
            timestamp=trade.exit_at,
            price=Decimal(trade.exit_price),
            quantity=int(trade.quantity),
            side=trade.side,
            pnl=Decimal(trade.pnl) if trade.pnl is not None else None,
            exit_reason=trade.exit_reason,
        )
    )
    return out


async def build_markers_for_strategy(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
    symbol: str,
    from_ts: datetime,
    to_ts: datetime,
) -> list[ChartMarker]:
    """Top-level read path used by the route handler.

    Walks every paper session the user has for ``strategy_id``, fans
    each session's trades into markers via :func:`_markers_for_trade`,
    and returns a single timestamp-sorted list.

    Sessions are walked sequentially (each session's trade-list query
    is independent, so :func:`asyncio.gather` is used to parallelise
    the per-session fetches). At the live-orders 7-session minimum
    that's at most 7 concurrent ``SELECT`` queries — well within
    Postgres connection pool comfort.

    Raises no exceptions — empty input → empty output. Authorisation
    (the user owns the strategy) is the caller's job; this service
    layer is dumb-by-design about identity.
    """
    sessions = await list_sessions(
        db, user_id=user_id, strategy_id=strategy_id
    )
    if not sessions:
        return []

    trade_lists = await asyncio.gather(
        *(list_trades(db, session_id=s.id) for s in sessions)
    )

    out: list[ChartMarker] = []
    for trades in trade_lists:
        for trade in trades:
            out.extend(
                _markers_for_trade(
                    trade,
                    from_ts=from_ts,
                    to_ts=to_ts,
                    symbol=symbol,
                )
            )
    out.sort(key=lambda m: m.timestamp)
    return out


__all__ = [
    "build_markers_for_strategy",
    "classify_exit",
]
