"""Order orchestration — the brain wiring webhooks to brokers.

One entry point: :func:`process_webhook_signal`. It owns the full lifecycle
of a single TradingView alert:

    webhook payload
        → fetch broker credentials (DB, decrypt)
        → instantiate broker
        → refresh session if expired
        → normalize symbol
        → dispatch (BUY / SELL / EXIT)
        → record trade + update Redis position cache
        → return ``OrderResult``

The function is careful about two things:

1. **Failure surface.** Every broker failure propagates as a typed
   ``BrokerError``. The webhook endpoint relies on that to map to the
   right HTTP status, so catching generic ``Exception`` here would
   silently collapse that information.

2. **Single-retry session refresh.** If the broker raises
   ``BrokerSessionExpiredError`` on the first call, we call ``login()``
   once and replay. Two-retry cycles mean the user is burning seconds
   inside TradingView's 10 s timeout — we prefer to fail fast than to
   queue up retries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.brokers.registry import get_broker_class
from app.core.exceptions import (
    BrokerAuthError,
    BrokerSessionExpiredError,
)
from app.core.logging import get_logger
from app.core.security import decrypt_credential
from app.db.models.broker_credential import BrokerCredential
from app.db.models.trade import Trade, TradeStatus
from app.schemas.broker import (
    BrokerCredentials,
    Exchange,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
)
from app.schemas.webhook import WebhookAction, WebhookPayload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.brokers.base import BrokerInterface


logger = get_logger("app.services.order_service")


# ═══════════════════════════════════════════════════════════════════════
# Return type
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class OrderResult:
    """What the webhook endpoint needs to build its response.

    We keep this as a plain dataclass rather than a Pydantic model — no
    validation is required on the service → router boundary, and the
    dataclass is cheap to construct inside a hot path.
    """

    success: bool
    trade_id: UUID | None
    broker_order_id: str | None
    order_status: OrderStatus | None
    message: str
    latency_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════
# Public entry point
# ═══════════════════════════════════════════════════════════════════════


async def process_webhook_signal(
    session: AsyncSession,
    *,
    user_id: UUID,
    broker_credential_id: UUID,
    payload: WebhookPayload,
    strategy_id: UUID | None = None,
    broker_factory: Any = None,
) -> OrderResult:
    """Execute a TradingView webhook signal end-to-end.

    Args:
        session: Active async DB session. The caller owns commit — we
            ``flush`` after writing so the returned ``trade_id`` is real,
            but let the outer request decide when to persist.
        user_id: Platform user placing the trade.
        broker_credential_id: Which credential to use (a user may have
            multiple brokers linked).
        payload: Parsed webhook payload.
        strategy_id: Optional strategy binding for attribution.
        broker_factory: Test hook — pass a callable that takes
            ``BrokerCredentials`` and returns a :class:`BrokerInterface`.
            Production code leaves this ``None`` so the registry resolves
            the concrete class.

    Returns:
        An :class:`OrderResult` describing what the broker did.
    """
    started = time.perf_counter()

    credential_row = await _load_credential(session, broker_credential_id, user_id)
    creds = _build_broker_credentials(credential_row, user_id)

    broker = _instantiate_broker(creds, broker_factory=broker_factory)
    await _ensure_session(broker)

    native_symbol = broker.normalize_symbol(payload.symbol, payload.exchange)

    try:
        broker_response = await _dispatch_action(
            broker, payload=payload, native_symbol=native_symbol
        )
    except BrokerSessionExpiredError:
        # One retry after a forced relogin — if it still fails, the error
        # type is kept and propagates to the HTTP layer as a 401.
        logger.info("order.session_expired_retrying", user_id=str(user_id))
        await broker.login()
        broker_response = await _dispatch_action(
            broker, payload=payload, native_symbol=native_symbol
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    trade = await _record_trade(
        session,
        user_id=user_id,
        broker_credential_id=broker_credential_id,
        strategy_id=strategy_id,
        payload=payload,
        native_symbol=native_symbol,
        broker_response=broker_response,
        latency_ms=elapsed_ms,
    )

    logger.info(
        "order.completed",
        user_id=str(user_id),
        broker_order_id=broker_response.broker_order_id,
        symbol=native_symbol,
        action=payload.action.value,
        latency_ms=elapsed_ms,
    )

    return OrderResult(
        success=broker_response.status != OrderStatus.REJECTED,
        trade_id=trade.id,
        broker_order_id=broker_response.broker_order_id,
        order_status=broker_response.status,
        message=broker_response.message or "order placed",
        latency_ms=elapsed_ms,
        metadata={"native_symbol": native_symbol},
    )


# ═══════════════════════════════════════════════════════════════════════
# Internals
# ═══════════════════════════════════════════════════════════════════════


async def _load_credential(
    session: AsyncSession, credential_id: UUID, user_id: UUID
) -> BrokerCredential:
    """Fetch a broker credential row — scoped to the user that owns it.

    Scoping to ``user_id`` prevents a lookup bug from letting user A's
    webhook trigger a trade on user B's account — defence in depth.
    """
    stmt = select(BrokerCredential).where(
        BrokerCredential.id == credential_id,
        BrokerCredential.user_id == user_id,
        BrokerCredential.is_active.is_(True),
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise BrokerAuthError(
            "Broker credential not found or inactive.",
            broker_name="unknown",
            metadata={
                "user_id": str(user_id),
                "broker_credential_id": str(credential_id),
            },
        )
    return row


def _build_broker_credentials(
    row: BrokerCredential, user_id: UUID
) -> BrokerCredentials:
    """Decrypt the persisted columns into a :class:`BrokerCredentials`."""
    return BrokerCredentials(
        broker=row.broker_name,
        user_id=str(user_id),
        client_id=decrypt_credential(row.client_id_enc),
        api_key=decrypt_credential(row.api_key_enc),
        api_secret=decrypt_credential(row.api_secret_enc),
        access_token=(
            decrypt_credential(row.access_token_enc)
            if row.access_token_enc
            else None
        ),
        refresh_token=(
            decrypt_credential(row.refresh_token_enc)
            if row.refresh_token_enc
            else None
        ),
        token_expires_at=row.token_expires_at,
    )


def _instantiate_broker(
    creds: BrokerCredentials, *, broker_factory: Any = None
) -> BrokerInterface:
    """Resolve the broker class from the registry and construct it."""
    if broker_factory is not None:
        return broker_factory(creds)  # type: ignore[no-any-return]
    cls = get_broker_class(creds.broker)
    return cls(creds)


async def _ensure_session(broker: BrokerInterface) -> None:
    """Call ``login()`` once if the cached session is stale."""
    if not await broker.is_session_valid():
        await broker.login()


async def _dispatch_action(
    broker: BrokerInterface,
    *,
    payload: WebhookPayload,
    native_symbol: str,
) -> OrderResponse:
    """Route BUY/SELL/EXIT to the correct broker operation."""
    match payload.action:
        case WebhookAction.BUY:
            return await broker.place_order(
                _build_order_request(payload, native_symbol, OrderSide.BUY)
            )
        case WebhookAction.SELL:
            return await broker.place_order(
                _build_order_request(payload, native_symbol, OrderSide.SELL)
            )
        case WebhookAction.EXIT:
            return await _square_off_symbol(broker, native_symbol, payload.exchange)


def _build_order_request(
    payload: WebhookPayload, native_symbol: str, side: OrderSide
) -> OrderRequest:
    """Translate a webhook payload into a broker-contract order request."""
    return OrderRequest(
        symbol=native_symbol,
        exchange=payload.exchange,
        side=side,
        quantity=payload.quantity,
        order_type=payload.order_type,
        product_type=payload.product_type,
        price=payload.price,
        trigger_price=payload.trigger_price,
        tag=payload.strategy_name,
    )


async def _square_off_symbol(
    broker: BrokerInterface, native_symbol: str, exchange: Exchange
) -> OrderResponse:
    """EXIT = close the existing position on this symbol only.

    We fetch positions, find the matching leg, and place a market order
    in the opposite direction. If no position exists the operation is a
    no-op surfaced as a COMPLETE response — TradingView should not get a
    500 for a redundant exit.
    """
    positions = await broker.get_positions()
    target = next(
        (
            p
            for p in positions
            if p.symbol == native_symbol
            and p.exchange == exchange
            and p.quantity != 0
        ),
        None,
    )
    if target is None:
        return OrderResponse(
            broker_order_id="",
            status=OrderStatus.COMPLETE,
            message="no open position to exit",
        )

    closing_side = OrderSide.SELL if target.quantity > 0 else OrderSide.BUY
    closing_qty = abs(target.quantity)
    order = OrderRequest(
        symbol=native_symbol,
        exchange=exchange,
        side=closing_side,
        quantity=closing_qty,
        order_type=_market_order_type(),
        product_type=target.product_type,
    )
    return await broker.place_order(order)


def _market_order_type() -> Any:
    """Isolate the import so the OrderType enum is only loaded when needed."""
    from app.schemas.broker import OrderType

    return OrderType.MARKET


async def _record_trade(
    session: AsyncSession,
    *,
    user_id: UUID,
    broker_credential_id: UUID,
    strategy_id: UUID | None,
    payload: WebhookPayload,
    native_symbol: str,
    broker_response: OrderResponse,
    latency_ms: int,
) -> Trade:
    """Persist a ``trades`` row, flush, and return the hydrated object."""
    trade_status = _map_order_status(broker_response.status)
    side = _resolve_trade_side(payload)

    trade = Trade(
        user_id=user_id,
        broker_credential_id=broker_credential_id,
        strategy_id=strategy_id,
        broker_order_id=broker_response.broker_order_id or None,
        tradingview_signal_id=payload.signal_id,
        symbol=native_symbol,
        exchange=payload.exchange.value,
        side=side,
        order_type=payload.order_type,
        product_type=payload.product_type,
        quantity=payload.quantity,
        price=payload.price,
        status=trade_status,
        latency_ms=latency_ms,
        raw_payload={
            "webhook": payload.model_dump(mode="json"),
            "broker_response": broker_response.model_dump(mode="json"),
        },
    )
    session.add(trade)
    await session.flush()
    return trade


def _resolve_trade_side(payload: WebhookPayload) -> OrderSide:
    """EXIT has no inherent side — record it as SELL for audit simplicity.

    The ``raw_payload`` JSON preserves the true action; the ``side`` column
    is a coarse index used by reports.
    """
    match payload.action:
        case WebhookAction.BUY:
            return OrderSide.BUY
        case WebhookAction.SELL:
            return OrderSide.SELL
        case WebhookAction.EXIT:
            return OrderSide.SELL


def _map_order_status(status: OrderStatus) -> TradeStatus:
    """Normalized broker status → persisted trade status."""
    match status:
        case OrderStatus.PENDING:
            return TradeStatus.PENDING
        case OrderStatus.OPEN:
            return TradeStatus.OPEN
        case OrderStatus.COMPLETE:
            return TradeStatus.COMPLETE
        case OrderStatus.CANCELLED:
            return TradeStatus.CANCELLED
        case OrderStatus.REJECTED:
            return TradeStatus.REJECTED
        case OrderStatus.PARTIAL:
            return TradeStatus.PARTIAL


__all__ = [
    "OrderResult",
    "process_webhook_signal",
]
