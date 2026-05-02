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
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.api.webhook import _resolve_webhook_token
from app.core import redis_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import verify_hmac_signature
from app.db.models.strategy import Strategy
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session
from app.services.kill_switch_service import kill_switch_service
from app.services.pine_mapper import (
    PineMappingError,
    is_pine_payload,
    map_to_tradetri_payload,
)

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

#: TTL for idempotency slots. Mirrors :mod:`app.api.webhook` — TradingView
#: retries the same alert inside ~30 s if our endpoint times out, so 60 s
#: covers the retry window without occupying Redis any longer than needed.
IDEMPOTENCY_TTL_SECONDS = 60

#: Webhook rate limit — fixed-window counter, per user (not per token), so
#: a customer with multiple tokens shares one bucket. Mirrors
#: :mod:`app.api.webhook` exactly: 60 requests per 60 s.
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

#: Actions the executor + position manager understand. BUY/SELL drive
#: entries; EXIT/SL_HIT/PARTIAL_LONG/PARTIAL_SHORT signal exits or
#: partials and never run the entry executor.
_ENTRY_ACTIONS: frozenset[str] = frozenset({"BUY", "SELL"})
_SUPPORTED_ACTIONS: frozenset[str] = frozenset(
    {"BUY", "SELL", "EXIT", "PARTIAL_LONG", "PARTIAL_SHORT", "SL_HIT"}
)


