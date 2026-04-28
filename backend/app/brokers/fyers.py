"""Fyers broker integration.

Wraps the official ``fyers-apiv3`` SDK behind :class:`BrokerInterface`.
The SDK is synchronous, so every call goes through :func:`asyncio.to_thread`
to keep the FastAPI event loop responsive.

Performance notes:
    * The SDK's HTTP layer pools connections internally; we keep our own
      :class:`httpx.AsyncClient` with HTTP/2 + keep-alive for any
      direct calls we add later (websockets are out of scope for Step 2).
    * On :meth:`login` we pre-warm the connection by calling
      ``get_profile`` so the first user-facing trade pays no TLS-handshake
      cost.
    * ``@track_latency`` decorates every async public method so the
      observability layer sees per-broker latency from day one.

Resilience:
    * Transient failures (network, rate-limit, expired session) retry up
      to three times via :mod:`tenacity` with exponential backoff
      (100 ms → 200 ms → 400 ms). Permanent errors (validation, auth,
      rejection) bubble up immediately.
    * Fyers error codes map into the typed :mod:`app.core.exceptions`
      hierarchy through :data:`_FYERS_ERROR_MAP`.

The TOTP-driven fully-automatic login lands in Step 2.5 — for now,
:meth:`generate_auth_url` + :meth:`exchange_auth_code` cover the OAuth
handshake.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar, cast

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.brokers.base import BrokerInterface
from app.core.exceptions import (
    BrokerAuthError,
    BrokerConnectionError,
    BrokerError,
    BrokerInsufficientFundsError,
    BrokerInvalidSymbolError,
    BrokerOrderError,
    BrokerOrderRejectedError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
)
from app.core.logging import get_logger
from app.core.performance import track_latency
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    Exchange,
    Holding,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    ProductType,
    Quote,
)

try:  # SDK is heavy (aiohttp, boto3 deps); allow the module to import without it.
    from fyers_apiv3 import fyersModel as _fyers_module  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover — covered via monkeypatched factory in tests
    _fyers_module = None  # type: ignore[assignment]


_logger = get_logger("brokers.fyers", broker_name="fyers")

#: Fyers REST host — used for httpx pre-warm and direct calls (no SDK needed).
_FYERS_API_HOST = "https://api-t1.fyers.in"

#: HTTP connection pool size — matches the upper end of typical fan-out
#: (concurrent quote fetches for a portfolio sweep).
_HTTP_POOL_SIZE = 20

#: Retry budget for transient errors. 100 → 200 → 400 ms = ~700 ms worst case
#: before surfacing the error to the caller — well below TradingView's 10 s
#: webhook timeout.
_RETRY_ATTEMPTS = 3

# ─── Enum maps (BrokerInterface vocab → Fyers wire vocab) ──────────────

_TYPE_TO_FYERS: dict[OrderType, int] = {
    OrderType.LIMIT: 1,
    OrderType.MARKET: 2,
    OrderType.SL_M: 3,
    OrderType.SL: 4,
}

_PRODUCT_TO_FYERS: dict[ProductType, str] = {
    ProductType.INTRADAY: "INTRADAY",
    ProductType.DELIVERY: "CNC",
    ProductType.MARGIN: "MARGIN",
    ProductType.BO: "BO",
    ProductType.CO: "CO",
}

_SIDE_TO_FYERS: dict[OrderSide, int] = {
    OrderSide.BUY: 1,
    OrderSide.SELL: -1,
}

#: Fyers v3 numeric order status → normalized vocab.
_STATUS_FROM_FYERS: dict[int, OrderStatus] = {
    1: OrderStatus.CANCELLED,
    2: OrderStatus.COMPLETE,
    4: OrderStatus.PENDING,    # Transit / In-progress
    5: OrderStatus.REJECTED,
    6: OrderStatus.OPEN,
    7: OrderStatus.CANCELLED,  # Expired — treated as cancelled for our flow
}

#: Symbol-suffix per exchange for cash equities. Derivatives do not use one.
_EQUITY_SUFFIX: dict[Exchange, str] = {
    Exchange.NSE: "-EQ",
    Exchange.BSE: "-A",
}

#: Exchange prefix used by Fyers. F&O segments share their underlying's prefix.
_EXCHANGE_PREFIX: dict[Exchange, str] = {
    Exchange.NSE: "NSE",
    Exchange.NFO: "NSE",
    Exchange.BSE: "BSE",
    Exchange.BFO: "BSE",
    Exchange.MCX: "MCX",
    Exchange.CDS: "CDS",
}

#: Fyers numeric error code → exception class. The default fallback in
#: :func:`_raise_for_response` is :class:`BrokerOrderError`.
_FYERS_ERROR_MAP: dict[int, type[BrokerError]] = {
    -16: BrokerSessionExpiredError,
    -17: BrokerAuthError,
    -50: BrokerInvalidSymbolError,
    -99: BrokerInsufficientFundsError,
    -159: BrokerInvalidSymbolError,
    -300: BrokerInsufficientFundsError,
    -310: BrokerRateLimitError,
    -429: BrokerRateLimitError,
}

#: Errors that the retry layer should attempt to recover from.
_TRANSIENT: tuple[type[BaseException], ...] = (
    BrokerConnectionError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
)


def _money(value: Any) -> Decimal:
    """Convert a Fyers numeric (often ``float``) to :class:`Decimal` safely.

    Goes via ``str`` so we don't inherit the binary-float rounding that
    would otherwise creep into rupee maths.
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _raise_for_response(payload: Any, op: str, broker: str) -> dict[str, Any]:
    """Translate a Fyers response dict into a typed exception or return data.

    Fyers responses always carry ``s`` ("ok"/"error") plus a ``code`` and
    ``message``. This helper centralises the mapping so callers stay
    one-liners.
    """
    if not isinstance(payload, dict):
        raise BrokerOrderError(
            f"Fyers {op} returned non-dict payload",
            broker,
            metadata={"payload": payload},
        )

    if payload.get("s") == "ok":
        return payload

    code = payload.get("code")
    message = str(payload.get("message", "Fyers call failed"))
    metadata = {"operation": op, "code": code, "raw": payload}

    if isinstance(code, int) and code in _FYERS_ERROR_MAP:
        exc_cls = _FYERS_ERROR_MAP[code]
        if exc_cls is BrokerRateLimitError:
            retry_after = payload.get("retry_after")
            raise BrokerRateLimitError(
                message,
                broker,
                retry_after=float(retry_after) if retry_after is not None else None,
                metadata=metadata,
            )
        return _raise_typed(exc_cls, message, broker, metadata)

    # Unknown code — treat order-flow ops as rejection so audit logs are clean.
    if op in {"place_order", "modify_order", "cancel_order"}:
        raise BrokerOrderRejectedError(
            message,
            broker,
            reason=message,
            metadata=metadata,
        )
    raise BrokerOrderError(message, broker, metadata=metadata)


