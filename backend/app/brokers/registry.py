"""Broker registry — maps :class:`BrokerName` enum values to broker classes.

Services depend on :class:`BrokerInterface` only; they look up the
concrete implementation through :func:`get_broker_class`. That is the
ONLY place in the codebase that imports a concrete broker module, which
makes adding a new broker (Dhan, Zerodha, …) a one-line change here.
"""

from __future__ import annotations

from app.brokers.base import BrokerInterface
from app.brokers.fyers import FyersBroker
from app.schemas.broker import BrokerName

#: Single source of truth — keep keys covering every value in BrokerName
#: that has a working implementation. Brokers without an integration yet
#: simply omit themselves; :func:`get_broker_class` raises a clear error.
BROKER_REGISTRY: dict[BrokerName, type[BrokerInterface]] = {
    BrokerName.FYERS: FyersBroker,
}


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
    """Return brokers with a registered implementation, in enum order."""
    return [b for b in BrokerName if b in BROKER_REGISTRY]


__all__ = ["BROKER_REGISTRY", "get_broker_class", "supported_brokers"]
