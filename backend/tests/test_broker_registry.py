"""Unit tests for :mod:`app.brokers.registry`."""

from __future__ import annotations

import pytest

from app.brokers import registry
from app.brokers.base import BrokerInterface
from app.brokers.fyers import FyersBroker
from app.schemas.broker import BrokerName


class TestRegistry:
    def test_fyers_resolves_to_fyers_broker(self) -> None:
        cls = registry.get_broker_class(BrokerName.FYERS)
        assert cls is FyersBroker
        assert issubclass(cls, BrokerInterface)

    def test_unsupported_broker_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="dhan"):
            registry.get_broker_class(BrokerName.DHAN)

    def test_error_message_lists_supported_brokers(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            registry.get_broker_class(BrokerName.ZERODHA)
        assert "fyers" in str(exc_info.value)
        assert "Supported brokers" in str(exc_info.value)

    def test_supported_brokers_returns_only_implemented(self) -> None:
        supported = registry.supported_brokers()
        assert BrokerName.FYERS in supported
        assert BrokerName.DHAN not in supported

    def test_registry_only_contains_broker_interface_subclasses(self) -> None:
        for cls in registry.BROKER_REGISTRY.values():
            assert issubclass(cls, BrokerInterface)
