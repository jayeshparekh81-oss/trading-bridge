"""TradingView webhook receiver — the heart of the bridge.

One endpoint: ``POST /api/webhook/{webhook_token}``. It runs the full
Kill-Switch pipeline from the blueprint:

    rate limit
      → token lookup (Redis cache, Postgres fallback)
      → HMAC verify (timing-safe)
      → payload parse (Pydantic)
      → idempotency claim (Redis SET NX)
      → kill-switch gate
      → user-active gate
      → order-service dispatch
      → audit write (async background)
      → response with ``latency_ms``

Every short-circuit path still writes a ``webhook_events`` row so the
audit log reflects reality. The actual DB write runs in a background
task so the happy-path response is not blocked by Postgres latency.
"""

from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core import redis_client
from app.core.exceptions import BrokerError, BrokerOrderRejectedError
from app.core.logging import bind_request_context, clear_request_context, get_logger
from app.core.security import decrypt_credential, verify_hmac_signature
from app.core.security_ext import sanitize_input
from app.db.models.strategy import Strategy
from app.db.models.trade import ProcessingStatus
from app.db.models.user import User
from app.db.models.webhook_event import WebhookEvent
from app.db.models.webhook_token import WebhookToken
from app.db.session import get_session
from app.schemas.webhook import (
    WebhookPayload,
    WebhookResponse,
    WebhookResponseStatus,
)
from app.services.circuit_breaker_service import (
    CircuitBreakerLevel,
    circuit_breaker_service,
)
from app.services.kill_switch_service import kill_switch_service
from app.services.order_service import OrderResult, process_webhook_signal

if TYPE_CHECKING:
    pass


logger = get_logger("app.api.webhook")

#: Forward-compatible 422 alias — starlette renamed the constant but the old
#: name still exists; using ``getattr`` keeps both old and new releases happy.
_STATUS_422 = getattr(
    status, "HTTP_422_UNPROCESSABLE_CONTENT", status.HTTP_422_UNPROCESSABLE_ENTITY
)

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

#: Max webhooks per user per minute. Beyond this → 429.
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

#: TTL for cached token → user-id mapping. Short enough that revoked
#: tokens stop working quickly, long enough to absorb the bursty alerts
#: TradingView sends around market opens.
TOKEN_CACHE_TTL_SECONDS = 60

#: TTL for idempotency slots. 60 s is the industry convention — Trading‑
#: View retries the same alert inside ~30 s if our endpoint times out.
IDEMPOTENCY_TTL_SECONDS = 60

#: Header name TradingView must send with the HMAC signature.
HMAC_HEADER = "X-Signature"


# ═══════════════════════════════════════════════════════════════════════
# Endpoint
# ═══════════════════════════════════════════════════════════════════════


