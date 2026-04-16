"""Tests for coming-soon broker stubs.

The purpose of this suite is defensive — the stubs exist so the broker
registry can advertise six integrations, but every operational call must
raise :class:`NotImplementedError` with a message that names the
supported brokers. A regression here would silently ship a broken
integration.
"""

from __future__ import annotations

import pytest

from app.brokers.stubs import (
    AngelOneBroker,
    ShoonyaBroker,
    UpstoxBroker,
    ZerodhaBroker,
)
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    Exchange,
    OrderRequest,
    OrderSide,
    OrderType,
    ProductType,
)


def _creds(broker: BrokerName) -> BrokerCredentials:
    return BrokerCredentials(
        broker=broker,
        user_id="22222222-2222-2222-2222-222222222222",
        client_id="x",
        api_key="k",
        api_secret="s",
    )


STUBS = [
    (ShoonyaBroker, BrokerName.SHOONYA, "Phase 3"),
    (ZerodhaBroker, BrokerName.ZERODHA, "Phase 4"),
    (UpstoxBroker, BrokerName.UPSTOX, "Phase 5"),
    (AngelOneBroker, BrokerName.ANGELONE, "Phase 6"),
]


def _order() -> OrderRequest:
    return OrderRequest(
        symbol="X",
        exchange=Exchange.NSE,
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
        product_type=ProductType.INTRADAY,
    )


class TestStubs:
    @pytest.mark.parametrize("cls,name,phase", STUBS)
    def test_construction_side_effect_free(
        self, cls: type, name: BrokerName, phase: str
    ) -> None:
        # Must not raise.
        cls(_creds(name))

    @pytest.mark.parametrize("cls,name,phase", STUBS)
    def test_broker_name_set(
        self, cls: type, name: BrokerName, phase: str
    ) -> None:
        assert cls.broker_name is name

    @pytest.mark.parametrize("cls,name,phase", STUBS)
    async def test_phase_in_message(
        self, cls: type, name: BrokerName, phase: str
    ) -> None:
        inst = cls(_creds(name))
        with pytest.raises(NotImplementedError) as exc:
            await inst.login()
        msg = str(exc.value)
        assert phase in msg
        assert "Fyers" in msg and "Dhan" in msg

    @pytest.mark.parametrize("cls,name,phase", STUBS)
    async def test_every_method_raises(
        self, cls: type, name: BrokerName, phase: str
    ) -> None:
        inst = cls(_creds(name))
        with pytest.raises(NotImplementedError):
            await inst.login()
        with pytest.raises(NotImplementedError):
            await inst.is_session_valid()
        with pytest.raises(NotImplementedError):
            await inst.place_order(_order())
        with pytest.raises(NotImplementedError):
            await inst.modify_order("x", _order())
        with pytest.raises(NotImplementedError):
            await inst.cancel_order("x")
        with pytest.raises(NotImplementedError):
            await inst.get_order_status("x")
        with pytest.raises(NotImplementedError):
            await inst.get_positions()
        with pytest.raises(NotImplementedError):
            await inst.get_holdings()
        with pytest.raises(NotImplementedError):
            await inst.get_funds()
        with pytest.raises(NotImplementedError):
            await inst.get_quote("X", Exchange.NSE)
        with pytest.raises(NotImplementedError):
            await inst.square_off_all()
        with pytest.raises(NotImplementedError):
            await inst.cancel_all_pending()
        with pytest.raises(NotImplementedError):
            inst.normalize_symbol("X", Exchange.NSE)
