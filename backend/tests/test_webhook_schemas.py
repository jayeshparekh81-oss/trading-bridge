"""Unit tests for :mod:`app.schemas.webhook`."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.broker import Exchange, OrderType, ProductType
from app.schemas.webhook import (
    WebhookAction,
    WebhookPayload,
    WebhookResponse,
    WebhookResponseStatus,
)


def _base(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "action": WebhookAction.BUY,
        "symbol": "RELIANCE",
        "exchange": Exchange.NSE,
        "order_type": OrderType.MARKET,
        "product_type": ProductType.INTRADAY,
        "quantity": 10,
    }
    data.update(overrides)
    return data


class TestWebhookPayload:
    def test_minimal_parses(self) -> None:
        payload = WebhookPayload.model_validate(_base())
        assert payload.action is WebhookAction.BUY
        assert payload.quantity == 10
        assert payload.order_type is OrderType.MARKET

    def test_defaults_applied(self) -> None:
        payload = WebhookPayload.model_validate(
            {"action": "BUY", "symbol": "X", "quantity": 1}
        )
        assert payload.exchange is Exchange.NSE
        assert payload.order_type is OrderType.MARKET
        assert payload.product_type is ProductType.INTRADAY

    def test_market_with_price_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not carry a price"):
            WebhookPayload.model_validate(_base(price=Decimal("100")))

    def test_limit_requires_price(self) -> None:
        with pytest.raises(ValidationError, match="LIMIT order requires"):
            WebhookPayload.model_validate(_base(order_type=OrderType.LIMIT))

    def test_limit_ok_with_price(self) -> None:
        payload = WebhookPayload.model_validate(
            _base(order_type=OrderType.LIMIT, price=Decimal("100"))
        )
        assert payload.price == Decimal("100")

    def test_sl_requires_both(self) -> None:
        with pytest.raises(ValidationError, match="SL order requires"):
            WebhookPayload.model_validate(_base(order_type=OrderType.SL))

    def test_sl_m_requires_trigger(self) -> None:
        with pytest.raises(ValidationError, match="SL_M order requires"):
            WebhookPayload.model_validate(_base(order_type=OrderType.SL_M))

    def test_sl_m_with_price_rejected(self) -> None:
        with pytest.raises(ValidationError, match="SL_M order must not carry"):
            WebhookPayload.model_validate(
                _base(
                    order_type=OrderType.SL_M,
                    price=Decimal("100"),
                    trigger_price=Decimal("99"),
                )
            )

    def test_negative_quantity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WebhookPayload.model_validate(_base(quantity=0))

    def test_extra_fields_ignored(self) -> None:
        payload = WebhookPayload.model_validate(
            _base(description="tradingview noise", timestamp="2026-04-16T10:00:00Z")
        )
        assert payload.symbol == "RELIANCE"

    def test_frozen(self) -> None:
        payload = WebhookPayload.model_validate(_base())
        with pytest.raises(ValidationError):
            payload.symbol = "INFY"  # type: ignore[misc]


class TestWebhookResponse:
    def test_success_shape(self) -> None:
        r = WebhookResponse(
            status=WebhookResponseStatus.SUCCESS,
            order_id="OID-1",
            latency_ms=42,
        )
        assert r.status is WebhookResponseStatus.SUCCESS
        assert r.latency_ms == 42

    def test_negative_latency_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WebhookResponse(status=WebhookResponseStatus.SUCCESS, latency_ms=-1)

    def test_extra_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WebhookResponse(
                status=WebhookResponseStatus.SUCCESS,
                latency_ms=1,
                unexpected="bad",  # type: ignore[call-arg]
            )
