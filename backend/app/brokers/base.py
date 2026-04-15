"""``BrokerInterface`` — the abstract contract every broker integration implements.

Adding a new broker = implementing this one interface in a new file under
``app/brokers/`` and registering it. Services never import concrete broker
classes — they depend on this abstraction only, which keeps the trading
engine broker-agnostic.

Har broker ke paas apna API format hota hai; ye interface ek normalized
view deti hai. Broker-specific quirks (symbol format, auth flow, rate
limits, TOTP, etc.) har subclass ke andar hi contained rehte hain.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import ClassVar

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


class BrokerInterface(ABC):
    """Abstract base class for every broker integration.

    Subclasses MUST:
        * Set the ``broker_name`` class attribute.
        * Implement every ``@abstractmethod`` below.
        * Raise specific exceptions from ``app.core.exceptions`` — never
          bare ``Exception`` — so upstream services can react correctly.

    Instances are **per-user**: one ``BrokerInterface`` instance wraps one
    user's session with one broker. Do not share instances across users.
    """

    #: Broker identity — subclasses override this with their ``BrokerName`` value.
    broker_name: ClassVar[BrokerName]

    @abstractmethod
    def __init__(self, credentials: BrokerCredentials) -> None:
        """Bootstrap the broker client with a user's decrypted credentials.

        Args:
            credentials: Decrypted credentials for this user. The subclass
                typically stashes the HTTP client and tokens on ``self``
                but must NOT perform network I/O here — do that in
                :meth:`login`.
        """

    # ══════════════════════════════════════════════════════════════════
    # Authentication
    # ══════════════════════════════════════════════════════════════════

    @abstractmethod
    async def login(self) -> bool:
        """Generate or refresh the broker session.

        Called on first use and whenever :meth:`is_session_valid` returns
        ``False``. Implementations should update the in-memory access
        token and expiry; persisting the new token back to the DB is the
        caller's responsibility.

        Returns:
            ``True`` if a usable session is established, ``False`` if the
            credentials were rejected.

        Raises:
            BrokerAuthError: When the broker's auth endpoint returns an
                unrecoverable error (bad credentials, account locked).
            BrokerConnectionError: For network-level failures.
        """

    @abstractmethod
    async def is_session_valid(self) -> bool:
        """Cheap check whether the current access token is still usable.

        Should NOT make a network round-trip unless absolutely necessary —
        prefer comparing ``token_expires_at`` against ``datetime.now``.
        """

    # ══════════════════════════════════════════════════════════════════
    # Order management
    # ══════════════════════════════════════════════════════════════════

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place a new order with the broker.

        Args:
            order: Normalized request. The implementation converts this
                into the broker's native payload.

        Returns:
            :class:`OrderResponse` with ``broker_order_id`` populated. The
            status will typically be ``PENDING`` or ``OPEN`` — actual
            fills arrive asynchronously via :meth:`get_order_status`.

        Raises:
            OrderRejectedError: Broker rejected the order (margin,
                symbol, price band, etc.).
            BrokerConnectionError: Network-level failure.
        """

    @abstractmethod
    async def modify_order(
        self, broker_order_id: str, order: OrderRequest
    ) -> OrderResponse:
        """Modify an existing pending order (price and/or quantity).

        Raises:
            OrderNotFoundError: ``broker_order_id`` does not exist.
            OrderRejectedError: Modification rejected (already filled,
                invalid price, etc.).
        """

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel a pending order.

        Returns:
            ``True`` if cancellation was accepted by the broker.

        Raises:
            OrderNotFoundError: ``broker_order_id`` does not exist.
        """

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """Fetch the latest normalized status for a single order."""

    # ══════════════════════════════════════════════════════════════════
    # Portfolio
    # ══════════════════════════════════════════════════════════════════

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Return all open positions (intraday + overnight)."""

    @abstractmethod
    async def get_holdings(self) -> list[Holding]:
        """Return delivery holdings (CNC / T+1 settled)."""

    @abstractmethod
    async def get_funds(self) -> Decimal:
        """Return available cash / margin in INR.

        Rupee amounts use :class:`~decimal.Decimal` — never ``float``.
        """

    # ══════════════════════════════════════════════════════════════════
    # Market data
    # ══════════════════════════════════════════════════════════════════

    @abstractmethod
    async def get_quote(self, symbol: str, exchange: Exchange) -> Quote:
        """Fetch a lightweight quote (LTP + best bid/ask) for a symbol."""

    # ══════════════════════════════════════════════════════════════════
    # Kill switch
    # ══════════════════════════════════════════════════════════════════

    @abstractmethod
    async def square_off_all(self) -> list[OrderResponse]:
        """Close every open position via market orders.

        Called by the kill-switch service when a user breaches their
        daily loss limit. Implementations must attempt each position
        independently — one failure must not prevent others from closing.

        Returns:
            The list of responses from every close attempt (successes
            AND failures), so the caller can persist a complete audit
            trail.
        """

    @abstractmethod
    async def cancel_all_pending(self) -> int:
        """Cancel every pending order for this user.

        Returns:
            The number of pending orders that were successfully cancelled.
        """

    # ══════════════════════════════════════════════════════════════════
    # Symbol mapping
    # ══════════════════════════════════════════════════════════════════

    @abstractmethod
    def normalize_symbol(self, tradingview_symbol: str, exchange: Exchange) -> str:
        """Convert a TradingView symbol to this broker's native format.

        TradingView alerts mein symbol format generic hota hai (e.g.
        ``NIFTY25JANFUT``) — har broker apna format chahta hai
        (e.g. Fyers ``NSE:NIFTY25JANFUT``, Zerodha ``NFO:NIFTY25JANFUT``).

        This method is intentionally synchronous — it is a pure lookup
        or string transformation, no network I/O.
        """


__all__ = ["BrokerInterface"]
