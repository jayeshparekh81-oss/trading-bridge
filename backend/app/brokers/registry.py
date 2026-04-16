"""Broker registry — maps :class:`BrokerName` enum values to broker classes.

Services depend on :class:`BrokerInterface` only; they look up the
concrete implementation through :func:`get_broker_class`. That is the
ONLY place in the codebase that imports a concrete broker module, which
makes adding a new broker (Dhan, Zerodha, …) a one-line change here.
"""

from __future__ import annotations

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

#: Single source of truth. Keys cover EVERY :class:`BrokerName` value —
#: implemented brokers point at their concrete class; the rest point at
#: :mod:`app.brokers.stubs` so the UI/API can advertise them as
#: "coming soon" instead of surfacing a raw ``KeyError``.
BROKER_REGISTRY: dict[BrokerName, type[BrokerInterface]] = {
    BrokerName.FYERS: FyersBroker,
    BrokerName.DHAN: DhanBroker,
    BrokerName.SHOONYA: ShoonyaBroker,
    BrokerName.ZERODHA: ZerodhaBroker,
    BrokerName.UPSTOX: UpstoxBroker,
    BrokerName.ANGELONE: AngelOneBroker,
}

#: Brokers whose class is a real integration (not a stub). The webhook
#: and order routing layers gate on this set when deciding whether a
#: user's credential row can be used for live trading.
FULLY_IMPLEMENTED: frozenset[BrokerName] = frozenset(
    {BrokerName.FYERS, BrokerName.DHAN}
)


def get_broker_class(broker_name: BrokerName) -> type[BrokerInterface]:
    """Resolve a broker name to its concrete class.

    Args:
        broker_name: Enum value identifying the desired broker.

    Returns:
        The class object — caller instantiates it with credentials.

    Raises:
        ValueError: ``broker_name`` is not (yet) implemented.
    """
    try:
        return BROKER_REGISTRY[broker_name]
    except KeyError as exc:
        supported = ", ".join(sorted(b.value for b in BROKER_REGISTRY))
        raise ValueError(
            f"Broker '{broker_name.value}' is not supported. "
            f"Supported brokers: {supported}."
        ) from exc


def supported_brokers() -> list[BrokerName]:
    """Return brokers with a registered implementation (incl. stubs), in enum order."""
    return [b for b in BrokerName if b in BROKER_REGISTRY]


def fully_implemented_brokers() -> list[BrokerName]:
    """Return brokers that are live (exclude coming-soon stubs)."""
    return [b for b in BrokerName if b in FULLY_IMPLEMENTED]


__all__ = [
    "BROKER_REGISTRY",
    "FULLY_IMPLEMENTED",
    "fully_implemented_brokers",
    "get_broker_class",
    "supported_brokers",
]
