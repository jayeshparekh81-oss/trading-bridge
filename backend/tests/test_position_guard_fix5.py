"""Fix #5 — defensive position guard in ``_live_place_order``.

Incident 2026-05-20 (BSE LTD signal e9b654ea-...): Dhan returned HTTP
200 + orderStatus=REJECTED for an insufficient-funds case. The Dhan
adapter (pre-Fix #4) returned an ``OrderResponse(status=REJECTED)``
without raising, and the strategy executor proceeded to create a
phantom ``strategy_position`` row.

Fix #4 makes the Dhan adapter raise on REJECTED. This Fix #5 adds a
defensive secondary check in ``_live_place_order`` so that any broker
adapter — current Fyers, future ones — that returns a non-success
status without raising still cannot lead to phantom position creation.

These tests exercise the guard directly (no DB needed — the function
under test only touches the broker mock) so they're robust against
the pre-existing JSONB-on-SQLite fixture problem in the integration
conftest.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.brokers.base import BrokerInterface
from app.core.exceptions import BrokerError, BrokerOrderRejectedError
from app.schemas.broker import (
    BrokerName,
    Exchange,
    OrderFill,
    OrderResponse,
    OrderSide,
    OrderStatus,
)
from app.services.strategy_executor import _live_place_order


def _make_broker(
    *,
    funds: Decimal = Decimal("500000"),
    place_order_response: OrderResponse | None = None,
    place_order_side_effect: Exception | None = None,
) -> MagicMock:
    """Build a BrokerInterface mock — only the methods _live_place_order calls."""
    broker = MagicMock(spec=BrokerInterface)
    broker.broker_name = BrokerName.DHAN
    broker.is_session_valid = AsyncMock(return_value=True)
    broker.login = AsyncMock(return_value=True)
    broker.validate_symbol = AsyncMock(return_value=None)
    broker.get_funds = AsyncMock(return_value=funds)
    if place_order_side_effect is not None:
        broker.place_order = AsyncMock(side_effect=place_order_side_effect)
    else:
        broker.place_order = AsyncMock(
            return_value=place_order_response
            or OrderResponse(
                broker_order_id="OK-1",
                status=OrderStatus.PENDING,
                message="placed",
                raw_response={},
            )
        )
    # confirm_fill is auto-mocked by spec=BrokerInterface; give it a real
    # OrderFill so the executor's fill-gate (COMPLETE + filled_qty > 0) passes
    # and a position is created. Scenarios that need a REJECTED/no-fill set
    # their own confirm_fill return value.
    broker.confirm_fill = AsyncMock(
        return_value=OrderFill(
            broker_order_id="OK-1",
            order_status=OrderStatus.COMPLETE,
            filled_qty=10**6,
            avg_price=Decimal("100"),
        )
    )
    return broker


# ═══════════════════════════════════════════════════════════════════════
# Defensive guard: broker returns non-success status without raising
# ═══════════════════════════════════════════════════════════════════════


async def test_broker_returns_rejected_raises_broker_order_rejected_error() -> None:
    """Misbehaving broker returns REJECTED without raising → executor's
    defensive check converts to BrokerOrderRejectedError so no phantom
    position can be created downstream."""
    broker = _make_broker(
        place_order_response=OrderResponse(
            broker_order_id="MISBEHAVE-1",
            status=OrderStatus.REJECTED,
            message="Insufficient margin",
            raw_response={"orderStatus": "REJECTED"},
        )
    )

    with pytest.raises(BrokerOrderRejectedError) as exc:
        await _live_place_order(
            broker=broker,
            user_id="11111111-1111-1111-1111-111111111111",
            symbol="NIFTY",
            side=OrderSide.BUY,
            quantity=1,
            lot_size=1,
        )

    assert "Insufficient margin" in exc.value.reason
    # OrderStatus enum values are lowercase ("rejected"); raw broker text
    # would be captured in raw_response if needed.
    assert exc.value.metadata.get("status") == OrderStatus.REJECTED.value
    assert exc.value.metadata.get("broker_order_id") == "MISBEHAVE-1"


async def test_broker_returns_cancelled_raises_broker_order_rejected_error() -> None:
    """Guard fires for OrderStatus.CANCELLED (EXPIRED maps to CANCELLED
    via _STATUS_FROM_DHAN, so this also covers EXPIRED)."""
    broker = _make_broker(
        place_order_response=OrderResponse(
            broker_order_id="CANC-1",
            status=OrderStatus.CANCELLED,
            message="Cancelled by exchange",
            raw_response={"orderStatus": "CANCELLED"},
        )
    )

    with pytest.raises(BrokerOrderRejectedError) as exc:
        await _live_place_order(
            broker=broker,
            user_id="11111111-1111-1111-1111-111111111111",
            symbol="NIFTY",
            side=OrderSide.BUY,
            quantity=1,
            lot_size=1,
        )
    assert "Cancelled" in exc.value.reason


async def test_broker_returns_pending_returns_normally() -> None:
    """Regression: a PENDING *ack* is NOT a rejection — the executor proceeds
    to confirm the fill and (on a confirmed TRADED) create the position.

    Post-2026-06-01 the returned ``status`` reflects the CONFIRMED fill
    (``confirm_fill`` → COMPLETE here), not the lagging place_order ack."""
    broker = _make_broker(
        place_order_response=OrderResponse(
            broker_order_id="PEND-1",
            status=OrderStatus.PENDING,
            message="placed, awaiting fill",
            raw_response={"orderStatus": "PENDING"},
        )
    )

    result = await _live_place_order(
        broker=broker,
        user_id="11111111-1111-1111-1111-111111111111",
        symbol="NIFTY",
        side=OrderSide.BUY,
        quantity=1,
        lot_size=1,
    )
    assert result["broker_order_id"] == "PEND-1"
    assert result["status"] == OrderStatus.COMPLETE.value  # confirmed fill


async def test_broker_returns_open_returns_normally() -> None:
    """Regression: an OPEN ack (limit order resting in book) is NOT a
    rejection — must not raise; the executor confirms the fill and returns the
    CONFIRMED status (COMPLETE here)."""
    broker = _make_broker(
        place_order_response=OrderResponse(
            broker_order_id="OPEN-1",
            status=OrderStatus.OPEN,
            message="resting in book",
            raw_response={"orderStatus": "OPEN"},
        )
    )

    result = await _live_place_order(
        broker=broker,
        user_id="11111111-1111-1111-1111-111111111111",
        symbol="NIFTY",
        side=OrderSide.BUY,
        quantity=1,
        lot_size=1,
    )
    assert result["status"] == OrderStatus.COMPLETE.value  # confirmed fill


async def test_broker_returns_complete_returns_normally() -> None:
    """Regression: COMPLETE / TRADED — happy path, must not raise."""
    broker = _make_broker(
        place_order_response=OrderResponse(
            broker_order_id="DONE-1",
            status=OrderStatus.COMPLETE,
            message="filled",
            raw_response={"orderStatus": "TRADED"},
        )
    )

    result = await _live_place_order(
        broker=broker,
        user_id="11111111-1111-1111-1111-111111111111",
        symbol="NIFTY",
        side=OrderSide.BUY,
        quantity=1,
        lot_size=1,
    )
    assert result["broker_order_id"] == "DONE-1"
    assert result["status"] == OrderStatus.COMPLETE.value


async def test_broker_raising_broker_error_still_propagates() -> None:
    """Regression: when the broker itself raises (Fix #4's path on Dhan)
    the existing ``except BrokerError: raise`` chain re-raises cleanly.
    The defensive guard runs AFTER that block, so it must not interfere
    with the raise path."""
    broker = _make_broker(
        place_order_side_effect=BrokerOrderRejectedError(
            "Dhan rejected place_order: Insufficient balance",
            BrokerName.DHAN.value,
            reason="Insufficient balance",
        )
    )

    with pytest.raises(BrokerOrderRejectedError) as exc:
        await _live_place_order(
            broker=broker,
            user_id="11111111-1111-1111-1111-111111111111",
            symbol="NIFTY",
            side=OrderSide.BUY,
            quantity=1,
            lot_size=1,
        )
    assert "Insufficient balance" in exc.value.reason


async def test_rejection_error_is_broker_error_subclass() -> None:
    """Sanity: BrokerOrderRejectedError must be a BrokerError so callers
    that catch BrokerError (widened webhook handler in strategy_webhook)
    still catch our defensive raise."""
    assert issubclass(BrokerOrderRejectedError, BrokerError)