@router.post(
    "/{webhook_token}",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Malformed JSON or quantity > ceiling"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid HMAC signature"},
        status.HTTP_403_FORBIDDEN: {
            "description": "Kill switch tripped or outside market hours",
        },
        status.HTTP_404_NOT_FOUND: {"description": "Unknown webhook token"},
        status.HTTP_409_CONFLICT: {"description": "Duplicate signal"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Rate limit exceeded"},
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

    # 2. Rate limit — fixed-window counter, 60/min per user. Mirrors the
    #    legacy /api/webhook receiver: rejects spam BEFORE the CPU-heavy
    #    HMAC verify, since a single Redis INCR is cheaper than sha256.
    allowed = await redis_client.rate_limit_check(
        key=f"webhook:{user_id}",
        max_requests=RATE_LIMIT_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Webhook rate limit exceeded.",
        )

    # 3. Parse JSON body — needed before HMAC verify because the
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

    # 4. HMAC verify — with a TradingView IP allowlist bypass.
    #    TV's free tier cannot sign webhooks, so requests from their
    #    published egress IPs skip HMAC. Every other safety gate still
    #    runs (rate limit above, idempotency / kill switch / user-active
    #    / max-trades / time-of-day below). Spoofing-resistance: the
    #    middleware-resolved client IP only honours X-Forwarded-For
    #    when the immediate peer is a trusted proxy (configured CIDR).
    client_ip = _resolve_client_ip(request)
    tv_ips = set(get_settings().tradingview_trusted_ips)
    if client_ip and client_ip in tv_ips:
        logger.info(
            "strategy_webhook.tradingview_ip_bypass",
            client_ip=client_ip,
            user_id=str(user_id),
        )
        # Strip a stray ``signature`` field if present so it doesn't
        # bleed into idempotency hashing or business-logic reads.
        payload.pop("signature", None)
    else:
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

    # 5. Idempotency claim — Redis SET NX, 60 s TTL. Mirrors the legacy
    #    /api/webhook receiver: dedupe BEFORE business-logic gates so a
    #    TradingView retry sent at 15:25:30 IST is silently absorbed
    #    rather than confusingly rejected as "outside hours".
    signal_hash = _compute_strategy_signal_hash(user_id, payload, raw_body)
    claimed = await redis_client.set_idempotency_key(
        signal_hash, ttl_seconds=IDEMPOTENCY_TTL_SECONDS
    )
    if not claimed:
        logger.info(
            "strategy_webhook.duplicate_suppressed",
            signal_hash_prefix=signal_hash[:32],
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "duplicate",
                "message": "duplicate signal suppressed",
            },
        )

    # 6. Kill switch — operator emergency stop. Per-user Redis flag.
    #    Blocks both live AND paper trades; bypassing in paper mode would
    #    defeat the purpose of an emergency stop. Mirrors legacy
    #    /api/webhook ordering (kill-switch immediately after idempotency).
    kill_status = await redis_client.get_kill_switch_status(user_id)
    if kill_status == redis_client.KILL_SWITCH_TRIPPED:
        logger.info(
            "strategy_webhook.kill_switch_tripped", user_id=str(user_id)
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kill switch is TRIPPED — trading paused.",
        )

    # 7. User-active check (Gate B) — disabled accounts cannot trade.
    #    Single PK select on the request session. The StaticPool fixture
    #    + position-loop disable (Task #5 conftest) make the seeded row
    #    visible here under TestClient's cross-loop access pattern.
    user_row = await session.get(User, user_id)
    if user_row is None or not user_row.is_active:
        logger.info("strategy_webhook.user_inactive", user_id=str(user_id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    # 8. Max-daily-trades gate (Gate C) — DB-backed config + Redis counter.
    #    Returns ``(True, 0, 0)`` if the user has no KillSwitchConfig row,
    #    so untouched users default to "no cap" — explicit thresholds are
    #    opt-in via :class:`KillSwitchConfig`.
    within_cap, trades_today, trades_limit = (
        await kill_switch_service.check_max_daily_trades(user_id, session)
    )
    if not within_cap:
        logger.info(
            "strategy_webhook.max_daily_trades",
            user_id=str(user_id),
            trades_today=trades_today,
            trades_limit=trades_limit,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Max daily trades reached ({trades_today}/{trades_limit}).",
        )

    # 9. Time-of-day guard (bypassed in paper mode for off-hours testing)
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

    # 10. Resolve strategy early — Pine mapping needs allowed_symbols for
    #    the symbol fallback. Native payloads don't strictly need it here
    #    but the lookup is a single PK select so the order is harmless.
    strategy = await _resolve_strategy(
        session, user_id=user_id, webhook_token_id=token_id
    )
    if strategy is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No active strategy is bound to this webhook token. Create "
                "one (with broker_credential_id) before sending alerts."
            ),
        )
    strategy_id: UUID = strategy.id

    # 11. Pine Script v4.8.1 detection — translate to native shape so the
    #    rest of the pipeline keeps a single contract. Native payloads
    #    pass through unchanged.
    if is_pine_payload(payload):
        try:
            payload = map_to_tradetri_payload(payload, strategy)
        except PineMappingError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pine payload mapping failed: {exc}",
            ) from exc

    # 12. Extract structured fields
    symbol = str(payload.get("symbol", "")).strip()
    action_raw = str(payload.get("action", "")).strip().upper()
    if not symbol or action_raw not in _SUPPORTED_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Payload requires non-empty 'symbol' and action in "
                f"{sorted(_SUPPORTED_ACTIONS)}."
            ),
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

    # 13. Persist signal row
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

    # 14. Schedule async processing — never blocks the webhook response.
    #    Only entries (BUY/SELL) hit the executor; exits, partials and
    #    SL_HIT are owned by the position manager / Friday billing work.
    if action_raw in _ENTRY_ACTIONS:
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
        "queued_for_processing": action_raw in _ENTRY_ACTIONS,
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


