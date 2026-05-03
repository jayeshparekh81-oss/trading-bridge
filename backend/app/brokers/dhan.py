"""Dhan (DhanHQ v2) integration.

Dhan publishes a plain REST API — no SDK required — so we drive it
through :class:`httpx.AsyncClient` directly. That gives us a shared
connection pool, HTTP/1.1 keep-alive, and native async with no
``asyncio.to_thread`` wrapping (unlike Fyers whose SDK is sync).

Layout mirrors :mod:`app.brokers.fyers`:
    * Enum maps at the top (OrderType, ProductType, Exchange, Side →
      Dhan wire vocab and back).
    * One HTTP helper ``_call`` with retry + typed error mapping.
    * One public method per :class:`BrokerInterface` abstract.
    * Symbol normalisation via Dhan's ``securityId`` scrip-master.

Symbol mapping
--------------
Dhan identifies every instrument by a **numeric ``securityId``** rather
than a string symbol. The master list is published at
``https://images.dhan.co/api-data/api-scrip-master.csv`` (hundreds of
thousands of rows). We lazily download it on first use, parse into an
in-memory ``(symbol, exchange_segment) → security_id`` dict, and refresh
once a day. For now we cache per-process; a later step may push this
into Redis so every worker shares one download.
"""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.brokers.base import BrokerInterface
from app.core import redis_client
from app.core.config import get_settings
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


_logger = get_logger("brokers.dhan", broker_name="dhan")


# ═══════════════════════════════════════════════════════════════════════
# Constants + enum maps
# ═══════════════════════════════════════════════════════════════════════


#: HTTP pool size — generous; Dhan allows 100 req/s per account.
_HTTP_POOL_SIZE = 20

#: Retry budget. 100 → 200 → 400 ms worst-case ≈ 700 ms total.
_RETRY_ATTEMPTS = 3

#: TTL for the session-valid cache in Redis (seconds).
_SESSION_VALID_TTL = 3600

#: Transient error classes the retry layer is allowed to replay.
_TRANSIENT: tuple[type[BaseException], ...] = (
    BrokerConnectionError,
    BrokerRateLimitError,
)


_SIDE_TO_DHAN: dict[OrderSide, str] = {
    OrderSide.BUY: "BUY",
    OrderSide.SELL: "SELL",
}

_TYPE_TO_DHAN: dict[OrderType, str] = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.SL: "STOP_LOSS",
    OrderType.SL_M: "STOP_LOSS_MARKET",
}

_TYPE_FROM_DHAN: dict[str, OrderType] = {v: k for k, v in _TYPE_TO_DHAN.items()}

_PRODUCT_TO_DHAN: dict[ProductType, str] = {
    ProductType.INTRADAY: "INTRADAY",
    ProductType.DELIVERY: "CNC",
    ProductType.MARGIN: "MARGIN",
    ProductType.BO: "BO",
    ProductType.CO: "CO",
}

_PRODUCT_FROM_DHAN: dict[str, ProductType] = {
    "INTRADAY": ProductType.INTRADAY,
    "CNC": ProductType.DELIVERY,
    "MARGIN": ProductType.MARGIN,
    "BO": ProductType.BO,
    "CO": ProductType.CO,
}

_EXCHANGE_TO_DHAN_SEGMENT: dict[Exchange, str] = {
    Exchange.NSE: "NSE_EQ",
    Exchange.BSE: "BSE_EQ",
    Exchange.NFO: "NSE_FNO",
    Exchange.BFO: "BSE_FNO",
    Exchange.MCX: "MCX_COMM",
    Exchange.CDS: "NSE_CURRENCY",
}

_DHAN_SEGMENT_TO_EXCHANGE: dict[str, Exchange] = {
    v: k for k, v in _EXCHANGE_TO_DHAN_SEGMENT.items()
}

