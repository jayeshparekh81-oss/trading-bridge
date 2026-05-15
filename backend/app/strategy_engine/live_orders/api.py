"""POST /api/orders/live — live broker order placement endpoint.

Thin FastAPI wrapper around :func:`place_live_order`. Translates the
orchestrator's typed exceptions into the right HTTP status codes:

    * ``LookupError`` (cross-user / unknown strategy) → 404 (matches
      the rest of the strategy endpoints — does not differentiate
      "missing" from "not yours" so the endpoint isn't an enumerator).
    * ``StrategyMissingBrokerCredentialError`` → 422 (the strategy is
      misconfigured, but the request itself was valid).
    * ``BrokerOfflineError`` → 503.
    * Any other :class:`BrokerError` from the typed broker hierarchy
      → 503 (transient) for connection/rate-limit, 422 (request bug)
      for invalid-symbol / insufficient-funds / rejected-order.

The endpoint never returns 4xx for a SafetyChain block — the chain's
verdict is rendered as a 200 with ``success=False`` and the
structured ``safety_chain_result`` so the frontend's pre-flight panel
can surface every check's status. **Spec calls for 403 on safety
block — that mapping is implemented here.**
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.exceptions import (
    BrokerConnectionError,
    BrokerError,
    BrokerInsufficientFundsError,
    BrokerInvalidSymbolError,
    BrokerOrderRejectedError,
    BrokerRateLimitError,
)
from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.live_orders.models import (
    LiveOrderRequest,
    LiveOrderResult,
    SafetyChainResult,
)
from app.strategy_engine.live_orders.order_router import (
    BrokerOfflineError,
    PaperModeActiveError,
    StrategyMissingBrokerCredentialError,
    place_live_order,
)
from app.strategy_engine.live_orders.safety_chain import run_safety_chain

logger = get_logger("app.strategy_engine.live_orders.api")

router = APIRouter(prefix="/api/orders", tags=["live-orders"])


@router.post(
    "/live",
    response_model=LiveOrderResult,
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Safety chain or broker guard blocked the order."},
        404: {"description": "Strategy not found or not owned by caller."},
        422: {"description": "Strategy misconfigured or broker rejected the request."},
        503: {"description": "Broker offline or session-expired retry failed."},
    },
)
async def post_live_order(
    request: LiveOrderRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> LiveOrderResult:
    """Place a live (real-money) order with the full SafetyChain.

    Per the spec:

        * 403 on SafetyChain or Broker Guard block (with check_name in
          the structured payload).
        * 503 on broker offline / session-expired retry failure.
        * 422 on broker-side validation failure (invalid symbol,
          insufficient funds, or strategy without a DSL).
        * 404 on cross-user enumeration / unknown strategy.

    Successful placements (live OR dry-run) return 200 with the full
    :class:`LiveOrderResult` body — ``success=True`` and ``order_id``
    populated.
    """
    try:
        result = await place_live_order(
            request,
            user_id=current_user.id,
            db_session=db,
        )
    except PaperModeActiveError as exc:
        # Safety fix #3: live orders refuse while the global paper-mode
        # gate is on. Map to 403 so the frontend modal can render the
        # SEBI-approval message in the same lane as SafetyChain blocks.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        # Cross-user probe / unknown id — same body as 'not found' so
        # the endpoint can't be used to enumerate strategy ids.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found.",
        ) from exc
    except StrategyMissingBrokerCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Strategy ke saath broker connect nahi hai. "
                "Brokers page se broker link karo, then strategy "
                "settings mein credential select karo."
            ),
        ) from exc
    except BrokerOfflineError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Broker session expired aur relogin fail ho gaya. "
                "Brokers page se refresh login karo."
            ),
        ) from exc
    except (BrokerConnectionError, BrokerRateLimitError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Broker connection issue: {exc}",
        ) from exc
    except (
        BrokerInvalidSymbolError,
        BrokerInsufficientFundsError,
        BrokerOrderRejectedError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except BrokerError as exc:
        # Any other typed broker error — surface as 503 since these
        # are the broker's "I cannot serve right now" signals.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Broker error: {exc}",
        ) from exc

    if not result.success:
        # SafetyChain or Broker Guard blocked. Spec maps this to 403
        # with the structured result in the body so the pre-flight UI
        # can render every check's verdict.
        logger.info(
            "live_order.blocked",
            user_id=str(current_user.id),
            strategy_id=str(request.strategy_id),
            blocking_check=(
                result.safety_chain_result.blocking_check.check_name
                if result.safety_chain_result.blocking_check
                else "broker_guard"
            ),
            reason=result.failure_reason_hinglish,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.model_dump(mode="json"),
        )

    logger.info(
        "live_order.placed",
        user_id=str(current_user.id),
        strategy_id=str(request.strategy_id),
        order_id=result.order_id,
        is_dry_run=result.is_dry_run,
    )
    return result


# ─── Pre-flight check ────────────────────────────────────────────────


@router.get(
    "/live/preflight",
    response_model=SafetyChainResult,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Strategy not found or not owned by caller."},
    },
)
async def get_live_preflight(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    strategy_id: Annotated[uuid.UUID, Query(...)],
) -> SafetyChainResult:
    """Run the SafetyChain without placing an order.

    The frontend pre-flight panel polls this on the strategy detail
    page so the user can see every safety check's status before
    clicking Go Live. Same checks, same fail-fast ordering as the
    full :func:`place_live_order` flow — just no broker call and no
    audit emission (calling this is a read-only surface; the audit
    trail belongs to actual order attempts).

    A SafetyChain block is **not** an HTTP error here — it is the
    expected output. The 200 response carries the full
    :class:`SafetyChainResult` so the UI renders every check's row,
    including the blocking one. 404 is reserved for cross-user /
    unknown strategy probes (matches the rest of the strategy
    endpoints' enumeration-guard pattern).
    """
    # Ownership check — same pattern the order endpoint uses.
    stmt = select(Strategy).where(
        Strategy.id == strategy_id,
        Strategy.user_id == current_user.id,
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found.",
        )

    return await run_safety_chain(
        user_id=current_user.id,
        strategy_id=strategy_id,
        db_session=db,
    )


__all__ = ["router"]
