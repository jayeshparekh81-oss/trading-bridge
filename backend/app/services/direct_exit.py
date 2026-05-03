"""Direct-exit handler — Pine-driven PARTIAL / EXIT / SL_HIT actions.

Distinct from :mod:`app.services.strategy_executor` which owns the
ENTRY path. This module handles webhook actions that act on an
*existing* :class:`StrategyPosition`:

  * ``PARTIAL`` — close ``closePct`` % of the open quantity. The
    server_final30mar.py reference uses a per-side memory dict
    (``mem["long_qty"]``); we mirror that with the position row's
    ``remaining_quantity`` and update ``last_action`` /
    ``action_history`` for audit.
  * ``EXIT`` — close all remaining quantity. Pine-decided clean exit.
  * ``SL_HIT`` — close all remaining quantity. Same effect as EXIT but
    recorded with ``leg_role='direct_sl'`` and a 🛑 Telegram emoji so
    the audit trail can distinguish the two reasons.

Concurrent-position semantics: at most ONE row per
``(strategy_id, symbol, side)`` with ``status IN ('open','partial')``.
A second ENTRY for the same triple SUMs into the existing row (matches
server_final30mar's scalar mem dict). PARTIAL operates on that single
row's ``remaining_quantity``.

Paper mode: skips the broker call and writes a ``PAPER-EXIT-`` order id.
The position update + audit + Telegram all run identically so paper
testing exercises the full state-machine.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.core.exceptions import BrokerError
from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.schemas.broker import (
    Exchange,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
)
from app.services.strategy_executor import (
    StrategyExecutorError,
    _build_broker,
    _load_credential,
    _resolve_lot_size,
    _resolve_product_type,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.brokers.base import BrokerInterface

_logger = get_logger("services.direct_exit")


# ═══════════════════════════════════════════════════════════════════════
# Public helpers
# ═══════════════════════════════════════════════════════════════════════


def opposite_side(position_side: str) -> OrderSide:
    """Return the broker-side that closes a position with given side.

    LONG (entry was BUY) closes via SELL. SHORT (entry was SELL) closes
    via BUY. The position row stores ``side`` as the lowercase
    OrderSide string (``"buy"`` / ``"sell"``).
    """
    side_lc = position_side.strip().lower()
    if side_lc in ("buy", "long"):
        return OrderSide.SELL
    if side_lc in ("sell", "short"):
        return OrderSide.BUY
    raise StrategyExecutorError(
        f"Unknown position side {position_side!r} — expected long/short/buy/sell."
    )


def qty_from_open_pct(open_qty: int, close_pct: float, lot_size: int) -> int:
    """Compute close-qty from open-qty + close % + lot-size.

    Mirrors server_final30mar.py's ``_qty_from_open_pct`` semantics:

      ``close_qty = floor(open_qty × close_pct / 100)``
      then floored to the nearest whole-lot multiple.

    Lot-floor is intentional — Dhan rejects below-lot quantities. If the
    rounded value is < 1 lot, this returns 0 and the caller should
    short-circuit with an "ignored: close_qty_below_lot" response.
    """
    if open_qty <= 0 or close_pct <= 0 or lot_size <= 0:
        return 0
    raw = math.floor(open_qty * close_pct / 100.0)
    # Round DOWN to lot multiple — never close more than the user asked.
    lots = raw // lot_size
    return lots * lot_size


async def get_open_position(
    session: "AsyncSession",
    *,
    strategy_id: uuid.UUID,
    symbol: str,
    side: str,
) -> StrategyPosition | None:
    """Look up the (at-most-one) open position for a strategy/symbol/side.

    Status filter ``IN ('open', 'partial')`` matches the position-loop
    poller. Side is normalized to the lowercase OrderSide spelling
    stored on the row.
    """
    side_lc = "buy" if side.lower() in ("long", "buy") else "sell"
    stmt = (
        select(StrategyPosition)
        .where(
            StrategyPosition.strategy_id == strategy_id,
            StrategyPosition.symbol == symbol.upper(),
            StrategyPosition.side == side_lc,
            StrategyPosition.status.in_(("open", "partial")),
        )
        .order_by(StrategyPosition.opened_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════
# PARTIAL handler
# ═══════════════════════════════════════════════════════════════════════


async def execute_partial(
    session: "AsyncSession",
    *,
    signal: StrategySignal,
    strategy: Strategy,
    broker_factory: Any = None,
) -> dict[str, Any]:
    """Process a Pine-driven PARTIAL signal.

    Returns a dict with ``status`` ∈ {"executed", "ignored"} and
    diagnostic fields for the signal-row notes column.

    Raises :class:`StrategyExecutorError` on hard failures (no active
    credential, broker rejection that isn't typed). Soft "no-op" cases
    (no open position, close_qty rounded to 0) return ``status="ignored"``
    with a ``reason`` string.
    """
    payload = signal.raw_payload or {}
    side_raw = str(payload.get("side") or "").lower()
    close_pct = _coerce_float(payload.get("closePct") or payload.get("close_pct"))

    if side_raw not in ("long", "short"):
        raise StrategyExecutorError(
            f"PARTIAL signal {signal.id} missing side (got {side_raw!r})."
        )
    if close_pct is None or not (0 < close_pct <= 99):
        raise StrategyExecutorError(
            f"PARTIAL signal {signal.id} invalid closePct (got {close_pct!r})."
        )

    position = await get_open_position(
        session,
        strategy_id=strategy.id,
        symbol=signal.symbol,
        side=side_raw,
    )
    if position is None or position.remaining_quantity <= 0:
        _logger.info(
            "direct_exit.partial.no_open_position",
            signal_id=str(signal.id),
            strategy_id=str(strategy.id),
            symbol=signal.symbol,
            side=side_raw,
        )
        return {"status": "ignored", "reason": "no_open_position"}

    settings = get_settings()
    paper_mode = settings.strategy_paper_mode

    cred_row = await _load_credential(
        session,
        credential_id=position.broker_credential_id,
        user_id=signal.user_id,
    )

    broker: BrokerInterface | None = None
    if not paper_mode:
        broker = _build_broker(cred_row, signal.user_id, broker_factory)

    lot_size = await _resolve_lot_size(
        broker=broker,
        symbol=signal.symbol,
        signal=signal,
        paper_mode=paper_mode,
    )

    close_qty = qty_from_open_pct(
        position.remaining_quantity, close_pct, lot_size
    )
    if close_qty <= 0:
        _logger.info(
            "direct_exit.partial.below_lot",
            signal_id=str(signal.id),
            position_id=str(position.id),
            open_qty=position.remaining_quantity,
            close_pct=close_pct,
            lot_size=lot_size,
        )
        return {"status": "ignored", "reason": "close_qty_below_lot"}

    # Broker call — opposite side, MARGIN preserved from the position's
    # original product_type when present, else the entry's payload.
    exit_side = opposite_side(position.side)
    product_type = _resolve_product_type(signal)

    fill_price, broker_order_id, broker_response = await _place_close_order(
        broker=broker,
        paper_mode=paper_mode,
        symbol=signal.symbol,
        side=exit_side,
        quantity=close_qty,
        product_type=product_type,
        signal=signal,
    )

    # Update position
    position.remaining_quantity -= close_qty
    position.status = "partial" if position.remaining_quantity > 0 else "closed"
    if position.status == "closed":
        position.closed_at = datetime.now(UTC)
        position.exit_reason = "direct_partial_full"
    _record_action(
        position,
        action="partial",
        qty=close_qty,
        side=side_raw,
        signal_id=str(signal.id),
        leg_role="direct_partial",
    )

    # Audit row
    exec_row = StrategyExecution(
        signal_id=signal.id,
        broker_credential_id=position.broker_credential_id,
        leg_number=0,  # exits use 0; leg_role disambiguates
        leg_role="direct_partial",
        symbol=signal.symbol,
        side=exit_side.value,
        quantity=close_qty,
        order_type=OrderType.MARKET.value,
        price=fill_price,
        broker_order_id=broker_order_id,
        broker_status=OrderStatus.COMPLETE.value if paper_mode else None,
        broker_response=broker_response,
        placed_at=datetime.now(UTC),
        completed_at=datetime.now(UTC) if paper_mode else None,
    )
    session.add(exec_row)
    await session.flush()

    _logger.info(
        "direct_exit.partial.executed",
        signal_id=str(signal.id),
        position_id=str(position.id),
        close_qty=close_qty,
        remaining=position.remaining_quantity,
        close_pct=close_pct,
        lot_size=lot_size,
        broker_order_id=broker_order_id,
    )

    await _alert_partial(
        strategy=strategy,
        position=position,
        close_qty=close_qty,
        fill_price=fill_price,
    )

    return {
        "status": "executed",
        "close_qty": close_qty,
        "remaining": position.remaining_quantity,
        "broker_order_id": broker_order_id,
        "position_status": position.status,
    }


# ═══════════════════════════════════════════════════════════════════════
# EXIT / SL_HIT handler
# ═══════════════════════════════════════════════════════════════════════


async def execute_exit(
    session: "AsyncSession",
    *,
    signal: StrategySignal,
    strategy: Strategy,
    leg_role: str = "direct_exit",
    broker_factory: Any = None,
) -> dict[str, Any]:
    """Close the full remaining quantity for a position.

    Used for both ``EXIT`` (Pine's clean exit) and ``SL_HIT`` (Pine's
    stop-loss hit). The caller passes ``leg_role='direct_exit'`` or
    ``'direct_sl'`` so the audit row records the intent.
    """
    payload = signal.raw_payload or {}
    side_raw = str(payload.get("side") or "").lower()
    if side_raw not in ("long", "short"):
        raise StrategyExecutorError(
            f"{leg_role.upper()} signal {signal.id} missing side "
            f"(got {side_raw!r})."
        )

    position = await get_open_position(
        session,
        strategy_id=strategy.id,
        symbol=signal.symbol,
        side=side_raw,
    )
    if position is None or position.remaining_quantity <= 0:
        _logger.info(
            "direct_exit.exit.no_open_position",
            signal_id=str(signal.id),
            strategy_id=str(strategy.id),
            symbol=signal.symbol,
            side=side_raw,
            leg_role=leg_role,
        )
        return {"status": "ignored", "reason": "no_open_position"}

    settings = get_settings()
    paper_mode = settings.strategy_paper_mode

    cred_row = await _load_credential(
        session,
        credential_id=position.broker_credential_id,
        user_id=signal.user_id,
    )

    broker: BrokerInterface | None = None
    if not paper_mode:
        broker = _build_broker(cred_row, signal.user_id, broker_factory)

    close_qty = position.remaining_quantity
    exit_side = opposite_side(position.side)
    product_type = _resolve_product_type(signal)

    fill_price, broker_order_id, broker_response = await _place_close_order(
        broker=broker,
        paper_mode=paper_mode,
        symbol=signal.symbol,
        side=exit_side,
        quantity=close_qty,
        product_type=product_type,
        signal=signal,
    )

    position.remaining_quantity = 0
    position.status = "closed"
    position.closed_at = datetime.now(UTC)
    position.exit_reason = leg_role
    _record_action(
        position,
        action="exit" if leg_role == "direct_exit" else "sl_hit",
        qty=close_qty,
        side=side_raw,
        signal_id=str(signal.id),
        leg_role=leg_role,
    )

    exec_row = StrategyExecution(
        signal_id=signal.id,
        broker_credential_id=position.broker_credential_id,
        leg_number=0,
        leg_role=leg_role,
        symbol=signal.symbol,
        side=exit_side.value,
        quantity=close_qty,
        order_type=OrderType.MARKET.value,
        price=fill_price,
        broker_order_id=broker_order_id,
        broker_status=OrderStatus.COMPLETE.value if paper_mode else None,
        broker_response=broker_response,
        placed_at=datetime.now(UTC),
        completed_at=datetime.now(UTC) if paper_mode else None,
    )
    session.add(exec_row)
    await session.flush()

    _logger.info(
        "direct_exit.exit.executed",
        signal_id=str(signal.id),
        position_id=str(position.id),
        close_qty=close_qty,
        leg_role=leg_role,
        broker_order_id=broker_order_id,
    )

    await _alert_exit(
        strategy=strategy,
        position=position,
        close_qty=close_qty,
        fill_price=fill_price,
        leg_role=leg_role,
    )

    return {
        "status": "executed",
        "close_qty": close_qty,
        "remaining": 0,
        "broker_order_id": broker_order_id,
        "position_status": "closed",
    }


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════


async def _place_close_order(
    *,
    broker: "BrokerInterface | None",
    paper_mode: bool,
    symbol: str,
    side: OrderSide,
    quantity: int,
    product_type: ProductType,
    signal: StrategySignal,
) -> tuple[Decimal | None, str, dict[str, Any]]:
    """Fire the close order. Returns (fill_price, broker_order_id, raw)."""
    if paper_mode or broker is None:
        # Use signal payload price if present, else None — position-loop
        # is not running for direct_exit positions, so no LTP is auto-seeded.
        price_raw = (signal.raw_payload or {}).get("price")
        if price_raw is not None:
            try:
                fill_price = Decimal(str(price_raw))
            except (TypeError, ValueError):
                fill_price = None
        else:
            fill_price = None
        broker_order_id = f"PAPER-EXIT-{uuid.uuid4()}"
        broker_response = {
            "broker_order_id": broker_order_id,
            "status": OrderStatus.COMPLETE.value,
            "message": "paper-mode simulated close",
            "fill_price": str(fill_price) if fill_price is not None else None,
            "raw": {"paper_mode": True, "source": "direct_exit"},
        }
        return fill_price, broker_order_id, broker_response

    if not await broker.is_session_valid():
        await broker.login()

    # Brokers with a scrip master fail-fast on a typo. Brokers without
    # inherit the no-op default; the order placement returns a typed error.
    await broker.validate_symbol(symbol, Exchange.NFO)

    order = OrderRequest(
        symbol=symbol,
        exchange=Exchange.NFO,
        side=side,
        quantity=quantity,
        order_type=OrderType.MARKET,
        product_type=product_type,
        tag="strategy-engine-direct-exit",
    )
    try:
        response: OrderResponse = await broker.place_order(order)
    except BrokerError:
        _logger.warning(
            "direct_exit.broker_error",
            symbol=symbol,
            quantity=quantity,
            side=side.value,
        )
        raise

    return None, response.broker_order_id, {
        "broker_order_id": response.broker_order_id,
        "status": response.status.value,
        "message": response.message,
        "fill_price": None,
        "raw": response.raw_response,
    }


def _record_action(
    position: StrategyPosition,
    *,
    action: str,
    qty: int,
    side: str,
    signal_id: str,
    leg_role: str,
) -> None:
    """Mutate ``position.last_action`` / ``last_action_at`` /
    ``action_history`` in place. Caller commits."""
    now = datetime.now(UTC)
    position.last_action = action
    position.last_action_at = now
    history = position.action_history or []
    history.append(
        {
            "action": action,
            "qty": qty,
            "side": side,
            "ts": now.isoformat(),
            "signal_id": signal_id,
            "leg_role": leg_role,
        }
    )
    position.action_history = history
    # SQLAlchemy doesn't always detect in-place mutations of JSON columns;
    # flag_modified is the safe path.
    flag_modified(position, "action_history")


async def _alert_partial(
    *,
    strategy: Strategy,
    position: StrategyPosition,
    close_qty: int,
    fill_price: Decimal | None,
) -> None:
    """Telegram 📉 alert for a Pine-driven PARTIAL booking."""
    try:
        from app.services import telegram_alerts as _alerts

        msg = (
            "📉 PARTIAL exit\n"
            f"strategy=`{strategy.name}` ({strategy.id})\n"
            f"position=`{position.id}`\n"
            f"symbol=`{position.symbol}` side=`{position.side}`\n"
            f"closed=`{close_qty}` remaining=`{position.remaining_quantity}`\n"
            f"price=`{fill_price if fill_price is not None else '?'}`"
        )
        await _alerts.send_alert(_alerts.AlertLevel.SUCCESS, msg)
    except Exception:
        _logger.exception(
            "direct_exit.partial.alert_failed",
            position_id=str(position.id),
        )


async def _alert_exit(
    *,
    strategy: Strategy,
    position: StrategyPosition,
    close_qty: int,
    fill_price: Decimal | None,
    leg_role: str,
) -> None:
    """Telegram alert for a Pine-driven EXIT (🔴) or SL_HIT (🛑)."""
    try:
        from app.services import telegram_alerts as _alerts

        is_sl = leg_role == "direct_sl"
        emoji = "🛑" if is_sl else "🔴"
        title = "SL_HIT — position closed" if is_sl else "EXIT — position closed"
        level = _alerts.AlertLevel.WARNING if is_sl else _alerts.AlertLevel.INFO
        msg = (
            f"{emoji} {title}\n"
            f"strategy=`{strategy.name}` ({strategy.id})\n"
            f"position=`{position.id}`\n"
            f"symbol=`{position.symbol}` side=`{position.side}`\n"
            f"closed=`{close_qty}`\n"
            f"price=`{fill_price if fill_price is not None else '?'}`"
        )
        await _alerts.send_alert(level, msg)
    except Exception:
        _logger.exception(
            "direct_exit.exit.alert_failed",
            position_id=str(position.id),
            leg_role=leg_role,
        )


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "execute_exit",
    "execute_partial",
    "get_open_position",
    "opposite_side",
    "qty_from_open_pct",
]