#: Maps Dhan's CSV (SEM_EXM_EXCH_ID, SEM_SEGMENT) tuple to our canonical
#: exchange_segment string. SEM_EXM_EXCH_ID is the bare exchange code
#: (NSE/BSE/MCX); SEM_SEGMENT is the single-letter segment code
#: (E=equity, D=derivatives, I=index, C=currency, M=commodity). The two
#: columns must be combined — exchange alone is ambiguous (NSE rows can
#: be equity OR F&O), which is why earlier code that read SEM_EXM_EXCH_ID
#: as if it were the segment dropped every F&O lookup.
_SEGMENT_FOR: dict[tuple[str, str], str] = {
    ("NSE", "E"): "NSE_EQ",
    ("NSE", "D"): "NSE_FNO",  # FUTSTK + FUTIDX + OPTSTK + OPTIDX live here
    ("NSE", "I"): "IDX_I",
    ("NSE", "C"): "NSE_CURRENCY",
    ("BSE", "E"): "BSE_EQ",
    ("BSE", "D"): "BSE_FNO",
    ("BSE", "I"): "IDX_I",
    ("BSE", "C"): "BSE_CURRENCY",
    ("MCX", "M"): "MCX_COMM",
}

#: Dhan status string → our normalized enum.
_STATUS_FROM_DHAN: dict[str, OrderStatus] = {
    "PENDING": OrderStatus.PENDING,
    "TRANSIT": OrderStatus.PENDING,
    "OPEN": OrderStatus.OPEN,
    "TRADED": OrderStatus.COMPLETE,
    "EXECUTED": OrderStatus.COMPLETE,
    "COMPLETE": OrderStatus.COMPLETE,
    "CANCELLED": OrderStatus.CANCELLED,
    "EXPIRED": OrderStatus.CANCELLED,
    "REJECTED": OrderStatus.REJECTED,
    "PART_TRADED": OrderStatus.PARTIAL,
    "PARTIALLY_EXECUTED": OrderStatus.PARTIAL,
}

#: Dhan error codes we map to specific typed exceptions. Everything else
#: falls through to BrokerOrderError / BrokerConnectionError based on HTTP.
_DHAN_ERROR_MAP: dict[str, type[BrokerError]] = {
    "DH-901": BrokerAuthError,         # invalid access token
    "DH-902": BrokerSessionExpiredError,
    "DH-903": BrokerInsufficientFundsError,
    "DH-904": BrokerInvalidSymbolError,
    "DH-905": BrokerOrderRejectedError,
    "DH-906": BrokerRateLimitError,
}


