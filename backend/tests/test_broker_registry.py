"""Unit tests for :mod:`app.brokers.registry`."""

from __future__ import annotations

from app.brokers import registry
from app.brokers.base import BrokerInterface
from app.brokers.dhan import DhanBroker
from app.brokers.fyers import FyersBroker
from app.brokers.stubs import (
    AngelOneBroker,
    ShoonyaBroker,
    UpstoxBroker,
    ZerodhaBroker,
)
from app.schemas.broker import BrokerName


class TestRegistry:
    def test_fyers_resolves_to_fyers_broker(self) -> None:
        cls = registry.get_broker_class(BrokerName.FYERS)
        assert cls is FyersBroker
        assert issubclass(cls, BrokerInterface)

    def test_dhan_resolves_to_dhan_broker(self) -> None:
        cls = registry.get_broker_class(BrokerName.DHAN)
        assert cls is DhanBroker

    def test_stubs_registered_for_coming_soon_brokers(self) -> None:
        assert registry.get_broker_class(BrokerName.SHOONYA) is ShoonyaBroker
        assert registry.get_broker_class(BrokerName.ZERODHA) is ZerodhaBroker
        assert registry.get_broker_class(BrokerName.UPSTOX) is UpstoxBroker
        assert registry.get_broker_class(BrokerName.ANGELONE) is AngelOneBroker

    def test_supported_brokers_covers_all_enum_values(self) -> None:
        supported = registry.supported_brokers()
        assert set(supported) == set(BrokerName)

    def test_fully_implemented_only_fyers_and_dhan(self) -> None:
        live = registry.fully_implemented_brokers()
        assert set(live) == {BrokerName.FYERS, BrokerName.DHAN}

    def test_registry_only_contains_broker_interface_subclasses(self) -> None:
        for cls in registry.BROKER_REGISTRY.values():
            assert issubclass(cls, BrokerInterface)
