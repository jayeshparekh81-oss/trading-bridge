"""Strategy executor — multi-leg order dispatcher.

One entry point: :func:`place_strategy_orders`. Owns the lifecycle from
"AI approved" to "position is open and tracked":

    signal (APPROVED)
        → load broker credential + decrypt
        → build entry OrderRequest (full-quantity, market)
        → place via broker  ── OR ──  PAPER_MODE: simulate fill at LTP
        → record N execution rows (one per leg, leg_role='entry')
        → open StrategyPosition with target/SL levels computed from
          strategy config
        → return list of execution rows + position id

The executor is deliberately broker-leg-light: we send ONE order to the
broker for the full lot count (broker handles its own splitting). The
``leg_number`` column in ``strategy_executions`` is for our exit-side
bookkeeping (lots 1-2 partial profit, lots 3-4 trail) and is recorded
identically across the entry rows so the audit trail is complete.

PAPER_MODE — gated by ``settings.strategy_paper_mode``. When True:
    * No broker SDK call is made.
    * A fake broker_order_id like ``PAPER-{uuid}`` is recorded.
    * avg_entry_price is taken from a configurable hint or defaults to 0.
    * The position is still opened so the position-manager loop can
      exercise its trailing-SL math against simulated ticks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.brokers.registry import get_broker_class
from app.core.config import get_settings
from app.core.exceptions import BrokerError, BrokerInsufficientFundsError
from app.core.logging import get_logger
from app.core.security import decrypt_credential
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.schemas.broker import (
    BrokerCredentials,
    Exchange,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.brokers.base import BrokerInterface

_logger = get_logger("services.strategy_executor")


#: Hard cap on per-signal quantity. Matches the AWS bot's ENTRY_QTY_MAX.
#: The webhook receiver enforces a stricter ceiling at the edge; we keep
#: this looser value so a 4-lot strategy can grow to a higher ceiling
#: without revisiting the executor.
QUANTITY_CEILING = 10


@dataclass
class ExecutionResult:
    """Outcome of a strategy entry — returned to the caller."""

    success: bool
    position_id: uuid.UUID | None
    execution_ids: list[uuid.UUID]
    broker_order_id: str
    paper_mode: bool
    message: str = ""


class StrategyExecutorError(RuntimeError):
    """Wraps any executor failure with structured context."""


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════


async def place_strategy_orders(
    session: AsyncSession,
    *,
    signal: StrategySignal,
    strategy: Strategy,
    broker_factory: Any = None,
    recommended_lots: int | None = None,
) -> ExecutionResult:
    """Place the strategy's entry order and open a tracking position.

    Args:
        session: Active async DB session. The caller is responsible for
            commit; this function only flushes so the IDs propagate.
        signal: An APPROVED ``StrategySignal``.
        strategy: The strategy that owns this signal — provides risk
            config (entry_lots, hard_sl_pct, etc.).
        broker_factory: Test seam — a callable ``(creds) -> broker``. If
            None we resolve via :mod:`app.brokers.registry`.
        recommended_lots: AI validator's tier output. When provided and
            positive, we use ``min(recommended_lots, strategy.entry_lots)``
            so the AI tier is honoured but never exceeds the user's
            configured ceiling. When 0 we raise — a rejected signal
            shouldn't reach the executor in the first place.

    Raises:
        :class:`StrategyExecutorError` for shape / config issues.
        :class:`BrokerError` for live-mode broker failures.
    """
    settings = get_settings()
    paper_mode = settings.strategy_paper_mode

    quantity = _resolve_quantity(signal, strategy, recommended_lots)
    if quantity <= 0 or quantity > QUANTITY_CEILING:
        raise StrategyExecutorError(
            f"Quantity {quantity} outside allowed range (1..{QUANTITY_CEILING})."
        )

    if strategy.broker_credential_id is None:
        raise StrategyExecutorError(
            f"Strategy {strategy.id} has no broker_credential_id linked."
        )

    side = _resolve_side(signal.action)

    cred_row = await _load_credential(
        session,
        credential_id=strategy.broker_credential_id,
        user_id=signal.user_id,
    )

    if paper_mode:
        sim = _simulate_fill(signal, quantity)
        avg_price = sim["avg_price"]
        broker_order_id = sim["broker_order_id"]
        # Persisted form must be JSON-serialisable — Decimal → str.
        broker_response = {
            **sim,
            "avg_price": str(avg_price) if avg_price is not None else None,
        }
        _logger.info(
            "strategy_executor.paper_fill",
            signal_id=str(signal.id),
            symbol=signal.symbol,
            quantity=quantity,
            broker_order_id=broker_order_id,
        )
    else:
        broker_response = await _live_place_order(
            cred_row=cred_row,
            user_id=signal.user_id,
            symbol=signal.symbol,
            side=side,
            quantity=quantity,
            broker_factory=broker_factory,
        )
        avg_price = broker_response.get("avg_price")
        broker_order_id = broker_response["broker_order_id"]

    # Record one execution row per logical leg. Same broker_order_id /
    # avg_price across all rows — broker did one fill, we account it as N.
    execution_ids: list[uuid.UUID] = []
    for leg in range(1, quantity + 1):
        ex = StrategyExecution(
            signal_id=signal.id,
            broker_credential_id=cred_row.id,
            leg_number=leg,
            leg_role="entry",
            symbol=signal.symbol,
            side=side.value,
            quantity=1,
            order_type=OrderType.MARKET.value,
            price=avg_price,
            broker_order_id=broker_order_id,
            broker_status=OrderStatus.COMPLETE.value if paper_mode else None,
            broker_response=broker_response,
            placed_at=datetime.now(UTC),
            completed_at=datetime.now(UTC) if paper_mode else None,
        )
        session.add(ex)
        await session.flush()
        execution_ids.append(ex.id)

    # Compute target / SL levels
    target_price, stop_loss_price, trail_offset = _compute_levels(
        avg_price=avg_price,
        side=side,
        strategy=strategy,
    )

    position = StrategyPosition(
        user_id=signal.user_id,
        strategy_id=strategy.id,
        broker_credential_id=cred_row.id,
        signal_id=signal.id,
        symbol=signal.symbol,
        side=side.value,
        total_quantity=quantity,
        remaining_quantity=quantity,
        avg_entry_price=avg_price,
        target_price=target_price,
        stop_loss_price=stop_loss_price,
        trail_offset=trail_offset,
        highest_price_seen=avg_price,
        status="open",
        opened_at=datetime.now(UTC),
    )
    session.add(position)
    await session.flush()

    return ExecutionResult(
        success=True,
        position_id=position.id,
        execution_ids=execution_ids,
        broker_order_id=broker_order_id,
        paper_mode=paper_mode,
        message="paper fill" if paper_mode else "broker order placed",
    )


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _resolve_quantity(
    signal: StrategySignal,
    strategy: Strategy,
    recommended_lots: int | None,
) -> int:
    """Pick the entry quantity, honouring AI recommendation + user ceiling.

    Precedence:
        1. ``recommended_lots`` (from AI validator) — when positive, this
           is the AI's tier and wins over signal/strategy defaults. Capped
           by ``strategy.entry_lots`` so users keep an absolute maximum.
        2. ``signal.quantity`` — explicit override from the webhook payload.
        3. ``strategy.entry_lots`` — the user's default sizing.

    A ``recommended_lots`` of 0 means the validator rejected; the caller
    should not reach the executor at all, so we raise to surface the bug.
    """
    if recommended_lots is not None:
        if recommended_lots <= 0:
            raise StrategyExecutorError(
                "place_strategy_orders called with recommended_lots=0 "
                "— rejected signals must short-circuit upstream."
            )
        ceiling = strategy.entry_lots or QUANTITY_CEILING
        return min(recommended_lots, ceiling)
    return signal.quantity or strategy.entry_lots


def _resolve_side(action: str) -> OrderSide:
    """Map signal action (BUY/SELL/EXIT) to OrderSide. EXIT is not handled here."""
    upper = action.upper()
    if upper == "BUY":
        return OrderSide.BUY
    if upper == "SELL":
        return OrderSide.SELL
    raise StrategyExecutorError(
        f"Unsupported action for strategy entry: {action!r} "
        "(EXIT is handled by the position manager, not the executor)."
    )


async def _load_credential(
    session: AsyncSession, *, credential_id: uuid.UUID, user_id: uuid.UUID
) -> BrokerCredential:
    stmt = select(BrokerCredential).where(
        BrokerCredential.id == credential_id,
        BrokerCredential.user_id == user_id,
        BrokerCredential.is_active.is_(True),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise StrategyExecutorError(
            f"Active broker credential {credential_id} not found for user {user_id}."
        )
    return row


def _build_broker_credentials(
    row: BrokerCredential, user_id: uuid.UUID
) -> BrokerCredentials:
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


async def _live_place_order(
    *,
    cred_row: BrokerCredential,
    user_id: uuid.UUID,
    symbol: str,
    side: OrderSide,
    quantity: int,
    broker_factory: Any,
) -> dict[str, Any]:
    """Real broker call. Only invoked when ``strategy_paper_mode`` is False."""
    creds = _build_broker_credentials(cred_row, user_id)
    if broker_factory is not None:
        broker: BrokerInterface = broker_factory(creds)
    else:
        broker = get_broker_class(creds.broker)(creds)

    if not await broker.is_session_valid():
        await broker.login()

    # Pre-trade gate 1: symbol resolution probe. Brokers with a local
    # scrip master (Dhan) fail fast on a typo or delisted symbol before
    # we burn an HTTP call fetching funds. Brokers without (Fyers) inherit
    # the no-op default — the order-placement call handles invalid-symbol
    # errors via :class:`BrokerOrderRejectedError`.
    await broker.validate_symbol(symbol, Exchange.NFO)

    # Pre-trade gate 2: minimum-funds threshold. Coarse heuristic, NOT a
    # real margin calculator (see ``pre_trade_margin_per_lot_inr`` in
    # config). Uses a 10 % slippage buffer on top of the per-lot floor so
    # a request for N lots needs ``N × FLOOR × 1.10`` available. This
    # catches empty-account requests; the broker's own margin engine still
    # owns the final word.
    settings = get_settings()
    floor_per_lot = settings.pre_trade_margin_per_lot_inr
    required = (Decimal(quantity) * floor_per_lot * Decimal("1.10")).quantize(
        Decimal("0.01")
    )
    available = await broker.get_funds()
    if available < required:
        raise BrokerInsufficientFundsError(
            f"Insufficient funds: have ₹{available}, need ~₹{required} "
            f"({quantity} lot(s) × ₹{floor_per_lot} × 1.10 buffer).",
            broker_name=creds.broker.value,
            metadata={
                "available_funds": str(available),
                "required_estimate": str(required),
                "quantity": quantity,
                "floor_per_lot": str(floor_per_lot),
                "slippage_buffer": "1.10",
            },
        )

    order = OrderRequest(
        symbol=symbol,
        exchange=Exchange.NFO,  # F&O assumed; refine when we add equity strategies
        side=side,
        quantity=quantity,
        order_type=OrderType.MARKET,
        product_type=ProductType.INTRADAY,
        tag="strategy-engine",
    )
    try:
        response: OrderResponse = await broker.place_order(order)
    except BrokerError:
        _logger.warning(
            "strategy_executor.broker_error",
            user_id=str(user_id),
            symbol=symbol,
        )
        raise

    return {
        "broker_order_id": response.broker_order_id,
        "status": response.status.value,
        "message": response.message,
        "avg_price": None,  # broker fills async; position-manager picks LTP
        "raw": response.raw_response,
    }


def _simulate_fill(signal: StrategySignal, quantity: int) -> dict[str, Any]:
    """Build a paper-fill response. avg_price comes from the signal payload
    if TradingView included one; else 0 (the position-manager seeds from LTP)."""
    payload = signal.raw_payload or {}
    raw_price = payload.get("price")
    if raw_price is not None:
        try:
            avg_price = Decimal(str(raw_price))
        except (TypeError, ValueError):
            avg_price = Decimal("0")
    else:
        avg_price = Decimal("0")
    return {
        "broker_order_id": f"PAPER-{uuid.uuid4()}",
        "status": OrderStatus.COMPLETE.value,
        "message": "paper-mode simulated fill",
        "avg_price": avg_price,
        "quantity": quantity,
        "raw": {"paper_mode": True, "source": "strategy_executor"},
    }


def _compute_levels(
    *,
    avg_price: Decimal | None,
    side: OrderSide,
    strategy: Strategy,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Compute target / stop-loss / trail-offset from strategy %-config.

    Returns ``(target_price, stop_loss_price, trail_offset)``. Any of the
    three may be None if the strategy has not configured the corresponding
    %; the position-manager treats None as "skip this trigger".
    """
    if avg_price is None or avg_price == 0:
        return None, None, None

    one = Decimal("100")

    target_price: Decimal | None = None
    if strategy.partial_profit_target_pct is not None:
        delta = avg_price * strategy.partial_profit_target_pct / one
        target_price = (
            avg_price + delta if side is OrderSide.BUY else avg_price - delta
        )

    stop_loss_price: Decimal | None = None
    if strategy.hard_sl_pct is not None:
        delta = avg_price * strategy.hard_sl_pct / one
        stop_loss_price = (
            avg_price - delta if side is OrderSide.BUY else avg_price + delta
        )

    trail_offset: Decimal | None = None
    if strategy.trail_offset_pct is not None:
        trail_offset = avg_price * strategy.trail_offset_pct / one

    return target_price, stop_loss_price, trail_offset


__all__ = [
    "QUANTITY_CEILING",
    "ExecutionResult",
    "StrategyExecutorError",
    "place_strategy_orders",
]
