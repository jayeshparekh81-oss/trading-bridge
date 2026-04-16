"""Placeholder broker classes for integrations that ship later.

Each class is a **complete** :class:`BrokerInterface` implementation in
the sense that every abstract method is defined — but every method
raises :class:`NotImplementedError` with a helpful message pointing the
user at the currently-supported brokers.

Why ship stubs at all?
    * The registry can return "6 brokers supported" so product /
      marketing work unblocks ahead of the actual integration.
    * Type-checkers and :func:`app.brokers.registry.supported_brokers`
      treat ``BrokerName`` as exhaustive — every enum value has a class.
    * When a user accidentally selects an unsupported broker, they see
      a clear message instead of a cryptic ``KeyError`` from the
      registry.

When a real implementation arrives, replace the class here with the
concrete module and update ``BROKER_REGISTRY``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from app.brokers.base import BrokerInterface
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    Exchange,
    Holding,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
    Quote,
)


_SUPPORTED_NOTE = "Currently supports Fyers and Dhan."


def _raise(broker: str, phase: str) -> None:
    """Uniform error message across every stub method."""
    raise NotImplementedError(
        f"{broker} integration coming in {phase}. {_SUPPORTED_NOTE}"
    )


class _StubBroker(BrokerInterface):
    """Shared skeleton — subclasses only need to declare the broker_name + phase.

    Declared on the ABC so concrete stubs can inherit the full set of
    abstract methods with one implementation each. Every method calls
    :func:`_raise` so behaviour is uniform.
    """

    phase: ClassVar[str] = "a future phase"

    def __init__(self, credentials: BrokerCredentials) -> None:  # noqa: D401
        # Accept and discard — a user may have a placeholder credential
        # row in the DB that references this broker. Do NOT raise here;
        # construction should be side-effect-free. Errors surface only
        # when the caller actually attempts an operation.
        self._credentials = credentials

    def _boom(self) -> None:
        _raise(self.broker_name.value.title(), self.phase)

    async def login(self) -> bool:
        self._boom()
        return False  # pragma: no cover — unreachable

    async def is_session_valid(self) -> bool:
        self._boom()
        return False  # pragma: no cover

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        self._boom()
        raise AssertionError  # pragma: no cover

    async def modify_order(
        self, broker_order_id: str, order: OrderRequest
    ) -> OrderResponse:
        self._boom()
        raise AssertionError  # pragma: no cover

    async def cancel_order(self, broker_order_id: str) -> bool:
        self._boom()
        return False  # pragma: no cover

    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        self._boom()
        raise AssertionError  # pragma: no cover

    async def get_positions(self) -> list[Position]:
        self._boom()
        return []  # pragma: no cover

    async def get_holdings(self) -> list[Holding]:
        self._boom()
        return []  # pragma: no cover

    async def get_funds(self) -> Decimal:
        self._boom()
        return Decimal("0")  # pragma: no cover

    async def get_quote(self, symbol: str, exchange: Exchange) -> Quote:
        self._boom()
        raise AssertionError  # pragma: no cover

    async def square_off_all(self) -> list[OrderResponse]:
        self._boom()
        return []  # pragma: no cover

    async def cancel_all_pending(self) -> int:
        self._boom()
        return 0  # pragma: no cover

    def normalize_symbol(
        self, tradingview_symbol: str, exchange: Exchange
    ) -> str:
        self._boom()
        return tradingview_symbol  # pragma: no cover


class ShoonyaBroker(_StubBroker):
    """Shoonya / Finvasia — Phase 3."""

    broker_name: ClassVar[BrokerName] = BrokerName.SHOONYA
    phase: ClassVar[str] = "Phase 3"


class ZerodhaBroker(_StubBroker):
    """Zerodha (Kite Connect) — Phase 4."""

    broker_name: ClassVar[BrokerName] = BrokerName.ZERODHA
    phase: ClassVar[str] = "Phase 4"


class UpstoxBroker(_StubBroker):
    """Upstox — Phase 5."""

    broker_name: ClassVar[BrokerName] = BrokerName.UPSTOX
    phase: ClassVar[str] = "Phase 5"


class AngelOneBroker(_StubBroker):
    """Angel One (SmartAPI) — Phase 6."""

    broker_name: ClassVar[BrokerName] = BrokerName.ANGELONE
    phase: ClassVar[str] = "Phase 6"


__all__ = [
    "AngelOneBroker",
    "ShoonyaBroker",
    "UpstoxBroker",
    "ZerodhaBroker",
]
