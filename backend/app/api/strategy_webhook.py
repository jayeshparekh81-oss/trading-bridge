"""Strategy-engine webhook receiver — TradingView → AI gate → executor.

Distinct from the legacy :mod:`app.api.webhook` endpoint at
``POST /api/webhook/{token}`` which fires a single broker order
synchronously. This new endpoint at ``POST /api/webhook/strategy/{token}``
runs the strategy engine pipeline:

    1. Token lookup (reuse the existing webhook_tokens infra).
    2. HMAC verification — header X-Signature OR ``signature`` field in
       the JSON body. TradingView free tier can't always send custom
       headers, so the in-body fallback keeps the door open.
    3. Time-of-day guard — outside 09:15-15:25 IST, reject with 403.
    4. Quantity ceiling — reject anything > 4 lots.
    5. Persist a :class:`StrategySignal` row with status='received'.
    6. Schedule background processing: AI validation → executor.
    7. Return 202 Accepted with the signal_id immediately.

The endpoint never blocks on the executor — TradingView times out fast
and we want the audit row written even if the broker is slow.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, time
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.api.webhook import _resolve_webhook_token
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import verify_hmac_signature
from app.db.models.strategy import Strategy
from app.db.models.strategy_signal import StrategySignal
from app.db.session import get_session

logger = get_logger("app.api.strategy_webhook")

router = APIRouter(prefix="/api/webhook/strategy", tags=["strategy-webhook"])

#: Hard quantity ceiling. Mirrors strategy_executor.QUANTITY_CEILING but
#: enforced here so a malformed signal never even hits the executor.
QUANTITY_CEILING = 4

#: IST trading window. Outside this we reject signals to avoid accidental
#: overnight orders. The AI validator is a second-line defence.
_IST = ZoneInfo("Asia/Kolkata")
_MARKET_OPEN = time(9, 15)
_MARKET_CLOSE = time(15, 25)

#: Header name TradingView sends. We also accept ``signature`` inside the JSON body.
HMAC_HEADER = "X-Signature"


@router.post(
    "/{webhook_token}",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Malformed JSON or quantity > ceiling"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid HMAC signature"},
        status.HTTP_403_FORBIDDEN: {"description": "Outside market hours"},
        status.HTTP_404_NOT_FOUND: {"description": "Unknown webhook token"},
        status.HTTP_409_CONFLICT: {"description": "Duplicate signal"},
    },
)
async def receive_strategy_signal(
    request: Request,
    background: BackgroundTasks,
    webhook_token: str = Path(..., min_length=16, max_length=128),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Accept a TradingView strategy alert and queue it for AI validation."""
    raw_body = await request.body()

    # 1. Token lookup — reuse legacy webhook resolver (Redis cache + DB fallback)
    token_info = await _resolve_webhook_token(session, webhook_token)
    if token_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown webhook token.",
        )
    user_id: UUID = token_info["user_id"]
    hmac_secret: str = token_info["hmac_secret"]
    token_id: UUID = token_info["token_id"]

    # 2. Parse JSON body — needed before HMAC verify because the
    #    in-body signature must be stripped before signing.
    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON body: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Body must be a JSON object.",
        )

    # 3. HMAC — header preferred, body fallback
    signature_header = request.headers.get(HMAC_HEADER, "")
    body_signature = str(payload.pop("signature", ""))

    if signature_header:
        if not verify_hmac_signature(raw_body, signature_header, hmac_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid HMAC signature (header).",
            )
    elif body_signature:
        # Re-sign the body without the signature key — must match
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        if not verify_hmac_signature(canonical, body_signature, hmac_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid HMAC signature (body).",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Missing HMAC signature. Send X-Signature header OR include "
                "a 'signature' field in the JSON body."
            ),
        )

    # 4. Time-of-day guard (bypassed in paper mode for off-hours testing)
    if get_settings().strategy_paper_mode:
        logger.info("time_of_day_check_bypassed_paper_mode")
    else:
        now_ist = datetime.now(_IST).time()
        if not (_MARKET_OPEN <= now_ist <= _MARKET_CLOSE):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Outside market hours (09:15-15:25 IST). Local now: {now_ist}."
                ),
            )

    # 5. Extract structured fields
    symbol = str(payload.get("symbol", "")).strip()
    action_raw = str(payload.get("action", "")).strip().upper()
    if not symbol or action_raw not in ("BUY", "SELL", "EXIT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload requires non-empty 'symbol' and action in {BUY,SELL,EXIT}.",
        )

    try:
        quantity = int(payload.get("quantity") or 0)
    except (TypeError, ValueError):
        quantity = 0
    if quantity <= 0:
        # Default to strategy.entry_lots downstream — leave NULL for now
        quantity_to_persist: int | None = None
    elif quantity > QUANTITY_CEILING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quantity {quantity} exceeds ceiling {QUANTITY_CEILING}.",
        )
    else:
        quantity_to_persist = quantity

    # 6. Resolve strategy linked to this webhook
    strategy_id = await _resolve_strategy_id(
        session, user_id=user_id, webhook_token_id=token_id
    )
    if strategy_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No active strategy is bound to this webhook token. Create "
                "one (with broker_credential_id) before sending alerts."
            ),
        )

    # 7. Persist signal row
    signal = StrategySignal(
        user_id=user_id,
        strategy_id=strategy_id,
        raw_payload=payload,
        symbol=symbol,
        action=action_raw,
        quantity=quantity_to_persist,
        order_type=str(payload.get("order_type") or "market"),
        status="received",
        received_at=datetime.now(UTC),
    )
    session.add(signal)
    await session.commit()
    await session.refresh(signal)

    # 8. Schedule async processing — never blocks the webhook response.
    #    EXIT is currently a no-op pending Day 6 work; we still record it.
    if action_raw != "EXIT":
        background.add_task(_process_signal_in_background, str(signal.id))

    logger.info(
        "strategy_webhook.signal_received",
        signal_id=str(signal.id),
        symbol=symbol,
        action=action_raw,
        quantity=quantity_to_persist,
    )
    return {
        "status": "accepted",
        "signal_id": str(signal.id),
        "strategy_id": str(strategy_id),
        "queued_for_processing": action_raw != "EXIT",
    }


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


