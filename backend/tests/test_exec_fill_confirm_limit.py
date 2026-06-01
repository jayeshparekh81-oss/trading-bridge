"""Targeted tests for the 2026-06-01 execution fix:

  * fill-confirmation gates position creation (REJECTED / 0-fill → raise, no
    phantom; TRADED → authoritative averageTradedPrice flows out);
  * scoped marketable-LIMIT (89423ecc only; CDSL & others stay MARKET);
  * direct-exit decrements remaining_quantity by the CONFIRMED filled qty.

Driven through ``_live_place_order`` with a spec'd BrokerInterface mock —
no DB / no live broker.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.brokers.base import BrokerInterface
from app.core.exceptions import BrokerOrderRejectedError
from app.schemas.broker import (
    BrokerName,
    OrderFill,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.services import strategy_executor as se

# asyncio_mode=auto (pyproject) auto-detects async tests — no marker needed.

_BSE = "89423ecc-c76e-432c-b107-0791508542f0"
_CDSL = "0252e82c-0000-0000-0000-000000000000"


def _broker(*, fill: OrderFill, ack_status: OrderStatus = OrderStatus.PENDING) -> MagicMock:
    b = MagicMock(spec=BrokerInterface)
    b.broker_name = BrokerName.DHAN
    b.is_session_valid = AsyncMock(return_value=True)
    b.login = AsyncMock(return_value=True)
    b.validate_symbol = AsyncMock(return_value=None)
    b.get_funds = AsyncMock(return_value=Decimal("10000000"))
    b.place_order = AsyncMock(
        return_value=OrderResponse(
            broker_order_id="OID-1", status=ack_status, message="", raw_response={}
        )
    )
    b.confirm_fill = AsyncMock(return_value=fill)
    return b


async def _place(broker: MagicMock, **kw):
    return await se._live_place_order(
        broker=broker,
        user_id="11111111-1111-1111-1111-111111111111",
        symbol="BSE-JUN2026-FUT",
        side=OrderSide.BUY,
        quantity=375,
        lot_size=375,
        **kw,
    )


# ── fill confirmation gates position creation ────────────────────────────


async def test_rejected_fill_raises_no_phantom() -> None:
    """confirm_fill REJECTED (e.g. EXCH:17070 LPP) → raise, so the caller
    never creates a phantom position."""
    broker = _broker(
        fill=OrderFill(
            broker_order_id="OID-1",
            order_status=OrderStatus.REJECTED,
            raw_status="REJECTED",
            filled_qty=0,
            reason="EXCH:17070 : The Price Is Out Of The Current LPP Range",
        )
    )
    with pytest.raises(BrokerOrderRejectedError):
        await _place(broker)
    broker.confirm_fill.assert_awaited_once()


async def test_accepted_but_zero_fill_raises() -> None:
    """An *accepted* (PENDING ack) order that confirms with 0 filled →
    raise (TRANSIT→REJECTED async path / no fill in window)."""
    broker = _broker(
        fill=OrderFill(
            broker_order_id="OID-1",
            order_status=OrderStatus.PENDING,
            raw_status="TRANSIT",
            filled_qty=0,
        )
    )
    with pytest.raises(BrokerOrderRejectedError):
        await _place(broker)


async def test_traded_returns_authoritative_avg_price() -> None:
    """TRADED → returned avg_price is the orderbook averageTradedPrice, not a
    position blend; status is the confirmed COMPLETE."""
    broker = _broker(
        fill=OrderFill(
            broker_order_id="OID-1",
            order_status=OrderStatus.COMPLETE,
            raw_status="TRADED",
            filled_qty=375,
            avg_price=Decimal("4089.30"),
        )
    )
    result = await _place(broker)
    assert result["status"] == OrderStatus.COMPLETE.value
    assert result["avg_price"] == "4089.30"
    assert result["filled_qty"] == 375


# ── scoped marketable-LIMIT ──────────────────────────────────────────────


def test_marketable_limit_basis_aware() -> None:
    sig = MagicMock(raw_payload={"price": 4060})
    assert se._marketable_limit(sig, OrderSide.BUY) == Decimal("4120.90")  # ×1.015
    assert se._marketable_limit(sig, OrderSide.SELL) == Decimal("3999.10")  # ×0.985


def test_marketable_limit_missing_price_returns_none() -> None:
    assert se._marketable_limit(MagicMock(raw_payload={}), OrderSide.BUY) is None
    assert se._marketable_limit(MagicMock(raw_payload={"price": "x"}), OrderSide.BUY) is None
    assert se._marketable_limit(MagicMock(raw_payload={"price": 0}), OrderSide.BUY) is None


def test_scope_is_bse_only_cdsl_excluded() -> None:
    assert _BSE in se._LIMIT_ORDER_STRATEGY_IDS
    assert _CDSL not in se._LIMIT_ORDER_STRATEGY_IDS


async def test_limit_order_type_passed_to_place_order() -> None:
    """When the caller passes order_type=LIMIT + price, the OrderRequest sent
    to the broker carries LIMIT + that price (this is how the scoped 89423ecc
    path reaches Dhan)."""
    broker = _broker(
        fill=OrderFill(
            broker_order_id="OID-1",
            order_status=OrderStatus.COMPLETE,
            raw_status="TRADED",
            filled_qty=375,
            avg_price=Decimal("4089.30"),
        )
    )
    await _place(broker, order_type=OrderType.LIMIT, limit_price=Decimal("4120.90"))
    sent = broker.place_order.await_args.args[0]
    assert sent.order_type is OrderType.LIMIT
    assert sent.price == Decimal("4120.90")


async def test_default_is_market_no_price() -> None:
    """No order_type/limit_price → MARKET, price None (byte-identical to the
    old path; this is what CDSL and every non-scoped strategy gets)."""
    broker = _broker(
        fill=OrderFill(
            broker_order_id="OID-1",
            order_status=OrderStatus.COMPLETE,
            raw_status="TRADED",
            filled_qty=375,
            avg_price=Decimal("4089.30"),
        )
    )
    await _place(broker)
    sent = broker.place_order.await_args.args[0]
    assert sent.order_type is OrderType.MARKET
    assert sent.price is None
