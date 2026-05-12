"""Indicator API route — POST /api/chart/indicator.

main.py wiring (Jayesh applies manually per
``PATCH_INSTRUCTIONS_INDICATORS.md``)::

    from app.api.indicator import router as indicator_router  # noqa: E402
    app.include_router(indicator_router)

The route delegates the entire pipeline to
:func:`compute_indicator` — REST handler stays thin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import bind_request_context, get_logger
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.indicator import IndicatorRequest, IndicatorResponse
from app.services.indicator_service import compute_indicator


_logger = get_logger("api.indicator")


router = APIRouter(tags=["chart-indicator"])


@router.post(
    "/api/chart/indicator",
    response_model=IndicatorResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute a technical indicator over closed OHLC candles",
    description=(
        "Returns indicator values for **closed candles only**; the "
        "current in-progress bar is excluded. The response is cached "
        "per (symbol, timeframe, indicator, params, last_closed_bar) "
        "for 5 minutes. NaN / warm-up positions are returned as JSON "
        "`null`. Empty windows return 200 with an empty series — never "
        "400."
    ),
)
async def post_indicator(
    body: IndicatorRequest,
    request: Request,  # noqa: ARG001 — kept for future request-id binding
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> IndicatorResponse:
    bind_request_context(
        user_id=str(user.id),
        symbol=body.symbol,
        timeframe=body.timeframe.value,
        indicator=body.params.indicator.value,
    )
    return await compute_indicator(request=body, user=user, db=db)


__all__ = ["router"]
