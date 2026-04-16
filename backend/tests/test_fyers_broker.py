"""Unit tests for :class:`app.brokers.fyers.FyersBroker`.

The fyers-apiv3 SDK is fully mocked — no real network traffic. The broker
reaches the SDK through the module-level ``_fyers_module`` attribute, so
each test injects a fake module that returns whatever payloads we need.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.brokers import fyers as fyers_mod
from app.brokers.fyers import FyersBroker
from app.core.exceptions import (
    BrokerAuthError,
    BrokerConnectionError,
    BrokerInsufficientFundsError,
    BrokerInvalidSymbolError,
    BrokerOrderError,
    BrokerOrderRejectedError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
)
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    Exchange,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


def _credentials(**overrides: Any) -> BrokerCredentials:
    base: dict[str, Any] = {
        "broker": BrokerName.FYERS,
        "user_id": "user-1",
        "client_id": "XA00001",
        "api_key": "APP-ID",
        "api_secret": "APP-SECRET",
        "access_token": "access-token-123",
        "refresh_token": "refresh-token-123",
        "token_expires_at": datetime.now(UTC) + timedelta(hours=6),
        "extra": {"redirect_uri": "https://example.test/callback"},
    }
    base.update(overrides)
    return BrokerCredentials(**base)


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Inject a fake fyers_apiv3 module exposing SessionModel + FyersModel."""
    sdk = MagicMock(name="fyers_apiv3.fyersModel")
    sdk.SessionModel = MagicMock(name="SessionModel")
    sdk.FyersModel = MagicMock(name="FyersModel")
    monkeypatch.setattr(fyers_mod, "_fyers_module", sdk)
    return sdk


@pytest.fixture
def fake_client(fake_sdk: MagicMock) -> MagicMock:
    """The ``FyersModel`` instance returned by SDK construction."""
    client = MagicMock(name="FyersModel-instance")
    client.get_profile.return_value = {"s": "ok", "data": {"name": "Test User"}}
    fake_sdk.FyersModel.return_value = client
    return client


@pytest.fixture
async def broker(fake_client: MagicMock) -> Iterator[FyersBroker]:
    b = FyersBroker(_credentials())
    yield b
    await b.aclose()


# ═══════════════════════════════════════════════════════════════════════
# Symbol normalization
# ═══════════════════════════════════════════════════════════════════════


class TestNormalizeSymbol:
    @pytest.mark.parametrize(
        "tv,exchange,expected",
        [
            ("RELIANCE", Exchange.NSE, "NSE:RELIANCE-EQ"),
            ("TCS", Exchange.NSE, "NSE:TCS-EQ"),
            ("RELIANCE", Exchange.BSE, "BSE:RELIANCE-A"),
            ("NIFTY24DECFUT", Exchange.NFO, "NSE:NIFTY24DECFUT"),
            ("NIFTY24DEC23000CE", Exchange.NFO, "NSE:NIFTY24DEC23000CE"),
            ("NIFTY24DEC23000PE", Exchange.NFO, "NSE:NIFTY24DEC23000PE"),
            ("SENSEX24DECFUT", Exchange.BFO, "BSE:SENSEX24DECFUT"),
            ("GOLD24DECFUT", Exchange.MCX, "MCX:GOLD24DECFUT"),
            ("USDINR24DECFUT", Exchange.CDS, "CDS:USDINR24DECFUT"),
        ],
    )
    def test_known_mappings(self, tv: str, exchange: Exchange, expected: str) -> None:
        broker = FyersBroker(_credentials())
        assert broker.normalize_symbol(tv, exchange) == expected

    def test_lowercase_input_uppercased(self) -> None:
        broker = FyersBroker(_credentials())
        assert broker.normalize_symbol("reliance", Exchange.NSE) == "NSE:RELIANCE-EQ"

    def test_already_normalized_passes_through(self) -> None:
        broker = FyersBroker(_credentials())
        assert broker.normalize_symbol("NSE:RELIANCE-EQ", Exchange.NSE) == "NSE:RELIANCE-EQ"

    def test_empty_symbol_raises(self) -> None:
        broker = FyersBroker(_credentials())
        with pytest.raises(BrokerInvalidSymbolError):
            broker.normalize_symbol("   ", Exchange.NSE)