@router.post(
    "/{webhook_token}",
    response_model=WebhookResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid HMAC signature"},
        status.HTTP_403_FORBIDDEN: {"description": "Kill switch tripped / user inactive"},
        status.HTTP_404_NOT_FOUND: {"description": "Unknown webhook token"},
        status.HTTP_409_CONFLICT: {"description": "Duplicate signal"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Rate limit exceeded"},
    },
)
async def receive_webhook(
    request: Request,
    background: BackgroundTasks,
    webhook_token: str = Path(..., min_length=16, max_length=128),
    session: AsyncSession = Depends(get_session),
) -> WebhookResponse:
    """Accept a TradingView alert and execute the associated order."""
    started = time.perf_counter()
    raw_body = await request.body()
    signature = request.headers.get(HMAC_HEADER, "")
    source_ip = _client_ip(request)

    # ── 1. Token lookup (cache → DB) ───────────────────────────────────
    token_info = await _resolve_webhook_token(session, webhook_token)
    if token_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown webhook token.",
        )
    user_id: UUID = token_info["user_id"]
    hmac_secret: str = token_info["hmac_secret"]
    bind_request_context(user_id=str(user_id))

    try:
        # ── 2. Rate limit ─────────────────────────────────────────────
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

        # ── 3. HMAC verify ────────────────────────────────────────────
        if not verify_hmac_signature(raw_body, signature, hmac_secret):
            background.add_task(
                _audit_event,
                user_id=user_id,
                source_ip=source_ip,
                signature_valid=False,
                payload={"raw": raw_body.decode("utf-8", errors="replace")},
                status_=ProcessingStatus.FAILED,
                error="invalid_signature",
                latency_ms=_elapsed_ms(started),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid HMAC signature.",
            )

        # ── 4. Payload parse ──────────────────────────────────────────
        payload = _parse_payload(raw_body)

        # ── 5. Idempotency ────────────────────────────────────────────
        signal_hash = _compute_signal_hash(user_id, payload, raw_body)
        claimed = await redis_client.set_idempotency_key(
            signal_hash, ttl_seconds=IDEMPOTENCY_TTL_SECONDS
        )
        if not claimed:
            background.add_task(
                _audit_event,
                user_id=user_id,
                source_ip=source_ip,
                signature_valid=True,
                payload=payload.model_dump(mode="json"),
                status_=ProcessingStatus.SKIPPED,
                error="duplicate",
                latency_ms=_elapsed_ms(started),
            )
            return WebhookResponse(
                status=WebhookResponseStatus.DUPLICATE,
                message="duplicate signal suppressed",
                latency_ms=_elapsed_ms(started),
            )

        # ── 6. Kill switch + user gate ────────────────────────────────
        kill_status = await redis_client.get_kill_switch_status(user_id)
        if kill_status == redis_client.KILL_SWITCH_TRIPPED:
            background.add_task(
                _audit_event,
                user_id=user_id,
                source_ip=source_ip,
                signature_valid=True,
                payload=payload.model_dump(mode="json"),
                status_=ProcessingStatus.SKIPPED,
                error="kill_switch_tripped",
                latency_ms=_elapsed_ms(started),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Kill switch is TRIPPED — trading paused.",
            )

        user_ctx = await _load_user_context(session, user_id)
        if user_ctx is None or not user_ctx.is_active:
            background.add_task(
                _audit_event,
                user_id=user_id,
                source_ip=source_ip,
                signature_valid=True,
                payload=payload.model_dump(mode="json"),
                status_=ProcessingStatus.SKIPPED,
                error="user_inactive",
                latency_ms=_elapsed_ms(started),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )

        # ── 7. Max-daily-trades gate ──────────────────────────────────
        within_cap, trades_today, trades_limit = (
            await kill_switch_service.check_max_daily_trades(user_id, session)
        )
        if not within_cap:
            background.add_task(
                _audit_event,
                user_id=user_id,
                source_ip=source_ip,
                signature_valid=True,
                payload=payload.model_dump(mode="json"),
                status_=ProcessingStatus.SKIPPED,
                error=f"max_daily_trades:{trades_today}/{trades_limit}",
                latency_ms=_elapsed_ms(started),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Max daily trades reached ({trades_today}/{trades_limit})."
                ),
            )

        # ── 8. Circuit-breaker gate ───────────────────────────────────
        cb_level = await circuit_breaker_service.get_state(
            sanitize_input(payload.symbol), payload.exchange
        )
        if cb_level is CircuitBreakerLevel.HALT:
            background.add_task(
                _audit_event,
                user_id=user_id,
                source_ip=source_ip,
                signature_valid=True,
                payload=payload.model_dump(mode="json"),
                status_=ProcessingStatus.SKIPPED,
                error="circuit_breaker_halt",
                latency_ms=_elapsed_ms(started),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Circuit breaker HALT on {payload.symbol}.",
            )

        # ── 9. Resolve strategy → broker credential ───────────────────
        binding = await _resolve_binding(
            session,
            user_id=user_id,
            webhook_token_id=token_info["token_id"],
        )
        if binding is None:
            raise HTTPException(
                status_code=_STATUS_422,
                detail=(
                    "No broker credential is bound to this webhook token. "
                    "Create a strategy that links the two before sending alerts."
                ),
            )
        strategy_id, broker_credential_id = binding

        # ── 10. Dispatch to order service ──────────────────────────────
        try:
            result: OrderResult = await process_webhook_signal(
                session,
                user_id=user_id,
                broker_credential_id=broker_credential_id,
                payload=payload,
                strategy_id=strategy_id,
            )
            await session.commit()
        except BrokerOrderRejectedError as exc:
            await session.rollback()
            background.add_task(
                _audit_event,
                user_id=user_id,
                source_ip=source_ip,
                signature_valid=True,
                payload=payload.model_dump(mode="json"),
                status_=ProcessingStatus.FAILED,
                error=f"rejected: {exc.reason}",
                latency_ms=_elapsed_ms(started),
            )
            # Let the app-level broker exception handler map to HTTP 422.
            raise
        except BrokerError:
            await session.rollback()
            background.add_task(
                _audit_event,
                user_id=user_id,
                source_ip=source_ip,
                signature_valid=True,
                payload=payload.model_dump(mode="json"),
                status_=ProcessingStatus.FAILED,
                error="broker_error",
                latency_ms=_elapsed_ms(started),
            )
            raise

        # ── 11. Post-trade bookkeeping ────────────────────────────────
        # Increment the daily trades counter; kill-switch evaluation runs
        # next so a breach detected here fires before we return to the caller.
        await kill_switch_service.increment_daily_trades(user_id)
        trip_result = await kill_switch_service.check_and_trigger(user_id, session)
        if trip_result.triggered:
            await session.commit()
            background.add_task(
                _audit_event,
                user_id=user_id,
                source_ip=source_ip,
                signature_valid=True,
                payload=payload.model_dump(mode="json"),
                status_=ProcessingStatus.EXECUTED,
                error=(
                    f"kill_switch_triggered:{trip_result.reason.value}"
                    if trip_result.reason
                    else "kill_switch_triggered"
                ),
                latency_ms=result.latency_ms,
            )
            return WebhookResponse(
                status=WebhookResponseStatus.SUCCESS,
                order_id=result.broker_order_id or None,
                trade_id=str(result.trade_id) if result.trade_id else None,
                message="order placed; kill-switch tripped",
                latency_ms=result.latency_ms,
                metadata={
                    **result.metadata,
                    "kill_switch_triggered": True,
                    "trip_reason": (
                        trip_result.reason.value if trip_result.reason else None
                    ),
                },
            )

        # ── 12. Audit (background) ────────────────────────────────────
        background.add_task(
            _audit_event,
            user_id=user_id,
            source_ip=source_ip,
            signature_valid=True,
            payload=payload.model_dump(mode="json"),
            status_=ProcessingStatus.EXECUTED,
            error=None,
            latency_ms=result.latency_ms,
        )

        return WebhookResponse(
            status=(
                WebhookResponseStatus.SUCCESS
                if result.success
                else WebhookResponseStatus.REJECTED
            ),
            order_id=result.broker_order_id or None,
            trade_id=str(result.trade_id) if result.trade_id else None,
            message=result.message,
            latency_ms=result.latency_ms,
            metadata=result.metadata,
        )
    finally:
        clear_request_context("user_id")


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _client_ip(request: Request) -> str | None:
    """Best-effort source IP: honour ``X-Forwarded-For`` (proxy) else peer."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _hash_token(token: str) -> str:
    """Webhook tokens are hashed before being stored — SHA-256 hex.

    Matches the column definition (``String(128)``); callers compare the
    stored hash against this digest.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _resolve_webhook_token(
    session: AsyncSession, token: str
) -> dict[str, Any] | None:
    """Look up a webhook token — Redis first, then DB.

    Returns a dict with ``user_id`` / ``token_id`` / ``hmac_secret`` on
    hit, ``None`` on miss. Caching the plaintext HMAC secret in Redis is
    OK: Redis is an internal service, never exposed, and the secret is
    per-token so rotation is cheap. If that ever changes, encrypt the
    cache payload with Fernet.
    """
    token_hash = _hash_token(token)

    cached = await redis_client.cache_get_json(f"webhook_token:{token_hash}")
    if cached is not None:
        try:
            return {
                "user_id": UUID(cached["user_id"]),
                "token_id": UUID(cached["token_id"]),
                "hmac_secret": cached["hmac_secret"],
            }
        except (KeyError, ValueError):
            # Cache got poisoned somehow — fall through to DB.
            logger.warning("webhook.cache_corrupt", token_hash=token_hash)

    stmt = select(WebhookToken).where(
        WebhookToken.token_hash == token_hash,
        WebhookToken.is_active.is_(True),
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None

    try:
        hmac_secret = decrypt_credential(row.hmac_secret_enc)
    except Exception:  # noqa: BLE001 — broken credentials should 404, not 500.
        logger.warning("webhook.hmac_decrypt_failed", token_hash=token_hash)
        return None

    info = {
        "user_id": row.user_id,
        "token_id": row.id,
        "hmac_secret": hmac_secret,
    }
    await redis_client.cache_set_json(
        f"webhook_token:{token_hash}",
        {
            "user_id": str(row.user_id),
            "token_id": str(row.id),
            "hmac_secret": hmac_secret,
        },
        TOKEN_CACHE_TTL_SECONDS,
    )
    return info


def _parse_payload(raw: bytes) -> WebhookPayload:
    """Pydantic-validate the body; re-raise validation errors as 422."""
    try:
        return WebhookPayload.model_validate_json(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=_STATUS_422,
            detail=f"Invalid webhook payload: {exc}",
        ) from exc


def _compute_signal_hash(
    user_id: UUID, payload: WebhookPayload, raw_body: bytes
) -> str:
    """Idempotency key.

    If the caller supplied ``signal_id``, trust it (gives TradingView the
    ability to explicitly suppress retries). Otherwise hash the raw body
    with the user id so two users sending identical alerts do not collide.
    """
    if payload.signal_id:
        return f"{user_id}:{payload.signal_id}"
    digest = hashlib.sha256(raw_body).hexdigest()
    return f"{user_id}:{digest}"


async def _load_user_context(session: AsyncSession, user_id: UUID) -> User | None:
    """Fetch the user row to gate on ``is_active``."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _resolve_binding(
    session: AsyncSession,
    *,
    user_id: UUID,
    webhook_token_id: UUID,
) -> tuple[UUID | None, UUID] | None:
    """Return ``(strategy_id, broker_credential_id)`` or ``None``.

    Strategies own the webhook_token → broker_credential binding. If no
    active strategy exists we fall back to the user's default broker
    credential — but only if they have exactly one, to avoid routing a
    live trade to the wrong account.
    """
    stmt = select(Strategy).where(
        Strategy.user_id == user_id,
        Strategy.webhook_token_id == webhook_token_id,
        Strategy.is_active.is_(True),
    )
    result = await session.execute(stmt)
    strategy = result.scalars().first()
    if strategy is not None and strategy.broker_credential_id is not None:
        return strategy.id, strategy.broker_credential_id

    # Fallback: single active broker credential for this user.
    from app.db.models.broker_credential import BrokerCredential

    stmt2 = select(BrokerCredential).where(
        BrokerCredential.user_id == user_id,
        BrokerCredential.is_active.is_(True),
    )
    result2 = await session.execute(stmt2)
    creds = result2.scalars().all()
    if len(creds) == 1:
        return None, creds[0].id
    return None


async def _audit_event(
    *,
    user_id: UUID,
    source_ip: str | None,
    signature_valid: bool,
    payload: dict[str, Any],
    status_: ProcessingStatus,
    error: str | None,
    latency_ms: int,
) -> None:
    """Write a ``webhook_events`` row in the background.

    Opens its own session — the request-scoped session may already be
    closed by the time this runs.
    """
    from app.db.session import get_sessionmaker

    maker = get_sessionmaker()
    try:
        async with maker() as session:
            event = WebhookEvent(
                user_id=user_id,
                source_ip=source_ip,
                signature_valid=signature_valid,
                payload=payload,
                processing_status=status_,
                error_message=error,
                latency_ms=latency_ms,
            )
            session.add(event)
            await session.commit()
    except Exception as exc:  # noqa: BLE001 — audit failure must not crash the worker.
        logger.warning(
            "webhook.audit_failed",
            user_id=str(user_id),
            error=str(exc),
        )


__all__ = ["router"]