async def _resolve_strategy(
    session: AsyncSession, *, user_id: UUID, webhook_token_id: UUID
) -> Strategy | None:
    """Full Strategy row — Pine mapping needs ``allowed_symbols``."""
    stmt = select(Strategy).where(
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

            from app.services import telegram_alerts as _alerts

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

                # Operator alerts — INFO (placed) + SUCCESS (filled).
                # Two distinct messages keep the alert taxonomy live-mode-
                # ready; in paper, fills are immediate and both fire back-
                # to-back. Real "filled with realised P&L" comes later
                # from the position-close path (Phase 2).
                _alert_msg = (
                    f"`{sig.symbol}` {sig.action} qty=`{sig.quantity or '?'}` "
                    f"order=`{result.broker_order_id}` "
                    f"position=`{result.position_id}` "
                    f"paper=`{result.paper_mode}`"
                )
                await _alerts.send_alert(_alerts.AlertLevel.INFO, "Order placed\n" + _alert_msg)
                await _alerts.send_alert(_alerts.AlertLevel.SUCCESS, "Order filled\n" + _alert_msg)

                # Post-trade hooks (Gates C bookkeeping + E auto-trip).
                # CRITICAL: failures here MUST NOT undo a successful order.
                # The trade is already committed above; we just log on error.
                try:
                    await kill_switch_service.increment_daily_trades(sig.user_id)
                    await kill_switch_service.check_and_trigger(
                        sig.user_id, session
                    )
                    await session.commit()
                except Exception:
                    logger.exception(
                        "strategy_webhook.post_trade_hook_failed",
                        signal_id=signal_id,
                        user_id=str(sig.user_id),
                    )
                    await session.rollback()
            except StrategyExecutorError as exc:
                sig.status = "failed"
                sig.notes = f"executor_error: {exc}"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                await _alerts.send_alert(
                    _alerts.AlertLevel.WARNING,
                    f"Order rejected\n`{sig.symbol}` {sig.action}: {exc}",
                )
            except Exception as exc:
                logger.exception(
                    "strategy_webhook.executor_unexpected",
                    signal_id=signal_id,
                )
                sig.status = "failed"
                sig.notes = f"unexpected: {exc}"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                await _alerts.send_alert(
                    _alerts.AlertLevel.CRITICAL,
                    f"Backend error in executor\nsignal=`{signal_id}` "
                    f"user=`{sig.user_id}` error=`{type(exc).__name__}: {exc}`",
                )
    except Exception:
        logger.exception(
            "strategy_webhook.background_failed", signal_id=signal_id
        )
        # Background-processor outer catch — usually session/DB-level.
        # Fire a CRITICAL alert without touching the broken session.
        try:
            from app.services import telegram_alerts as _alerts2

            await _alerts2.send_alert(
                _alerts2.AlertLevel.CRITICAL,
                f"Backend error in background processor\n"
                f"signal=`{signal_id}` (DB/session-level — see logs)",
            )
        except Exception:
            pass  # Alert path itself failed — already logged in send_alert.


def _resolve_client_ip(request: Request) -> str | None:
    """Resolve the originating client IP for the TV-bypass check.

    Prefers ``request.state.client_ip`` (set by
    :class:`app.middleware.security.TrustedProxyMiddleware` after honouring
    ``X-Forwarded-For`` when the immediate peer is in
    ``settings.trusted_proxy_ips``). Falls back to the immediate peer when
    the middleware didn't run (direct internal calls, some test paths).

    Spoofing-resistance is owned by the middleware: it only trusts XFF
    when the peer is in the configured trusted-proxy CIDR. Untrusted
    peers always get their own IP back regardless of XFF.
    """
    state_ip = getattr(request.state, "client_ip", None)
    if state_ip:
        return state_ip
    return request.client.host if request.client else None


def _signature_canonical(body: dict[str, Any]) -> bytes:
    """Helper kept for tests — sign the same bytes the verify path uses."""
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def _compute_strategy_signal_hash(
    user_id: UUID, payload: dict[str, Any], raw_body: bytes
) -> str:
    """Idempotency key — mirrors :func:`app.api.webhook._compute_signal_hash`.

    If the (post-mapping or native) payload supplied ``signal_id``, trust
    it so callers can explicitly suppress retries. Otherwise hash the raw
    body with the user id so two users sending identical alerts never
    collide.
    """
    sid = payload.get("signal_id")
    if sid:
        return f"{user_id}:{sid}"
    digest = hashlib.sha256(raw_body).hexdigest()
    return f"{user_id}:{digest}"


__all__ = ["QUANTITY_CEILING", "router"]
