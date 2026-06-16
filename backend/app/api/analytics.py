"""Read-only analytics aggregation over a user's FULL trade history.

Additive endpoint — does not touch any existing route or trading logic.
The existing ``/api/users/me/trades`` (recent list) and
``/api/users/me/trades/stats`` (lightweight counts) stay untouched; this
adds a full-history rollup the ``/analytics`` page can render (P&L over
time, win rate, per-symbol breakdown) without re-fetching every trade
client-side.

Read-only: SELECT-only aggregates filtered by the caller's ``user_id``,
over FILLED trades that carry a realized P&L. No writes, no broker, no
network.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.models.trade import Trade, TradeStatus
from app.db.models.user import User
from app.db.session import get_session

router = APIRouter(prefix="/api/users/me/analytics", tags=["analytics"])


def _f(value: Decimal | int | float | None) -> float:
    """Coerce a possibly-None Numeric/Decimal aggregate to a JSON float."""
    return float(value) if value is not None else 0.0


@router.get("/summary")
async def analytics_summary(
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Full-history trade analytics for the caller.

    Aggregates over ALL of the user's FILLED trades with a realized P&L:
    headline totals, win/loss split, best/worst, a per-symbol breakdown
    (top by trade count), and a monthly realized-P&L series for charting.
    """
    # "Closed" trades that carry a realized P&L — the terminal states that
    # produce a settled result (normal close + kill-switch square-off).
    base = (
        select(Trade)
        .where(Trade.user_id == user.id)
        .where(Trade.status.in_([TradeStatus.COMPLETE, TradeStatus.SQUARED_OFF]))
        .where(Trade.pnl_realized.is_not(None))
        .subquery()
    )

    # ── Headline rollup (single aggregate row) ────────────────────────
    win = case((base.c.pnl_realized > 0, 1), else_=0)
    loss = case((base.c.pnl_realized < 0, 1), else_=0)
    headline = (
        await db.execute(
            select(
                func.count().label("trades"),
                func.coalesce(func.sum(base.c.pnl_realized), 0).label("total_pnl"),
                func.coalesce(func.sum(win), 0).label("wins"),
                func.coalesce(func.sum(loss), 0).label("losses"),
                func.max(base.c.pnl_realized).label("best"),
                func.min(base.c.pnl_realized).label("worst"),
            )
        )
    ).one()

    total_trades = int(headline.trades or 0)
    wins = int(headline.wins or 0)
    losses = int(headline.losses or 0)
    decided = wins + losses
    win_rate = round(wins / decided * 100, 2) if decided else 0.0

    # ── Per-symbol breakdown (top 20 by trade count) ──────────────────
    by_symbol_rows = (
        await db.execute(
            select(
                base.c.symbol,
                func.count().label("trades"),
                func.coalesce(func.sum(base.c.pnl_realized), 0).label("pnl"),
            )
            .group_by(base.c.symbol)
            .order_by(func.count().desc())
            .limit(20)
        )
    ).all()

    # ── Monthly realized-P&L series (ascending) ───────────────────────
    month = func.to_char(func.date_trunc("month", base.c.filled_at), "YYYY-MM")
    by_month_rows = (
        await db.execute(
            select(
                month.label("month"),
                func.count().label("trades"),
                func.coalesce(func.sum(base.c.pnl_realized), 0).label("pnl"),
            )
            .where(base.c.filled_at.is_not(None))
            .group_by(month)
            .order_by(month.asc())
        )
    ).all()

    return {
        "total_trades": total_trades,
        "total_realized_pnl": _f(headline.total_pnl),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": win_rate,
        "best_trade_pnl": _f(headline.best),
        "worst_trade_pnl": _f(headline.worst),
        "by_symbol": [
            {"symbol": r.symbol, "trades": int(r.trades), "realized_pnl": _f(r.pnl)}
            for r in by_symbol_rows
        ],
        "by_month": [
            {"month": r.month, "trades": int(r.trades), "realized_pnl": _f(r.pnl)}
            for r in by_month_rows
        ],
    }


__all__ = ["router"]