def _money(value: Any) -> Decimal:
    """Safe float → Decimal, matching the Fyers helper."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


# ═══════════════════════════════════════════════════════════════════════
# Scrip master (symbol → securityId)
# ═══════════════════════════════════════════════════════════════════════


class _ScripMaster:
    """In-process cache of Dhan's scrip-master CSV.

    The CSV is large (~40 MB) but the parsed dict is small compared to
    the useful slice — we keep only ``(symbol, exchange_segment) →
    security_id`` entries plus a reverse lookup for positions/holdings.

    Access is guarded by an :class:`asyncio.Lock` so the first call in
    a worker doesn't trigger multiple concurrent downloads.
    """

    def __init__(self) -> None:
        self._by_symbol: dict[tuple[str, str], str] = {}
        self._by_id: dict[str, tuple[str, str]] = {}
        self._lot_sizes: dict[str, int] = {}
        self._loaded_at: datetime | None = None
        self._lock = asyncio.Lock()
        self._ttl = timedelta(hours=24)

    def is_loaded(self) -> bool:
        return (
            self._loaded_at is not None
            and datetime.now(UTC) - self._loaded_at < self._ttl
        )

    async def ensure_loaded(self, http: httpx.AsyncClient, url: str) -> None:
        """Download + parse the CSV exactly once per TTL window."""
        if self.is_loaded():
            return
        async with self._lock:
            if self.is_loaded():  # Double-check inside the lock.
                return
            try:
                response = await http.get(url, timeout=30.0)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise BrokerConnectionError(
                    "Dhan scrip master download failed",
                    BrokerName.DHAN.value,
                    original_error=exc,
                ) from exc
            self._parse(response.text)
            self._loaded_at = datetime.now(UTC)

    def load_from_text(self, text: str) -> None:
        """Test hook — parse a CSV payload without an HTTP round-trip."""
        self._parse(text)
        self._loaded_at = datetime.now(UTC)

    def _parse(self, text: str) -> None:
        """Ingest the CSV.

        The CSV schema varies slightly across Dhan versions; we look up
        the relevant columns case-insensitively to stay forward-
        compatible. Rows without both a security id and a trading symbol
        are skipped, as are INDEX instruments (not directly orderable).

        Segment resolution:
            * Preferred: ``(SEM_EXM_EXCH_ID, SEM_SEGMENT)`` via
              :data:`_SEGMENT_FOR` — combines exchange + segment letter
              into the canonical exchange_segment string.
            * Fallback: legacy single-column lookup via
              :func:`_canonical_segment` on the exchange code, used by
              older fixtures and CSV variants that don't carry
              ``SEM_SEGMENT``.
        """
        reader = csv.DictReader(io.StringIO(text))
        by_symbol: dict[tuple[str, str], str] = {}
        by_id: dict[str, tuple[str, str]] = {}
        lot_sizes: dict[str, int] = {}
        for row in reader:
            normalised = {k.strip().upper(): (v or "").strip() for k, v in row.items()}
            sec_id = normalised.get("SEM_SMST_SECURITY_ID") or normalised.get(
                "SECURITY_ID"
            )
            symbol = (
                normalised.get("SEM_TRADING_SYMBOL")
                or normalised.get("TRADING_SYMBOL")
                or normalised.get("SM_SYMBOL_NAME")
            )
            if not sec_id or not symbol:
                continue

            instrument = normalised.get("SEM_INSTRUMENT_NAME", "").upper()
            # Indices aren't orderable as F&O orders; the strategy executor
            # would resolve them and then have the order rejected by the
            # broker. Skip at parse time so lookups MISS cleanly.
            if instrument == "INDEX":
                continue

            exchange_code = (
                normalised.get("SEM_EXM_EXCH_ID")
                or normalised.get("EXCH_ID")
                or normalised.get("EXM_EXCH_ID")
                or ""
            ).upper()
            segment_code = normalised.get("SEM_SEGMENT", "").upper()

            segment = _SEGMENT_FOR.get((exchange_code, segment_code))
            if segment is None:
                # Legacy fallback — older fixtures and CSV variants that
                # only carry the exchange column.
                segment = _canonical_segment(exchange_code or "NSE_EQ")

            key = (symbol.upper(), segment)
            by_symbol[key] = sec_id
            by_id[sec_id] = key

            lot_str = normalised.get("SEM_LOT_UNITS", "")
            if lot_str:
                try:
                    # CSV stores lot units as float string (e.g. '375.0').
                    lot_sizes[sec_id] = int(float(lot_str))
                except ValueError:
                    pass

        self._by_symbol = by_symbol
        self._by_id = by_id
        self._lot_sizes = lot_sizes

    def lookup(self, symbol: str, segment: str) -> str | None:
        return self._by_symbol.get((symbol.upper(), segment))

    def reverse(self, security_id: str) -> tuple[str, str] | None:
        return self._by_id.get(security_id)

    def lot_size(self, security_id: str) -> int | None:
        """Return Dhan's lot units for a security_id, or None if unknown.

        Used by the strategy executor + position manager to convert
        between "lots" (the strategy-config unit) and "contracts" (the
        unit Dhan's order API expects).
        """
        return self._lot_sizes.get(security_id)


def _canonical_segment(raw: str) -> str:
    """Fold Dhan's historical segment codes into the v2 vocabulary."""
    raw = raw.strip().upper()
    aliases = {
        "NSE": "NSE_EQ",
        "BSE": "BSE_EQ",
        "NFO": "NSE_FNO",
        "BFO": "BSE_FNO",
        "MCX": "MCX_COMM",
        "CDS": "NSE_CURRENCY",
    }
    return aliases.get(raw, raw)


# Module-level cache — shared across every DhanBroker instance.
_SCRIP_MASTER = _ScripMaster()


# ═══════════════════════════════════════════════════════════════════════
# DhanBroker
# ═══════════════════════════════════════════════════════════════════════


class DhanBroker(BrokerInterface):
    """REST-backed implementation of :class:`BrokerInterface` for Dhan v2."""

    broker_name: ClassVar[BrokerName] = BrokerName.DHAN

    def __init__(self, credentials: BrokerCredentials) -> None:
        settings = get_settings()
        self._credentials = credentials
        self._client_id = credentials.client_id
        self._access_token = credentials.access_token or ""
        self._base_url = settings.dhan_api_base_url
        self._scrip_url = settings.dhan_scrip_master_url
        self._http: httpx.AsyncClient | None = None
        self._log = _logger.bind(user_id=credentials.user_id)

    # ══════════════════════════════════════════════════════════════════
    # Authentication
    # ══════════════════════════════════════════════════════════════════

    @track_latency("dhan.login")
    async def login(self) -> bool:
        """Validate the access token by hitting the profile/fundlimit endpoint.

        Dhan tokens are long-lived (daily) and user-pasted — there is no
        OAuth flow like Fyers. A successful ``/fundlimit`` call proves
        the token is active; we cache the positive result in Redis so
        subsequent :meth:`is_session_valid` hits don't pay the RTT.
        """
        if not self._access_token:
            raise BrokerAuthError(
                "No Dhan access token configured.",
                self.broker_name.value,
            )
        await self._call("login", "GET", "/fundlimit")
        await self._cache_session_valid(True)
        self._log.info("dhan.login_ok")
        return True

    async def is_session_valid(self) -> bool:
        """Check Redis first, fall back to a cheap API probe."""
        if not self._access_token:
            return False
        cached = await redis_client.cache_get(self._session_cache_key())
        if cached == "1":
            return True
        if cached == "0":
            return False
        # Unknown — probe once.
        try:
            await self._call("session_check", "GET", "/fundlimit")
        except BrokerAuthError:
            await self._cache_session_valid(False)
            return False
        except BrokerError:
            return False
        await self._cache_session_valid(True)
        return True

    def _session_cache_key(self) -> str:
        return f"dhan_session:{self._credentials.user_id}"

    async def _cache_session_valid(self, valid: bool) -> None:
        await redis_client.cache_set(
            self._session_cache_key(),
            "1" if valid else "0",
            ttl_seconds=_SESSION_VALID_TTL,
        )

    # ══════════════════════════════════════════════════════════════════
    # Order management
    # ══════════════════════════════════════════════════════════════════

    @track_latency("dhan.place_order")
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        payload = await self._build_order_payload(order)
        result = await self._call("place_order", "POST", "/orders", json=payload)
        order_id = (
            result.get("orderId")
            or result.get("order_id")
            or result.get("dhanOrderId")
        )
        if not order_id:
            raise BrokerOrderError(
                "Dhan place_order returned no order id",
                self.broker_name.value,
                metadata={"raw": result},
            )
        status = _STATUS_FROM_DHAN.get(
            str(result.get("orderStatus", "PENDING")).upper(),
            OrderStatus.PENDING,
        )
        return OrderResponse(
            broker_order_id=str(order_id),
            status=status,
            message=str(result.get("message", "")),
            raw_response=result,
        )

    @track_latency("dhan.modify_order")
    async def modify_order(
        self, broker_order_id: str, order: OrderRequest
    ) -> OrderResponse:
        payload: dict[str, Any] = {
            "dhanClientId": self._client_id,
            "orderId": broker_order_id,
            "orderType": _TYPE_TO_DHAN[order.order_type],
            "quantity": order.quantity,
        }
        if order.price is not None:
            payload["price"] = float(order.price)
        if order.trigger_price is not None:
            payload["triggerPrice"] = float(order.trigger_price)
        result = await self._call(
            "modify_order", "PUT", f"/orders/{broker_order_id}", json=payload
        )
        return OrderResponse(
            broker_order_id=str(result.get("orderId", broker_order_id)),
            status=_STATUS_FROM_DHAN.get(
                str(result.get("orderStatus", "PENDING")).upper(),
                OrderStatus.OPEN,
            ),
            message=str(result.get("message", "")),
            raw_response=result,
        )

    @track_latency("dhan.cancel_order")
    async def cancel_order(self, broker_order_id: str) -> bool:
        result = await self._call(
            "cancel_order", "DELETE", f"/orders/{broker_order_id}"
        )
        status = str(result.get("orderStatus", "")).upper()
        return status in ("CANCELLED", "CANCELED") or bool(result.get("orderId"))

    @track_latency("dhan.get_order_status")
    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        result = await self._call(
            "order_status", "GET", f"/orders/{broker_order_id}"
        )
        return _STATUS_FROM_DHAN.get(
            str(result.get("orderStatus", "PENDING")).upper(),
            OrderStatus.PENDING,
        )

    # ══════════════════════════════════════════════════════════════════
    # Portfolio
    # ══════════════════════════════════════════════════════════════════

    @track_latency("dhan.get_positions")
    async def get_positions(self) -> list[Position]:
        rows = await self._call_list("positions", "GET", "/positions")
        out: list[Position] = []
        for row in rows:
            qty = int(row.get("netQty", row.get("netQuantity", 0)) or 0)
            if qty == 0:
                continue
            segment = _canonical_segment(
                str(row.get("exchangeSegment", "NSE_EQ"))
            )
            out.append(
                Position(
                    symbol=str(
                        row.get("tradingSymbol")
                        or row.get("securityId")
                        or ""
                    ),
                    exchange=_DHAN_SEGMENT_TO_EXCHANGE.get(segment, Exchange.NSE),
                    quantity=qty,
                    avg_price=_money(row.get("buyAvg") or row.get("costPrice")),
                    ltp=_money(row.get("ltp") or row.get("lastTradedPrice")),
                    unrealized_pnl=_money(
                        row.get("unrealizedProfit") or row.get("unrealizedPnL") or 0
                    ),
                    product_type=_PRODUCT_FROM_DHAN.get(
                        str(row.get("productType", "INTRADAY")).upper(),
                        ProductType.INTRADAY,
                    ),
                )
            )
        return out

    @track_latency("dhan.get_holdings")
    async def get_holdings(self) -> list[Holding]:
        rows = await self._call_list("holdings", "GET", "/holdings")
        out: list[Holding] = []
        for row in rows:
            qty = int(row.get("totalQty", row.get("quantity", 0)) or 0)
            if qty <= 0:
                continue
            segment = _canonical_segment(
                str(row.get("exchange", row.get("exchangeSegment", "NSE_EQ")))
            )
            avg = _money(row.get("avgCostPrice", row.get("costPrice")))
            ltp = _money(row.get("lastTradedPrice", row.get("ltp")))
            current_value = ltp * qty
            out.append(
                Holding(
                    symbol=str(row.get("tradingSymbol", "")),
                    exchange=_DHAN_SEGMENT_TO_EXCHANGE.get(segment, Exchange.NSE),
                    quantity=qty,
                    avg_price=avg,
                    ltp=ltp,
                    current_value=current_value,
                    pnl=current_value - avg * qty,
                )
            )
        return out

    @track_latency("dhan.get_funds")
    async def get_funds(self) -> Decimal:
        result = await self._call("funds", "GET", "/fundlimit")
        return _money(
            result.get("availableBalance")
            or result.get("availabelBalance")  # Dhan typo seen in sandbox
            or result.get("withdrawableBalance")
            or 0
        )

    # ══════════════════════════════════════════════════════════════════
    # Market data
    # ══════════════════════════════════════════════════════════════════

    @track_latency("dhan.get_quote")
    async def get_quote(self, symbol: str, exchange: Exchange) -> Quote:
        segment = _EXCHANGE_TO_DHAN_SEGMENT.get(exchange)
        if segment is None:
            raise BrokerInvalidSymbolError(
                f"Unsupported exchange for Dhan: {exchange.value}",
                self.broker_name.value,
                metadata={"exchange": exchange.value},
            )
        security_id = await self.get_security_id(symbol, exchange)
        payload = {segment: [int(security_id)]}
        result = await self._call(
            "quotes", "POST", "/marketfeed/ltp", json=payload
        )
        # Dhan returns ``{"data": {"NSE_EQ": {"11536": {"last_price": ...}}}}``.
        data = result.get("data", {}) if isinstance(result, dict) else {}
        seg_block = data.get(segment, {}) or {}
        quote_raw = seg_block.get(str(security_id)) or seg_block.get(security_id)
        if not quote_raw:
            raise BrokerInvalidSymbolError(
                f"No Dhan quote for {symbol}",
                self.broker_name.value,
                metadata={"symbol": symbol, "security_id": security_id},
            )
        ts_raw = quote_raw.get("lastTradeTime") or quote_raw.get("timestamp")
        try:
            ts = (
                datetime.fromtimestamp(int(ts_raw), tz=UTC)
                if ts_raw
                else datetime.now(UTC)
            )
        except (TypeError, ValueError):
            ts = datetime.now(UTC)
        return Quote(
            symbol=symbol,
            exchange=exchange,
            ltp=_money(quote_raw.get("last_price") or quote_raw.get("ltp")),
            bid=_money(quote_raw.get("bid_price") or quote_raw.get("bid")),
            ask=_money(quote_raw.get("ask_price") or quote_raw.get("ask")),
            volume=int(quote_raw.get("volume", 0) or 0),
            timestamp=ts,
        )

    # ══════════════════════════════════════════════════════════════════
    # Kill switch
    # ══════════════════════════════════════════════════════════════════

    @track_latency("dhan.square_off_all")
    async def square_off_all(self) -> list[OrderResponse]:
        positions = await self.get_positions()

        async def _close(pos: Position) -> OrderResponse:
            side = OrderSide.SELL if pos.quantity > 0 else OrderSide.BUY
            order = OrderRequest(
                symbol=pos.symbol,
                exchange=pos.exchange,
                side=side,
                quantity=abs(pos.quantity),
                order_type=OrderType.MARKET,
                product_type=pos.product_type,
                tag="kill-switch",
            )
            try:
                return await self.place_order(order)
            except BrokerError as exc:
                self._log.error(
                    "dhan.square_off_failed",
                    symbol=pos.symbol,
                    error=str(exc),
                )
                return OrderResponse(
                    broker_order_id="",
                    status=OrderStatus.REJECTED,
                    message=str(exc),
                    raw_response={"error": str(exc), "symbol": pos.symbol},
                )

        return list(await asyncio.gather(*(_close(p) for p in positions)))

    @track_latency("dhan.cancel_all_pending")
    async def cancel_all_pending(self) -> int:
        rows = await self._call_list("orderbook", "GET", "/orders")
        pending_ids: list[str] = []
        for row in rows:
            status = _STATUS_FROM_DHAN.get(
                str(row.get("orderStatus", "")).upper(), OrderStatus.PENDING
            )
            if status not in (OrderStatus.PENDING, OrderStatus.OPEN):
                continue
            oid = row.get("orderId") or row.get("dhanOrderId")
            if oid:
                pending_ids.append(str(oid))

        if not pending_ids:
            return 0

        async def _cancel(oid: str) -> bool:
            try:
                return await self.cancel_order(oid)
            except BrokerError as exc:
                self._log.warning(
                    "dhan.cancel_failed", order_id=oid, error=str(exc)
                )
                return False

        results = await asyncio.gather(*(_cancel(i) for i in pending_ids))
        return sum(1 for r in results if r)

    # ══════════════════════════════════════════════════════════════════
    # Symbol mapping
    # ══════════════════════════════════════════════════════════════════

    def normalize_symbol(self, tradingview_symbol: str, exchange: Exchange) -> str:
        """TradingView symbol → Dhan trading-symbol format.

        Dhan's order payload carries both a ``securityId`` (numeric) and
        a ``tradingSymbol`` (string). This method returns the latter —
        services continue to call :meth:`get_security_id` for the
        numeric form when building the HTTP body.

        The function is synchronous per the ``BrokerInterface`` contract,
        so it does NOT load the scrip master; passing a symbol through
        when we have no cached mapping is safe because the real
        :meth:`get_security_id` call will enforce it.
        """
        sym = tradingview_symbol.strip().upper()
        if not sym:
            raise BrokerInvalidSymbolError(
                "Empty symbol",
                self.broker_name.value,
                metadata={"input": tradingview_symbol},
            )
        return sym

    async def validate_symbol(self, symbol: str, exchange: Exchange) -> None:
        """Probe the scrip master — raises :class:`BrokerInvalidSymbolError`
        if the symbol is unknown on the requested exchange. Reuses
        :meth:`get_security_id` so the lookup path (cache + on-demand
        download + raise-on-miss) is identical to the order-placement code.
        """
        await self.get_security_id(symbol, exchange)

    async def get_security_id(self, symbol: str, exchange: Exchange) -> str:
        """Return Dhan's numeric ``securityId`` for a given symbol.

        Hits the scrip-master cache, triggering a one-off download if
        necessary. Raises :class:`BrokerInvalidSymbolError` when the
        symbol isn't in the master (delisted / typo / wrong segment).
        """
        segment = _EXCHANGE_TO_DHAN_SEGMENT.get(exchange)
        if segment is None:
            raise BrokerInvalidSymbolError(
                f"Unsupported exchange for Dhan: {exchange.value}",
                self.broker_name.value,
                metadata={"exchange": exchange.value},
            )
        await self.download_scrip_master()
        security_id = _SCRIP_MASTER.lookup(symbol.upper(), segment)
        if not security_id:
            raise BrokerInvalidSymbolError(
                f"Symbol {symbol!r} not found in Dhan scrip master",
                self.broker_name.value,
                metadata={"symbol": symbol, "segment": segment},
            )
        return security_id

    async def download_scrip_master(self) -> None:
        """Ensure the scrip master is loaded (no-op if already fresh)."""
        http = await self._ensure_http_client()
        await _SCRIP_MASTER.ensure_loaded(http, self._scrip_url)

    async def get_lot_size(self, symbol: str, exchange: Exchange) -> int | None:
        """Return Dhan's lot_size for ``(symbol, exchange)``, or None.

        Resolves through :meth:`get_security_id` so a missing symbol
        raises :class:`BrokerInvalidSymbolError` consistent with the
        order-placement path. ``None`` is returned only when the row was
        present but its ``SEM_LOT_UNITS`` cell was empty/unparseable —
        in practice that means the master is malformed.
        """
        security_id = await self.get_security_id(symbol, exchange)
        return _SCRIP_MASTER.lot_size(security_id)

    # ══════════════════════════════════════════════════════════════════
    # HTTP plumbing
    # ══════════════════════════════════════════════════════════════════

    async def _ensure_http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            limits = httpx.Limits(
                max_connections=_HTTP_POOL_SIZE,
                max_keepalive_connections=_HTTP_POOL_SIZE,
                keepalive_expiry=30.0,
            )
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=limits,
                headers={
                    "access-token": self._access_token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._http

    async def aclose(self) -> None:
        """Release the httpx pool."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _call(
        self,
        op: str,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue one HTTP call with retry + typed error mapping."""
        try:
            async for retry in AsyncRetrying(
                stop=stop_after_attempt(_RETRY_ATTEMPTS),
                wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
                retry=retry_if_exception_type(_TRANSIENT),
                reraise=True,
            ):
                with retry:
                    return await self._attempt(op, method, path, json)
        except RetryError as exc:  # pragma: no cover — reraise=True bubbles the original
            raise BrokerConnectionError(
                f"Dhan {op} exhausted retries",
                self.broker_name.value,
                original_error=exc,
            ) from exc
        raise AssertionError("unreachable: AsyncRetrying exited without result")

    async def _attempt(
        self,
        op: str,
        method: str,
        path: str,
        json: dict[str, Any] | None,
    ) -> dict[str, Any]:
        http = await self._ensure_http_client()
        started = datetime.now(UTC)
        try:
            response = await http.request(method, path, json=json)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise BrokerConnectionError(
                f"Dhan {op} network failure",
                self.broker_name.value,
                original_error=exc,
                metadata={"operation": op, "path": path},
            ) from exc
        except httpx.HTTPError as exc:
            raise BrokerConnectionError(
                f"Dhan {op} unexpected HTTP error",
                self.broker_name.value,
                original_error=exc,
                metadata={"operation": op, "path": path},
            ) from exc

        latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        self._log.info(
            "dhan.http",
            operation=op,
            method=method,
            path=path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        if response.status_code == 401:
            raise BrokerAuthError(
                "Dhan access token rejected",
                self.broker_name.value,
                metadata={"operation": op, "path": path},
            )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise BrokerRateLimitError(
                "Dhan rate limit hit",
                self.broker_name.value,
                retry_after=(float(retry_after) if retry_after else None),
                metadata={"operation": op, "path": path},
            )
        if 500 <= response.status_code < 600:
            raise BrokerConnectionError(
                f"Dhan {op} server error {response.status_code}",
                self.broker_name.value,
                metadata={"status_code": response.status_code, "path": path},
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise BrokerConnectionError(
                f"Dhan {op} returned non-JSON body",
                self.broker_name.value,
                original_error=exc,
                metadata={"status_code": response.status_code},
            ) from exc

        if 400 <= response.status_code < 500:
            _raise_for_error(body, op, self.broker_name.value)

        if isinstance(body, dict) and body.get("status") == "failure":
            _raise_for_error(body, op, self.broker_name.value)

        if isinstance(body, list):
            return {"data": body}
        return body

    async def _call_list(
        self, op: str, method: str, path: str
    ) -> list[dict[str, Any]]:
        """Convenience wrapper for endpoints that return a JSON array."""
        body = await self._call(op, method, path)
        raw = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(raw, list):
            return list(raw)
        return []

    async def _build_order_payload(self, order: OrderRequest) -> dict[str, Any]:
        segment = _EXCHANGE_TO_DHAN_SEGMENT.get(order.exchange)
        if segment is None:
            raise BrokerInvalidSymbolError(
                f"Unsupported exchange for Dhan: {order.exchange.value}",
                self.broker_name.value,
                metadata={"exchange": order.exchange.value},
            )
        security_id = await self.get_security_id(order.symbol, order.exchange)
        payload: dict[str, Any] = {
            "dhanClientId": self._client_id,
            "transactionType": _SIDE_TO_DHAN[order.side],
            "exchangeSegment": segment,
            "productType": _PRODUCT_TO_DHAN[order.product_type],
            "orderType": _TYPE_TO_DHAN[order.order_type],
            "validity": "DAY",
            "securityId": security_id,
            "tradingSymbol": order.symbol.upper(),
            "quantity": order.quantity,
            "disclosedQuantity": 0,
            "price": float(order.price) if order.price is not None else 0.0,
            "triggerPrice": (
                float(order.trigger_price)
                if order.trigger_price is not None
                else 0.0
            ),
        }
        if order.tag:
            payload["correlationId"] = order.tag
        return payload


# ═══════════════════════════════════════════════════════════════════════
# Error helpers
# ═══════════════════════════════════════════════════════════════════════


def _raise_for_error(body: Any, op: str, broker: str) -> None:
    """Translate a Dhan error JSON body into the typed exception hierarchy.

    Dhan returns errors in one of two shapes:

    * ``{"status": "failure", "errorCode": "DH-905", "errorMessage": "..."}``
    * ``{"errorCode": "DH-905", "errorMessage": "...", "httpStatus": 400}``
    """
    if not isinstance(body, dict):
        raise BrokerOrderError(
            f"Dhan {op} failed with non-dict body",
            broker,
            metadata={"operation": op, "raw": body},
        )
    code = str(body.get("errorCode") or body.get("code") or "")
    message = str(
        body.get("errorMessage") or body.get("message") or f"Dhan {op} failed"
    )
    metadata = {"operation": op, "code": code, "raw": body}

    exc_cls = _DHAN_ERROR_MAP.get(code)
    if exc_cls is BrokerOrderRejectedError:
        raise BrokerOrderRejectedError(
            message, broker, reason=message, metadata=metadata
        )
    if exc_cls is BrokerRateLimitError:
        raise BrokerRateLimitError(message, broker, metadata=metadata)
    if exc_cls is not None:
        raise exc_cls(message, broker, metadata=metadata)

    # Fallback — order-flow ops should surface as rejection so audit logs
    # record a reason; every other op is a generic broker error.
    if op in {"place_order", "modify_order", "cancel_order"}:
        raise BrokerOrderRejectedError(
            message, broker, reason=message, metadata=metadata
        )
    raise BrokerOrderError(message, broker, metadata=metadata)


__all__ = ["DhanBroker"]