def _raise_typed(
    exc_cls: type[BrokerError], message: str, broker: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    """Helper that always raises — return type kept for control-flow ergonomics."""
    raise exc_cls(message, broker, metadata=metadata)


class FyersBroker(BrokerInterface):
    """:class:`BrokerInterface` implementation backed by ``fyers-apiv3``."""

    broker_name: ClassVar[BrokerName] = BrokerName.FYERS

    def __init__(self, credentials: BrokerCredentials) -> None:
        self._credentials = credentials
        self._app_id: str = credentials.api_key
        self._app_secret: str = credentials.api_secret
        self._redirect_uri: str = str(credentials.extra.get("redirect_uri", ""))
        self._access_token: str | None = credentials.access_token
        self._refresh_token: str | None = credentials.refresh_token
        self._token_expires_at: datetime | None = credentials.token_expires_at
        self._client: Any | None = None
        self._http: httpx.AsyncClient | None = None
        self._log = _logger.bind(user_id=credentials.user_id)

    # ══════════════════════════════════════════════════════════════════
    # OAuth helpers (public — called by the auth router, not BrokerInterface)
    # ══════════════════════════════════════════════════════════════════

    def generate_auth_url(self, state: str | None = None) -> str:
        """Return the Fyers OAuth URL the user must visit.

        Synchronous — ``SessionModel.generate_authcode`` is a pure URL
        construction, no network I/O.

        ``state`` is round-tripped via the OAuth ``state`` query param for
        CSRF protection. Passing it through the SessionModel constructor
        lets the SDK include it in the generated URL — no manual append.
        """
        session = self._build_session(state=state)
        return cast(str, session.generate_authcode())

    @track_latency("fyers.exchange_auth_code")
    async def exchange_auth_code(self, auth_code: str) -> dict[str, Any]:
        """Trade an OAuth ``auth_code`` for an access + refresh token pair.

        Stores the resulting tokens on ``self`` so subsequent calls can
        proceed without another login round-trip; persisting them back
        to the credential store is the caller's responsibility.
        """
        session = self._build_session()
        session.set_token(auth_code)
        result = await asyncio.to_thread(session.generate_token)

        if not isinstance(result, dict) or not result.get("access_token"):
            self._log.warning("fyers.token_exchange_failed", response=result)
            raise BrokerAuthError(
                "Fyers token exchange failed",
                self.broker_name.value,
                metadata={"response": result},
            )

        self._access_token = result["access_token"]
        self._refresh_token = result.get("refresh_token")
        # Fyers session tokens expire at the next market open (~06:00 IST).
        # 12-hour conservative TTL keeps us refreshing before they bite.
        self._token_expires_at = datetime.now(UTC) + timedelta(hours=12)
        self._log.info("fyers.token_exchanged")
        return cast(dict[str, Any], result)

    # ══════════════════════════════════════════════════════════════════
    # Authentication (BrokerInterface)
    # ══════════════════════════════════════════════════════════════════

    @track_latency("fyers.login")
    async def login(self) -> bool:
        """Activate the SDK client and pre-warm the HTTP connection.

        Step 2 expects the access token to already be present (from the
        OAuth flow). The TOTP-driven auto-login wrapper is Step 2.5.
        """
        if not self._access_token:
            raise BrokerAuthError(
                "No Fyers access token; complete the OAuth flow first.",
                self.broker_name.value,
            )

        self._client = self._build_model()
        await self._ensure_http_client()

        try:
            profile = await asyncio.to_thread(self._client.get_profile)
        except Exception as exc:  # noqa: BLE001 — re-raised as typed below
            self._log.warning("fyers.login_network_error", error=str(exc))
            raise BrokerConnectionError(
                "Fyers profile fetch failed during login pre-warm",
                self.broker_name.value,
                original_error=exc,
            ) from exc

        _raise_for_response(profile, "get_profile", self.broker_name.value)
        self._log.info("fyers.login_ok")
        return True

    async def is_session_valid(self) -> bool:
        """Cheap check — no network call. True iff token present and unexpired."""
        if not self._access_token:
            return False
        if self._token_expires_at is None:
            # Token loaded from DB without an expiry — assume valid; let the
            # session-expired retry path handle it if the broker disagrees.
            return True
        # Compare in UTC; tolerate naive datetimes from older DB rows.
        now = datetime.now(UTC)
        expires = self._token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return expires > now

    # ══════════════════════════════════════════════════════════════════
    # Order management
    # ══════════════════════════════════════════════════════════════════

    @track_latency("fyers.place_order")
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        payload = self._build_order_payload(order)
        result = await self._call("place_order", lambda c: c.place_order(payload))
        order_id = result.get("id") or result.get("orderId") or ""
        if not order_id:
            raise BrokerOrderError(
                "Fyers place_order succeeded but returned no order id",
                self.broker_name.value,
                metadata={"raw": result},
            )
        return OrderResponse(
            broker_order_id=str(order_id),
            status=OrderStatus.PENDING,
            message=str(result.get("message", "")),
            raw_response=result,
        )

    @track_latency("fyers.modify_order")
    async def modify_order(
        self, broker_order_id: str, order: OrderRequest
    ) -> OrderResponse:
        payload: dict[str, Any] = {
            "id": broker_order_id,
            "qty": order.quantity,
            "type": _TYPE_TO_FYERS[order.order_type],
        }
        if order.price is not None:
            payload["limitPrice"] = float(order.price)
        if order.trigger_price is not None:
            payload["stopPrice"] = float(order.trigger_price)

        result = await self._call("modify_order", lambda c: c.modify_order(payload))
        return OrderResponse(
            broker_order_id=str(result.get("id", broker_order_id)),
            status=OrderStatus.OPEN,
            message=str(result.get("message", "")),
            raw_response=result,
        )

    @track_latency("fyers.cancel_order")
    async def cancel_order(self, broker_order_id: str) -> bool:
        result = await self._call(
            "cancel_order", lambda c: c.cancel_order({"id": broker_order_id})
        )
        return result.get("s") == "ok" or "id" in result

    @track_latency("fyers.get_order_status")
    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        result = await self._call("orderbook", lambda c: c.orderbook())
        for row in result.get("orderBook", []) or []:
            if str(row.get("id")) == broker_order_id:
                return _STATUS_FROM_FYERS.get(int(row.get("status", 0)), OrderStatus.PENDING)
        raise BrokerOrderError(
            f"Order {broker_order_id} not found in Fyers orderbook",
            self.broker_name.value,
            metadata={"broker_order_id": broker_order_id},
        )

    # ══════════════════════════════════════════════════════════════════
    # Portfolio
    # ══════════════════════════════════════════════════════════════════

    @track_latency("fyers.get_positions")
    async def get_positions(self) -> list[Position]:
        result = await self._call("positions", lambda c: c.positions())
        positions: list[Position] = []
        for row in result.get("netPositions", []) or []:
            qty = int(row.get("netQty", 0))
            if qty == 0:
                continue  # Closed-out intraday — skip noise.
            positions.append(
                Position(
                    symbol=str(row.get("symbol", "")),
                    exchange=self._exchange_from_symbol(str(row.get("symbol", ""))),
                    quantity=qty,
                    avg_price=_money(row.get("netAvg")),
                    ltp=_money(row.get("ltp")),
                    unrealized_pnl=_money(row.get("unrealized_profit", row.get("pl", 0))),
                    product_type=self._product_from_fyers(str(row.get("productType", ""))),
                )
            )
        return positions

    @track_latency("fyers.get_holdings")
    async def get_holdings(self) -> list[Holding]:
        result = await self._call("holdings", lambda c: c.holdings())
        holdings: list[Holding] = []
        for row in result.get("holdings", []) or []:
            qty = int(row.get("quantity", 0))
            if qty <= 0:
                continue
            ltp = _money(row.get("ltp"))
            avg = _money(row.get("costPrice"))
            current_value = _money(row.get("marketVal", ltp * qty))
            holdings.append(
                Holding(
                    symbol=str(row.get("symbol", "")),
                    exchange=self._exchange_from_symbol(str(row.get("symbol", ""))),
                    quantity=qty,
                    avg_price=avg,
                    ltp=ltp,
                    current_value=current_value,
                    pnl=_money(row.get("pl", current_value - avg * qty)),
                )
            )
        return holdings

    @track_latency("fyers.get_funds")
    async def get_funds(self) -> Decimal:
        result = await self._call("funds", lambda c: c.funds())
        # Fyers returns an array of fund-limit rows; total available is title 10.
        for row in result.get("fund_limit", []) or []:
            if row.get("title") == "Available Balance" or row.get("id") == 10:
                return _money(row.get("equityAmount", row.get("commodityAmount", 0)))
        # Fallback: sum equity column.
        total = sum(
            _money(row.get("equityAmount", 0))
            for row in result.get("fund_limit", []) or []
        )
        return cast(Decimal, total) if isinstance(total, Decimal) else Decimal("0")

    # ══════════════════════════════════════════════════════════════════
    # Market data
    # ══════════════════════════════════════════════════════════════════

    @track_latency("fyers.get_quote")
    async def get_quote(self, symbol: str, exchange: Exchange) -> Quote:
        fyers_symbol = self.normalize_symbol(symbol, exchange)
        result = await self._call(
            "quotes", lambda c: c.quotes({"symbols": fyers_symbol})
        )
        rows = result.get("d", []) or []
        if not rows:
            raise BrokerInvalidSymbolError(
                f"No quote returned for {fyers_symbol}",
                self.broker_name.value,
                metadata={"symbol": fyers_symbol},
            )
        first = rows[0]
        if first.get("s") != "ok":
            raise BrokerInvalidSymbolError(
                str(first.get("message", "Fyers quote error")),
                self.broker_name.value,
                metadata={"symbol": fyers_symbol, "raw": first},
            )
        data = first.get("v", {})
        ts_raw = data.get("tt") or data.get("timestamp")
        ts = datetime.fromtimestamp(int(ts_raw), tz=UTC) if ts_raw else datetime.now(UTC)
        return Quote(
            symbol=symbol,
            exchange=exchange,
            ltp=_money(data.get("lp")),
            bid=_money(data.get("bid")),
            ask=_money(data.get("ask")),
            volume=int(data.get("volume", 0) or 0),
            timestamp=ts,
        )

    # ══════════════════════════════════════════════════════════════════
    # Kill switch
    # ══════════════════════════════════════════════════════════════════

    @track_latency("fyers.square_off_all")
    async def square_off_all(self) -> list[OrderResponse]:
        positions = await self.get_positions()
        responses: list[OrderResponse] = []
        for pos in positions:
            close_side = OrderSide.SELL if pos.quantity > 0 else OrderSide.BUY
            close_qty = abs(pos.quantity)
            close_order = OrderRequest(
                symbol=pos.symbol,
                exchange=pos.exchange,
                side=close_side,
                quantity=close_qty,
                order_type=OrderType.MARKET,
                product_type=pos.product_type,
                tag="kill-switch",
            )
            try:
                responses.append(await self.place_order(close_order))
            except BrokerError as exc:
                # One failure must not prevent other positions from closing.
                self._log.error(
                    "fyers.square_off_failed",
                    symbol=pos.symbol,
                    error=str(exc),
                )
                responses.append(
                    OrderResponse(
                        broker_order_id="",
                        status=OrderStatus.REJECTED,
                        message=str(exc),
                        raw_response={"error": str(exc), "symbol": pos.symbol},
                    )
                )
        return responses

    @track_latency("fyers.cancel_all_pending")
    async def cancel_all_pending(self) -> int:
        result = await self._call("orderbook", lambda c: c.orderbook())
        cancelled = 0
        for row in result.get("orderBook", []) or []:
            status = int(row.get("status", 0))
            if _STATUS_FROM_FYERS.get(status) not in (OrderStatus.OPEN, OrderStatus.PENDING):
                continue
            try:
                if await self.cancel_order(str(row.get("id"))):
                    cancelled += 1
            except BrokerError as exc:
                self._log.error(
                    "fyers.cancel_pending_failed", id=row.get("id"), error=str(exc)
                )
        return cancelled

    # ══════════════════════════════════════════════════════════════════
    # Symbol mapping
    # ══════════════════════════════════════════════════════════════════

    def normalize_symbol(self, tradingview_symbol: str, exchange: Exchange) -> str:
        """Map a TradingView symbol to Fyers' ``EXCHANGE:SYMBOL[-SUFFIX]`` form.

        Already-normalised symbols (containing ``:``) pass through, so
        callers that already speak Fyers do not double-prefix.
        """
        sym = tradingview_symbol.strip().upper()
        if not sym:
            raise BrokerInvalidSymbolError(
                "Empty symbol", self.broker_name.value, metadata={"input": tradingview_symbol}
            )
        if ":" in sym:
            return sym

        prefix = _EXCHANGE_PREFIX.get(exchange)
        if prefix is None:
            raise BrokerInvalidSymbolError(
                f"Unsupported exchange for Fyers: {exchange.value}",
                self.broker_name.value,
                metadata={"exchange": exchange.value},
            )

        # Exchange enum already disambiguates cash vs derivative segments;
        # NSE/BSE are cash-only and always need an instrument suffix, while
        # NFO/BFO/MCX/CDS carry the expiry/strike inside the symbol itself.
        if exchange in _EQUITY_SUFFIX:
            return f"{prefix}:{sym}{_EQUITY_SUFFIX[exchange]}"

        return f"{prefix}:{sym}"

    # ══════════════════════════════════════════════════════════════════
    # Internals
    # ══════════════════════════════════════════════════════════════════

    def _build_session(self, state: str | None = None) -> Any:
        if _fyers_module is None:
            raise BrokerConnectionError(
                "fyers-apiv3 SDK not installed", self.broker_name.value
            )
        kwargs: dict[str, Any] = {
            "client_id": self._app_id,
            "secret_key": self._app_secret,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "grant_type": "authorization_code",
        }
        if state is not None:
            kwargs["state"] = state
        return _fyers_module.SessionModel(**kwargs)

    def _build_model(self) -> Any:
        if _fyers_module is None:
            raise BrokerConnectionError(
                "fyers-apiv3 SDK not installed", self.broker_name.value
            )
        return _fyers_module.FyersModel(
            client_id=self._app_id,
            is_async=False,
            token=self._access_token,
        )

    async def _ensure_http_client(self) -> httpx.AsyncClient:
        """Create the keep-alive httpx client lazily (and only once)."""
        if self._http is None:
            limits = httpx.Limits(
                max_connections=_HTTP_POOL_SIZE,
                max_keepalive_connections=_HTTP_POOL_SIZE,
                keepalive_expiry=60.0,
            )
            self._http = httpx.AsyncClient(
                base_url=_FYERS_API_HOST,
                timeout=httpx.Timeout(10.0, connect=3.0),
                limits=limits,
                http2=False,  # Fyers REST is HTTP/1.1; HTTP/2 only buys complexity here.
            )
        return self._http

    async def aclose(self) -> None:
        """Release the httpx pool. Call from a shutdown hook."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _call(
        self, op: str, fn: Any
    ) -> dict[str, Any]:
        """Invoke ``fn(client)`` with retries, latency, and typed error mapping.

        ``fn`` is a closure so callers can compose any SDK call without
        passing the client explicitly. The retry layer rebuilds the
        session on :class:`BrokerSessionExpiredError`.
        """
        if self._client is None:
            await self.login()

        async def attempt() -> dict[str, Any]:
            client = self._client
            assert client is not None  # login() guarantees this
            try:
                raw = await asyncio.to_thread(fn, client)
            except (httpx.HTTPError, ConnectionError, TimeoutError, OSError) as exc:
                raise BrokerConnectionError(
                    f"Fyers {op} network failure",
                    self.broker_name.value,
                    original_error=exc,
                    metadata={"operation": op},
                ) from exc
            except BrokerError:
                raise
            except Exception as exc:  # noqa: BLE001 — wrap unknowns as connection errors
                raise BrokerConnectionError(
                    f"Fyers {op} unexpected SDK error",
                    self.broker_name.value,
                    original_error=exc,
                    metadata={"operation": op},
                ) from exc
            return _raise_for_response(raw, op, self.broker_name.value)

        try:
            async for retry in AsyncRetrying(
                stop=stop_after_attempt(_RETRY_ATTEMPTS),
                wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
                retry=retry_if_exception_type(_TRANSIENT),
                reraise=True,
            ):
                with retry:
                    try:
                        return await attempt()
                    except BrokerSessionExpiredError:
                        # Force re-login on next attempt — fresh token, same call.
                        self._log.info("fyers.session_expired_retry", operation=op)
                        self._client = None
                        await self.login()
                        raise
        except RetryError as exc:  # pragma: no cover — reraise=True bubbles the original
            raise BrokerConnectionError(
                f"Fyers {op} exhausted retries",
                self.broker_name.value,
                original_error=exc,
            ) from exc
        # AsyncRetrying with reraise=True always returns or raises within the loop.
        raise AssertionError("unreachable: AsyncRetrying exited without result")

    @staticmethod
    def _exchange_from_symbol(fyers_symbol: str) -> Exchange:
        """Best-effort exchange inference from a Fyers-prefixed symbol.

        Falls back to NSE if the prefix is missing — positions/holdings
        endpoints occasionally return raw symbols without the prefix on
        paper accounts.
        """
        prefix, _, _ = fyers_symbol.partition(":")
        if prefix == "BSE":
            return Exchange.BSE
        if prefix == "MCX":
            return Exchange.MCX
        if prefix == "CDS":
            return Exchange.CDS
        return Exchange.NSE

    @staticmethod
    def _product_from_fyers(value: str) -> ProductType:
        match value.upper():
            case "INTRADAY":
                return ProductType.INTRADAY
            case "CNC":
                return ProductType.DELIVERY
            case "MARGIN":
                return ProductType.MARGIN
            case "BO":
                return ProductType.BO
            case "CO":
                return ProductType.CO
            case _:
                return ProductType.INTRADAY

    def _build_order_payload(self, order: OrderRequest) -> dict[str, Any]:
        """Translate :class:`OrderRequest` into Fyers' wire format."""
        return {
            "symbol": self.normalize_symbol(order.symbol, order.exchange),
            "qty": order.quantity,
            "type": _TYPE_TO_FYERS[order.order_type],
            "side": _SIDE_TO_FYERS[order.side],
            "productType": _PRODUCT_TO_FYERS[order.product_type],
            "limitPrice": float(order.price) if order.price is not None else 0.0,
            "stopPrice": (
                float(order.trigger_price) if order.trigger_price is not None else 0.0
            ),
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False,
            "stopLoss": 0,
            "takeProfit": 0,
            "orderTag": order.tag or "",
        }


__all__ = ["FyersBroker"]
