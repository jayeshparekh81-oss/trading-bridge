"""HTTP routes for the Phase B strategy-tester aggregation API.

Three endpoints, all authenticated + ownership-gated:

    GET /api/strategy-tester/{strategy_id}/metrics
        ?mode=BACKTEST|PAPER|LIVE  (required)
        &from=<iso8601>            (optional, tz-aware)
        &to=<iso8601>              (optional, tz-aware)
        &starting_equity=<num>     (optional, default 100000; only
                                    affects max_drawdown_pct walk)
        → 200 :class:`StrategyTesterMetrics`

    GET /api/strategy-tester/{strategy_id}/equity
        ?mode=BACKTEST|PAPER|LIVE  (required)
        &starting_equity=<num>     (optional, default 100000)
        &from=<iso8601>            (optional, tz-aware)
        &to=<iso8601>              (optional, tz-aware)
        → 200 :class:`EquityCurveResponse`

    GET /api/strategy-tester/{strategy_id}/trades
        ?mode=BACKTEST|PAPER|LIVE  (required)
        &from=<iso8601>            (optional, tz-aware)
        &to=<iso8601>              (optional, tz-aware)
        &symbol=<str>              (optional, max 64 chars)
        &limit=<1..500>            (default 100)
        &offset=<int>              (default 0)
        → 200 :class:`TradeListResponse`

Auth + authorisation
    * JWT via ``get_current_active_user`` — same dep every other
      authenticated route uses.
    * Strategy ownership: the user MUST own ``strategy_id``. We
      collapse "doesn't exist" + "not yours" into one 403 so existence
      cannot be probed (mirrors the Phase A ``trade_markers`` route).

Router registration
    This router is **not** registered in ``main.py`` yet — see
    ``backend/PATCH_INSTRUCTIONS_PHASE_B.md`` for the manual
    ``include_router`` line. New-files-only rule on parallel-CC
    branches forbids editing shared files.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import bind_request_context, get_logger
from app.db.models.strategy import Strategy
from app.db.models.trade_marker import MarkerMode
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.strategy_tester import (
    EquityCurveResponse,
    StrategyTesterMetrics,
    TradeListResponse,
)
from app.services.strategy_tester_service import (
    aggregate_metrics,
    build_equity_curve,
    get_trades,
)


_logger = get_logger("api.strategy_tester")


router = APIRouter(prefix="/api/strategy-tester", tags=["strategy-tester"])


# ─── Helpers ───────────────────────────────────────────────────────────


async def _assert_strategy_owned_by_user(
    db: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    user: User,
) -> Strategy:
    """Load strategy + assert ownership.

    Existence + ownership collapse into one 403 so a sequence of
    guess-and-check requests can't probe whether a given strategy id
    exists. Same shape as the Phase A ``trade_markers`` router.
    """
    stmt = select(Strategy).where(Strategy.id == strategy_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None or row.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Is strategy ka tester data dekhne ka access nahi hai. "
                "Strategy ID confirm karo aur apni login session check karo."
            ),
        )
    return row


def _validate_time_window(
    from_ts: datetime | None,
    to_ts: datetime | None,
) -> None:
    """Reject naive timestamps and an inverted window. ``None`` is OK."""
    for label, ts in (("from", from_ts), ("to", to_ts)):
        if ts is not None and ts.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{label} ISO 8601 timezone-aware hona chahiye "
                    "(e.g. 2026-05-14T09:15:00+05:30)."
                ),
            )
    if from_ts is not None and to_ts is not None and from_ts > to_ts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from is greater than to — invalid window.",
        )


# ─── Endpoints ─────────────────────────────────────────────────────────


@router.get(
    "/{strategy_id}/metrics",
    response_model=StrategyTesterMetrics,
)
async def metrics(
    strategy_id: Annotated[uuid.UUID, Path(...)],
    mode: Annotated[MarkerMode, Query(...)],
    from_ts: Annotated[datetime | None, Query(alias="from")] = None,
    to_ts: Annotated[datetime | None, Query(alias="to")] = None,
    starting_equity: Annotated[Decimal, Query(gt=0)] = Decimal("100000"),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> StrategyTesterMetrics:
    """Report-card metrics over closed trades for one strategy + mode."""
    bind_request_context(
        user_id=str(user.id),
        strategy_id=str(strategy_id),
        mode=mode.value,
    )
    _validate_time_window(from_ts, to_ts)
    await _assert_strategy_owned_by_user(
        db, strategy_id=strategy_id, user=user
    )
    return await aggregate_metrics(
        strategy_id=strategy_id,
        mode=mode,
        from_ts=from_ts,
        to_ts=to_ts,
        db=db,
        starting_equity=starting_equity,
    )


@router.get(
    "/{strategy_id}/equity",
    response_model=EquityCurveResponse,
)
async def equity(
    strategy_id: Annotated[uuid.UUID, Path(...)],
    mode: Annotated[MarkerMode, Query(...)],
    starting_equity: Annotated[Decimal, Query(gt=0)] = Decimal("100000"),
    from_ts: Annotated[datetime | None, Query(alias="from")] = None,
    to_ts: Annotated[datetime | None, Query(alias="to")] = None,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> EquityCurveResponse:
    """Equity-by-trade time series with peak-relative drawdown at each step."""
    bind_request_context(
        user_id=str(user.id),
        strategy_id=str(strategy_id),
        mode=mode.value,
    )
    _validate_time_window(from_ts, to_ts)
    await _assert_strategy_owned_by_user(
        db, strategy_id=strategy_id, user=user
    )
    return await build_equity_curve(
        strategy_id=strategy_id,
        mode=mode,
        starting_equity=starting_equity,
        from_ts=from_ts,
        to_ts=to_ts,
        db=db,
    )


@router.get(
    "/{strategy_id}/trades",
    response_model=TradeListResponse,
)
async def trades(
    strategy_id: Annotated[uuid.UUID, Path(...)],
    mode: Annotated[MarkerMode, Query(...)],
    from_ts: Annotated[datetime | None, Query(alias="from")] = None,
    to_ts: Annotated[datetime | None, Query(alias="to")] = None,
    symbol: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> TradeListResponse:
    """Paginated trade list — entries paired with their exits.

    Open trades surface with ``exit_*`` and ``pnl*`` fields ``null``.
    """
    bind_request_context(
        user_id=str(user.id),
        strategy_id=str(strategy_id),
        mode=mode.value,
    )
    _validate_time_window(from_ts, to_ts)
    await _assert_strategy_owned_by_user(
        db, strategy_id=strategy_id, user=user
    )
    return await get_trades(
        strategy_id=strategy_id,
        mode=mode,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        offset=offset,
        db=db,
        symbol_filter=symbol,
    )


__all__ = ["router"]
