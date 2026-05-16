"""Chart-markers HTTP route — Day 3 prep / scaffold.

Single endpoint:

    GET /api/chart/markers
        ?strategy_id=<uuid>
        &symbol=<str>
        &timeframe=<str>
        &from=<iso8601>
        &to=<iso8601>

Returns :class:`ChartMarkersResponse` — a flat list of paper-trading
ENTRY / EXIT / SL_HIT / TP_HIT markers within the requested window.

Module status (Day 3 prep / scaffold)
    This router is **not** registered in ``main.py`` yet — see
    ``frontend/PATCH_INSTRUCTIONS_FRONTEND_DAY3.md`` for the manual
    ``include_router`` line. The intent is to lock the wire contract
    today (so frontend Phase-7 can scaffold against a fixed schema
    and tests can lock the route surface) without exposing an
    unfinished feature on the live API surface. The route is fully
    implemented + tested; only the wire-up step is deferred.

Auth + authorisation
    * JWT via ``get_current_active_user`` — same dependency every
      other authenticated route uses.
    * Strategy ownership: the user MUST own the requested
      ``strategy_id`` (Strategy.user_id == user.id). 403 otherwise.
      Returning 404 would leak existence; 403 says "you can't see
      this" without confirming whether the strategy exists.

Caching
    Redis 5-minute cache, key derived from
    ``markers:{user_id}:{strategy_id}:{symbol}:{timeframe}:{from_epoch}:{to_epoch}``.
    The ``user_id`` prefix is mandatory — without it, a cache hit
    populated by the owner would be served to any other
    authenticated caller who guessed the same ``strategy_id``,
    bypassing the ownership check on the cache-hit branch (safety
    fix #4, 2026-05-16). Same TTL choice as
    :func:`app.api.chart.get_chart_history` — paper-trading data
    lives the full session, so a 5-min stale window is safe and
    cuts DB load when an operator pans a chart. Read-side parsing
    uses ``model_validate_json`` per the chart-module READ-SIDE
    CONTRACT documented in :mod:`app.services.chart_redis`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import bind_request_context, get_logger
from app.core.redis_client import cache_get, cache_set
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.chart_marker import ChartMarkersResponse
from app.services.chart_marker_service import build_markers_for_strategy


_logger = get_logger("api.chart_markers")


# ─── Constants ─────────────────────────────────────────────────────────


#: Cache TTL for marker responses. Mirrors the 5-minute window used by
#: ``GET /api/chart/history`` — same balance of freshness vs DB load.
_MARKERS_CACHE_TTL_S = 300


# ─── Router (deliberately UNREGISTERED in main.py) ────────────────────


#: To wire this up at Day 3 dispatch, add the following next to the
#: other ``app.include_router`` calls in ``backend/app/main.py``::
#:
#:     from app.api.chart_markers import router as chart_markers_router
#:     app.include_router(chart_markers_router)
#:
#: Documented in ``frontend/PATCH_INSTRUCTIONS_FRONTEND_DAY3.md`` so
#: the operator can apply both the backend and frontend changes in
#: one pass.
router = APIRouter(tags=["chart-markers"])


# ─── Helpers ───────────────────────────────────────────────────────────


def _markers_cache_key(
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
    symbol: str,
    timeframe: str,
    from_ts: datetime,
    to_ts: datetime,
) -> str:
    """Deterministic per-user cache key. Epoch-second buckets in the
    key (not ISO strings) so two callers asking for the same window
    with different timezone formatting still hit the same cache
    entry — same convention as :func:`app.api.chart._history_cache_key`.

    ``user_id`` is the FIRST component so two different users
    requesting the same ``strategy_id`` get disjoint cache entries.
    The route still runs the ownership check on the cache-miss
    path; partitioning by user_id closes the gap on the cache-hit
    path where the ownership check is skipped (safety fix #4,
    2026-05-16).
    """
    return (
        f"markers:{user_id}:{strategy_id}:{symbol.upper()}:{timeframe}:"
        f"{int(from_ts.timestamp())}:{int(to_ts.timestamp())}"
    )


async def _resolve_strategy_owned_by_user(
    db: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    user: User,
) -> Strategy:
    """Load the strategy and assert the requesting user owns it.

    Raises:
        HTTPException 403: Strategy does not exist OR exists but is
            owned by another user. We deliberately collapse the two
            cases into one 403 so existence cannot be probed by a
            sequence of guess-and-check requests.
    """
    stmt = select(Strategy).where(Strategy.id == strategy_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None or row.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Is strategy ke markers dekhne ka access nahi hai. "
                "Strategy ID confirm karo aur apni login session check karo."
            ),
        )
    return row


# ─── Endpoint ──────────────────────────────────────────────────────────


@router.get("/api/chart/markers", response_model=ChartMarkersResponse)
async def get_chart_markers(
    strategy_id: Annotated[uuid.UUID, Query(...)],
    symbol: Annotated[str, Query(min_length=1, max_length=64)],
    timeframe: Annotated[str, Query(min_length=1, max_length=8)],
    from_ts: Annotated[datetime, Query(alias="from")],
    to_ts: Annotated[datetime, Query(alias="to")],
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> ChartMarkersResponse:
    """Return paper-trading markers for ``strategy_id`` in the window.

    See module docstring for the full contract.
    """
    bind_request_context(
        user_id=str(user.id),
        symbol=symbol.upper(),
        strategy_id=str(strategy_id),
    )

    if from_ts.tzinfo is None or to_ts.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "from + to dono ISO 8601 timezone-aware hone chahiye "
                "(e.g. 2026-01-01T09:15:00+05:30)."
            ),
        )
    if from_ts > to_ts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from is greater than to — invalid window.",
        )

    sym = symbol.strip().upper()
    cache_key = _markers_cache_key(
        user.id, strategy_id, sym, timeframe, from_ts, to_ts
    )

    cached_str = await cache_get(cache_key)
    if cached_str is not None:
        try:
            cached_resp = ChartMarkersResponse.model_validate_json(
                cached_str
            )
            return cached_resp.model_copy(update={"cached": True})
        except ValidationError:
            _logger.warning(
                "chart.markers.cache_corrupt",
                cache_key=cache_key,
                strategy_id=str(strategy_id),
            )
            # Fall through to a fresh build; cache will be overwritten.

    # Authorisation is the only DB call we need before building — the
    # service layer is permission-blind so we MUST NOT skip this.
    await _resolve_strategy_owned_by_user(
        db, strategy_id=strategy_id, user=user
    )

    markers = await build_markers_for_strategy(
        db,
        user_id=user.id,
        strategy_id=strategy_id,
        symbol=sym,
        from_ts=from_ts,
        to_ts=to_ts,
    )

    response = ChartMarkersResponse(
        strategy_id=str(strategy_id),
        symbol=sym,
        timeframe=timeframe,
        from_ts=from_ts,
        to_ts=to_ts,
        cached=False,
        markers=markers,
    )

    try:
        await cache_set(
            cache_key,
            response.model_dump_json(),
            ttl_seconds=_MARKERS_CACHE_TTL_S,
        )
    except Exception as exc:  # noqa: BLE001
        # A cache write failure must NEVER fail the request. Log + carry on.
        _logger.warning(
            "chart.markers.cache_set_failed",
            cache_key=cache_key,
            error=type(exc).__name__,
        )

    return response


__all__ = ["router"]