async def _resolve_strategy_id(
    session: AsyncSession, *, user_id: UUID, webhook_token_id: UUID
) -> UUID | None:
    stmt = select(Strategy.id).where(
        Strategy.user_id == user_id,
        Strategy.webhook_token_id == webhook_token_id,
        Strategy.is_active.is_(True),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _process_signal_in_background(signal_id: str) -> None:
    """Run AI validator → executor in the background.

    Owns its own DB session — the request session is closed by the time
    BackgroundTasks fires. Errors are logged but never raised.
    """
    from app.db.session import get_sessionmaker
    from app.schemas.ai_decision import AIDecisionStatus
    from app.services.ai_validator import validate_signal
    from app.services.strategy_executor import (
        StrategyExecutorError,
        place_strategy_orders,
    )

    maker = get_sessionmaker()
    sid = UUID(signal_id)
    try:
        async with maker() as session:
            sig = await session.get(StrategySignal, sid)
            if sig is None:
                logger.warning("strategy_webhook.signal_missing", signal_id=signal_id)
                return
            strategy = await session.get(Strategy, sig.strategy_id)
            if strategy is None or not strategy.is_active:
                sig.status = "failed"
                sig.notes = "strategy missing or inactive"
                await session.commit()
                return

            sig.status = "validating"
            await session.commit()

            decision = await validate_signal(sig, strategy)

            sig.ai_decision = decision.decision.value
            sig.ai_reasoning = decision.reasoning
            sig.ai_confidence = decision.confidence
            sig.validated_at = datetime.now(UTC)

            if decision.decision is AIDecisionStatus.REJECTED:
                sig.status = "rejected"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                return

            sig.status = "executing"
            await session.commit()

            try:
                result = await place_strategy_orders(
                    session,
                    signal=sig,
                    strategy=strategy,
                    recommended_lots=decision.recommended_lots,
                )
                sig.status = "executed"
                sig.notes = (
                    f"position_id={result.position_id} "
                    f"broker_order_id={result.broker_order_id}"
                )
                sig.processed_at = datetime.now(UTC)
                await session.commit()
            except StrategyExecutorError as exc:
                sig.status = "failed"
                sig.notes = f"executor_error: {exc}"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
            except Exception as exc:
                logger.exception(
                    "strategy_webhook.executor_unexpected",
                    signal_id=signal_id,
                )
                sig.status = "failed"
                sig.notes = f"unexpected: {exc}"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
    except Exception:
        logger.exception(
            "strategy_webhook.background_failed", signal_id=signal_id
        )


def _signature_canonical(body: dict[str, Any]) -> bytes:
    """Helper kept for tests — sign the same bytes the verify path uses."""
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def _content_hash(payload: dict[str, Any]) -> str:
    """SHA-256 over the canonical body — useful for idempotency keys."""
    return hashlib.sha256(_signature_canonical(payload)).hexdigest()


__all__ = ["QUANTITY_CEILING", "router"]