# ═══════════════════════════════════════════════════════════════════════
# OAuth flow
# ═══════════════════════════════════════════════════════════════════════


class TestOAuth:
    def test_generate_auth_url(self, fake_sdk: MagicMock) -> None:
        session = MagicMock()
        session.generate_authcode.return_value = "https://api.fyers.in/auth?code=abc"
        fake_sdk.SessionModel.return_value = session

        broker = FyersBroker(_credentials())
        url = broker.generate_auth_url()
        assert url == "https://api.fyers.in/auth?code=abc"
        fake_sdk.SessionModel.assert_called_once()

    def test_generate_auth_url_without_sdk_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(fyers_mod, "_fyers_module", None)
        broker = FyersBroker(_credentials())
        with pytest.raises(BrokerConnectionError, match="SDK not installed"):
            broker.generate_auth_url()

    async def test_exchange_auth_code_stores_tokens(
        self, fake_sdk: MagicMock
    ) -> None:
        session = MagicMock()
        session.generate_token.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
        }
        fake_sdk.SessionModel.return_value = session

        broker = FyersBroker(_credentials(access_token=None, refresh_token=None))
        result = await broker.exchange_auth_code("auth-code-xyz")

        assert result["access_token"] == "new-access"
        assert broker._access_token == "new-access"
        assert broker._refresh_token == "new-refresh"
        assert broker._token_expires_at is not None
        session.set_token.assert_called_once_with("auth-code-xyz")

    async def test_exchange_auth_code_failure_raises_auth(
        self, fake_sdk: MagicMock
    ) -> None:
        session = MagicMock()
        session.generate_token.return_value = {"s": "error", "message": "bad code"}
        fake_sdk.SessionModel.return_value = session

        broker = FyersBroker(_credentials())
        with pytest.raises(BrokerAuthError, match="token exchange"):
            await broker.exchange_auth_code("bad")


# ═══════════════════════════════════════════════════════════════════════
# Login & session
# ═══════════════════════════════════════════════════════════════════════


class TestLogin:
    async def test_login_pre_warms_profile_call(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        ok = await broker.login()
        assert ok is True
        fake_client.get_profile.assert_called_once()

    async def test_login_without_token_raises(self, fake_sdk: MagicMock) -> None:
        broker = FyersBroker(_credentials(access_token=None, token_expires_at=None))
        with pytest.raises(BrokerAuthError, match="OAuth flow first"):
            await broker.login()

    async def test_login_translates_network_error(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.get_profile.side_effect = ConnectionError("dns failed")
        with pytest.raises(BrokerConnectionError):
            await broker.login()

    async def test_login_translates_session_expired(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.get_profile.return_value = {
            "s": "error",
            "code": -16,
            "message": "session expired",
        }
        with pytest.raises(BrokerSessionExpiredError):
            await broker.login()

    async def test_is_session_valid_true_for_future_expiry(self) -> None:
        broker = FyersBroker(_credentials())
        assert await broker.is_session_valid() is True

    async def test_is_session_valid_false_when_no_token(self) -> None:
        broker = FyersBroker(_credentials(access_token=None, token_expires_at=None))
        assert await broker.is_session_valid() is False

    async def test_is_session_valid_false_when_expired(self) -> None:
        broker = FyersBroker(
            _credentials(token_expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        assert await broker.is_session_valid() is False

    async def test_is_session_valid_naive_datetime_treated_as_utc(self) -> None:
        broker = FyersBroker(
            _credentials(
                token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None)
            )
        )
        assert await broker.is_session_valid() is True

    async def test_is_session_valid_true_when_no_expiry_recorded(self) -> None:
        broker = FyersBroker(_credentials(token_expires_at=None))
        assert await broker.is_session_valid() is True


# ═══════════════════════════════════════════════════════════════════════
# Order management
# ═══════════════════════════════════════════════════════════════════════


class TestPlaceOrder:
    async def test_place_market_order(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "BROKER-ORDER-1",
            "message": "placed",
        }
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
        )
        resp = await broker.place_order(order)
        assert resp.broker_order_id == "BROKER-ORDER-1"
        assert resp.status is OrderStatus.PENDING

        sent_payload = fake_client.place_order.call_args[0][0]
        assert sent_payload["symbol"] == "NSE:RELIANCE-EQ"
        assert sent_payload["qty"] == 10
        assert sent_payload["type"] == 2  # market
        assert sent_payload["side"] == 1  # buy
        assert sent_payload["productType"] == "INTRADAY"

    async def test_place_limit_order_includes_price(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.place_order.return_value = {"s": "ok", "id": "X"}
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.SELL,
            quantity=5,
            order_type=OrderType.LIMIT,
            product_type=ProductType.DELIVERY,
            price=Decimal("2500.50"),
        )
        await broker.place_order(order)
        sent = fake_client.place_order.call_args[0][0]
        assert sent["limitPrice"] == 2500.50
        assert sent["type"] == 1  # limit
        assert sent["side"] == -1  # sell
        assert sent["productType"] == "CNC"

    async def test_place_order_rejected_raises(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.place_order.return_value = {
            "s": "error",
            "code": -1234,
            "message": "freeze qty exceeded",
        }
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
        )
        with pytest.raises(BrokerOrderRejectedError) as exc_info:
            await broker.place_order(order)
        assert exc_info.value.reason == "freeze qty exceeded"

    async def test_place_order_insufficient_funds(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.place_order.return_value = {
            "s": "error",
            "code": -300,
            "message": "insufficient funds",
        }
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
        )
        with pytest.raises(BrokerInsufficientFundsError):
            await broker.place_order(order)

    async def test_place_order_missing_id_raises(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.place_order.return_value = {"s": "ok"}  # no id
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
        )
        with pytest.raises(BrokerOrderError, match="no order id"):
            await broker.place_order(order)


class TestModifyAndCancel:
    async def test_modify_order_payload(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.modify_order.return_value = {"s": "ok", "id": "ORD-1"}
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.BUY,
            quantity=20,
            order_type=OrderType.LIMIT,
            product_type=ProductType.INTRADAY,
            price=Decimal("2400.00"),
        )
        resp = await broker.modify_order("ORD-1", order)
        assert resp.broker_order_id == "ORD-1"
        sent = fake_client.modify_order.call_args[0][0]
        assert sent["id"] == "ORD-1"
        assert sent["qty"] == 20
        assert sent["limitPrice"] == 2400.00

    async def test_cancel_order_returns_true_on_ok(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.cancel_order.return_value = {"s": "ok", "id": "ORD-1"}
        assert await broker.cancel_order("ORD-1") is True
        fake_client.cancel_order.assert_called_once_with({"id": "ORD-1"})


class TestOrderStatus:
    async def test_get_order_status_found(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.orderbook.return_value = {
            "s": "ok",
            "orderBook": [
                {"id": "ORD-1", "status": 6},
                {"id": "ORD-2", "status": 2},
            ],
        }
        assert await broker.get_order_status("ORD-1") is OrderStatus.OPEN
        assert await broker.get_order_status("ORD-2") is OrderStatus.COMPLETE

    async def test_get_order_status_not_found(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.orderbook.return_value = {"s": "ok", "orderBook": []}
        with pytest.raises(BrokerOrderError, match="not found"):
            await broker.get_order_status("MISSING")


# ═══════════════════════════════════════════════════════════════════════
# Portfolio
# ═══════════════════════════════════════════════════════════════════════


class TestPortfolio:
    async def test_get_positions_filters_zero_qty(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.positions.return_value = {
            "s": "ok",
            "netPositions": [
                {
                    "symbol": "NSE:RELIANCE-EQ",
                    "netQty": 10,
                    "netAvg": 2500.0,
                    "ltp": 2550.0,
                    "unrealized_profit": 500.0,
                    "productType": "INTRADAY",
                },
                {
                    "symbol": "NSE:TCS-EQ",
                    "netQty": 0,  # closed-out — must be filtered
                    "netAvg": 3500.0,
                    "ltp": 3600.0,
                    "unrealized_profit": 0,
                    "productType": "INTRADAY",
                },
            ],
        }
        positions = await broker.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "NSE:RELIANCE-EQ"
        assert positions[0].avg_price == Decimal("2500.0")
        assert positions[0].unrealized_pnl == Decimal("500.0")
        assert isinstance(positions[0].unrealized_pnl, Decimal)

    async def test_get_holdings(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.holdings.return_value = {
            "s": "ok",
            "holdings": [
                {
                    "symbol": "NSE:RELIANCE-EQ",
                    "quantity": 10,
                    "costPrice": 2500.0,
                    "ltp": 2550.0,
                    "marketVal": 25500.0,
                    "pl": 500.0,
                }
            ],
        }
        holdings = await broker.get_holdings()
        assert len(holdings) == 1
        h = holdings[0]
        assert h.quantity == 10
        assert h.avg_price == Decimal("2500.0")
        assert h.current_value == Decimal("25500.0")
        assert h.pnl == Decimal("500.0")

    async def test_get_funds_returns_decimal(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.funds.return_value = {
            "s": "ok",
            "fund_limit": [
                {"id": 10, "title": "Available Balance", "equityAmount": 100000.50},
            ],
        }
        funds = await broker.get_funds()
        assert funds == Decimal("100000.50")
        assert isinstance(funds, Decimal)


# ═══════════════════════════════════════════════════════════════════════
# Quotes
# ═══════════════════════════════════════════════════════════════════════


class TestQuotes:
    async def test_get_quote(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.quotes.return_value = {
            "s": "ok",
            "d": [
                {
                    "s": "ok",
                    "n": "NSE:RELIANCE-EQ",
                    "v": {
                        "lp": 2550.25,
                        "bid": 2550.20,
                        "ask": 2550.30,
                        "volume": 1234567,
                        "tt": 1734000000,
                    },
                }
            ],
        }
        q = await broker.get_quote("RELIANCE", Exchange.NSE)
        assert q.symbol == "RELIANCE"
        assert q.exchange is Exchange.NSE
        assert q.ltp == Decimal("2550.25")
        assert q.bid == Decimal("2550.20")
        assert q.ask == Decimal("2550.30")
        assert q.volume == 1234567
        sent = fake_client.quotes.call_args[0][0]
        assert sent["symbols"] == "NSE:RELIANCE-EQ"

    async def test_get_quote_invalid_symbol(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.quotes.return_value = {
            "s": "ok",
            "d": [{"s": "error", "message": "no such symbol"}],
        }
        with pytest.raises(BrokerInvalidSymbolError):
            await broker.get_quote("BADSYM", Exchange.NSE)

    async def test_get_quote_empty_response(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.quotes.return_value = {"s": "ok", "d": []}
        with pytest.raises(BrokerInvalidSymbolError, match="No quote"):
            await broker.get_quote("RELIANCE", Exchange.NSE)


# ═══════════════════════════════════════════════════════════════════════
# Kill switch
# ═══════════════════════════════════════════════════════════════════════


class TestKillSwitch:
    async def test_square_off_all_places_opposite_orders(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.positions.return_value = {
            "s": "ok",
            "netPositions": [
                {
                    "symbol": "NSE:RELIANCE-EQ",
                    "netQty": 10,
                    "netAvg": 2500.0,
                    "ltp": 2550.0,
                    "unrealized_profit": 500.0,
                    "productType": "INTRADAY",
                },
                {
                    "symbol": "NSE:TCS-EQ",
                    "netQty": -5,  # short position → buy to close
                    "netAvg": 3500.0,
                    "ltp": 3450.0,
                    "unrealized_profit": 250.0,
                    "productType": "INTRADAY",
                },
            ],
        }
        fake_client.place_order.return_value = {"s": "ok", "id": "CLOSE"}

        responses = await broker.square_off_all()
        assert len(responses) == 2
        assert all(r.status is OrderStatus.PENDING for r in responses)

        sides = [
            call.args[0]["side"] for call in fake_client.place_order.call_args_list
        ]
        assert sides == [-1, 1]  # sell long, buy back short

    async def test_square_off_continues_after_failure(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.positions.return_value = {
            "s": "ok",
            "netPositions": [
                {
                    "symbol": "NSE:RELIANCE-EQ",
                    "netQty": 10,
                    "netAvg": 2500.0,
                    "ltp": 2550.0,
                    "unrealized_profit": 0,
                    "productType": "INTRADAY",
                },
                {
                    "symbol": "NSE:TCS-EQ",
                    "netQty": 5,
                    "netAvg": 3500.0,
                    "ltp": 3550.0,
                    "unrealized_profit": 0,
                    "productType": "INTRADAY",
                },
            ],
        }
        fake_client.place_order.side_effect = [
            {"s": "ok", "id": "OK-1"},
            {"s": "error", "code": -1, "message": "rejected"},
        ]
        responses = await broker.square_off_all()
        assert len(responses) == 2
        assert responses[0].status is OrderStatus.PENDING
        assert responses[1].status is OrderStatus.REJECTED

    async def test_cancel_all_pending_only_targets_open(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.orderbook.return_value = {
            "s": "ok",
            "orderBook": [
                {"id": "OPEN-1", "status": 6},
                {"id": "DONE-1", "status": 2},
                {"id": "OPEN-2", "status": 4},
            ],
        }
        fake_client.cancel_order.return_value = {"s": "ok"}

        cancelled = await broker.cancel_all_pending()
        assert cancelled == 2
        cancelled_ids = [
            call.args[0]["id"] for call in fake_client.cancel_order.call_args_list
        ]
        assert cancelled_ids == ["OPEN-1", "OPEN-2"]


# ═══════════════════════════════════════════════════════════════════════
# Retry / error mapping
# ═══════════════════════════════════════════════════════════════════════


class TestRetryAndErrors:
    async def test_transient_network_error_retries(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.funds.side_effect = [
            ConnectionError("flaky"),
            ConnectionError("flaky"),
            {"s": "ok", "fund_limit": [
                {"id": 10, "title": "Available Balance", "equityAmount": 50.0}
            ]},
        ]
        funds = await broker.get_funds()
        assert funds == Decimal("50.0")
        assert fake_client.funds.call_count == 3

    async def test_retry_gives_up_after_three_attempts(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.funds.side_effect = ConnectionError("permadown")
        with pytest.raises(BrokerConnectionError):
            await broker.get_funds()
        assert fake_client.funds.call_count == 3

    async def test_rate_limit_carries_retry_after(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.funds.side_effect = [
            {"s": "error", "code": -310, "message": "rate limit", "retry_after": 0.5},
            {"s": "error", "code": -310, "message": "rate limit", "retry_after": 0.5},
            {"s": "error", "code": -310, "message": "rate limit", "retry_after": 0.5},
        ]
        with pytest.raises(BrokerRateLimitError) as exc_info:
            await broker.get_funds()
        assert exc_info.value.retry_after == 0.5

    async def test_session_expired_triggers_relogin(
        self, broker: FyersBroker, fake_client: MagicMock, fake_sdk: MagicMock
    ) -> None:
        # First call → session expired, second → success.
        fake_client.funds.side_effect = [
            {"s": "error", "code": -16, "message": "expired"},
            {"s": "ok", "fund_limit": [
                {"id": 10, "title": "Available Balance", "equityAmount": 1.0}
            ]},
        ]
        # SDK should be reconstructed on relogin → return a fresh client whose
        # get_profile succeeds so the inner login passes.
        fresh_client = MagicMock()
        fresh_client.get_profile.return_value = {"s": "ok"}
        fresh_client.funds = fake_client.funds  # reuse the side_effect iterator
        fake_sdk.FyersModel.side_effect = [fake_client, fresh_client]

        funds = await broker.get_funds()
        assert funds == Decimal("1.0")

    async def test_unexpected_sdk_exception_wraps_as_connection_error(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.funds.side_effect = RuntimeError("unexpected SDK bug")
        with pytest.raises(BrokerConnectionError, match="unexpected SDK error"):
            await broker.get_funds()


# ═══════════════════════════════════════════════════════════════════════
# HTTP client lifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestHttpClientLifecycle:
    async def test_login_creates_pooled_http_client(
        self, broker: FyersBroker
    ) -> None:
        await broker.login()
        assert isinstance(broker._http, httpx.AsyncClient)
        # Limits reflect our configured pool size.
        limits = broker._http._transport._pool._max_connections  # type: ignore[attr-defined]
        assert limits == fyers_mod._HTTP_POOL_SIZE

    async def test_aclose_releases_client(self, broker: FyersBroker) -> None:
        await broker.login()
        client = broker._http
        assert client is not None
        await broker.aclose()
        assert broker._http is None
        # Idempotent — second close must not raise.
        await broker.aclose()


# ═══════════════════════════════════════════════════════════════════════
# Registration sanity
# ═══════════════════════════════════════════════════════════════════════


class TestBrokerRegistration:
    def test_broker_name_is_fyers(self) -> None:
        assert FyersBroker.broker_name is BrokerName.FYERS


# ═══════════════════════════════════════════════════════════════════════
# Helpers & branches
# ═══════════════════════════════════════════════════════════════════════


class TestHelpers:
    def test_money_handles_none(self) -> None:
        assert fyers_mod._money(None) == Decimal("0")

    def test_money_passthrough_for_decimal(self) -> None:
        d = Decimal("3.14")
        assert fyers_mod._money(d) is d

    def test_money_converts_via_str(self) -> None:
        # 0.1 + 0.2 must not creep in as a binary float remainder.
        assert fyers_mod._money(0.1) == Decimal("0.1")

    def test_raise_for_response_rejects_non_dict(self) -> None:
        with pytest.raises(BrokerOrderError, match="non-dict"):
            fyers_mod._raise_for_response("nonsense", "place_order", "fyers")

    def test_raise_for_response_unknown_code_non_order_op(self) -> None:
        with pytest.raises(BrokerOrderError) as exc_info:
            fyers_mod._raise_for_response(
                {"s": "error", "code": -99999, "message": "weird"},
                "funds",
                "fyers",
            )
        assert not isinstance(exc_info.value, BrokerOrderRejectedError)

    def test_exchange_from_symbol_branches(self) -> None:
        assert FyersBroker._exchange_from_symbol("BSE:RELIANCE-A") is Exchange.BSE
        assert FyersBroker._exchange_from_symbol("MCX:GOLD24DECFUT") is Exchange.MCX
        assert FyersBroker._exchange_from_symbol("CDS:USDINR24DECFUT") is Exchange.CDS
        assert FyersBroker._exchange_from_symbol("NSE:RELIANCE-EQ") is Exchange.NSE
        # Unprefixed symbol → fall back to NSE.
        assert FyersBroker._exchange_from_symbol("RELIANCE-EQ") is Exchange.NSE

    def test_product_from_fyers_all_branches(self) -> None:
        assert FyersBroker._product_from_fyers("INTRADAY") is ProductType.INTRADAY
        assert FyersBroker._product_from_fyers("CNC") is ProductType.DELIVERY
        assert FyersBroker._product_from_fyers("MARGIN") is ProductType.MARGIN
        assert FyersBroker._product_from_fyers("BO") is ProductType.BO
        assert FyersBroker._product_from_fyers("CO") is ProductType.CO
        # Unknown → safe default.
        assert FyersBroker._product_from_fyers("???") is ProductType.INTRADAY

    def test_build_model_without_sdk_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(fyers_mod, "_fyers_module", None)
        broker = FyersBroker(_credentials())
        with pytest.raises(BrokerConnectionError, match="SDK not installed"):
            broker._build_model()


class TestEdgeCases:
    async def test_get_holdings_filters_zero_qty(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.holdings.return_value = {
            "s": "ok",
            "holdings": [
                {"symbol": "NSE:DUD-EQ", "quantity": 0, "costPrice": 0, "ltp": 0},
                {
                    "symbol": "NSE:RELIANCE-EQ",
                    "quantity": 5,
                    "costPrice": 2500.0,
                    "ltp": 2550.0,
                    "marketVal": 12750.0,
                    "pl": 250.0,
                },
            ],
        }
        holdings = await broker.get_holdings()
        assert len(holdings) == 1
        assert holdings[0].symbol == "NSE:RELIANCE-EQ"

    async def test_get_funds_falls_back_to_sum(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        # No row matches "Available Balance" → fallback path runs.
        fake_client.funds.return_value = {
            "s": "ok",
            "fund_limit": [
                {"id": 1, "title": "Total", "equityAmount": 100.0},
                {"id": 2, "title": "Used", "equityAmount": 25.5},
            ],
        }
        funds = await broker.get_funds()
        assert funds == Decimal("125.5")

    async def test_cancel_all_pending_swallows_failure(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        fake_client.orderbook.return_value = {
            "s": "ok",
            "orderBook": [
                {"id": "OPEN-1", "status": 6},
                {"id": "OPEN-2", "status": 6},
            ],
        }
        # First cancel succeeds, second raises — total must still be 1.
        fake_client.cancel_order.side_effect = [
            {"s": "ok"},
            BrokerOrderError("nope", "fyers"),
        ]
        cancelled = await broker.cancel_all_pending()
        assert cancelled == 1
