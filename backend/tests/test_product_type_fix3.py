"""Fix #3 — Product type hard guard (permanent rule 1).

See /tmp/PERMANENT_RULES.md and /tmp/3_PRODUCT_TYPE.md.

Incident 2026-05-20 (BSE LTD signal e9b654ea-...): Pine alerts don't
emit ``product_type``; the executor defaulted to INTRADAY for ANY
segment; Dhan would have auto-square-offed the BSE LTD F&O position at
15:15 IST mid-trade, leaving Pine's state diverged from broker reality.

This module tests three defense layers:

1. ``strategy_executor._resolve_product_type`` — segment-aware:
   - F&O segment + missing payload → MARGIN.
   - F&O segment + explicit INTRADAY/MIS → raises
     ``InvalidProductTypeError``.
   - Equity + missing payload → DELIVERY (not INTRADAY).
   - Equity + explicit INTRADAY → INTRADAY (equity exempt).

2. ``dhan._build_order_payload`` — last-chance trap raises
   ``BrokerOrderRejectedError`` if an F&O OrderRequest with
   ``ProductType.INTRADAY`` ever reaches the HTTP body builder.

3. Regression: equity intraday still works (no false positive).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.brokers import dhan as dhan_mod
from app.brokers.dhan import DhanBroker
from app.core.exceptions import BrokerOrderRejectedError
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    Exchange,
    OrderRequest,
    OrderSide,
    OrderType,
    ProductType,
)
from app.services.strategy_executor import (
    InvalidProductTypeError,
    _resolve_product_type,
)


# ═══════════════════════════════════════════════════════════════════════
# Layer 1: strategy_executor._resolve_product_type
# ═══════════════════════════════════════════════════════════════════════


def _signal(product_type: str | None = None) -> SimpleNamespace:
    """Minimal signal stand-in — _resolve_product_type only reads
    signal.raw_payload."""
    payload: dict[str, Any] = {}
    if product_type is not None:
        payload["product_type"] = product_type
    return SimpleNamespace(raw_payload=payload)


class TestResolveProductTypeFnO:
    def test_fno_missing_payload_defaults_to_margin(self) -> None:
        """Pine alerts omit product_type → F&O must default MARGIN, NOT INTRADAY."""
        assert _resolve_product_type(_signal(), Exchange.NFO) is ProductType.MARGIN

    def test_fno_explicit_margin_returns_margin(self) -> None:
        assert (
            _resolve_product_type(_signal("MARGIN"), Exchange.NFO)
            is ProductType.MARGIN
        )

    def test_fno_explicit_nrml_normalises_to_margin(self) -> None:
        assert (
            _resolve_product_type(_signal("NRML"), Exchange.NFO)
            is ProductType.MARGIN
        )

    def test_fno_explicit_intraday_raises_invalid_product_type(self) -> None:
        """Permanent rule 1 — F&O + INTRADAY is FORBIDDEN."""
        with pytest.raises(InvalidProductTypeError) as exc:
            _resolve_product_type(_signal("INTRADAY"), Exchange.NFO)
        assert "FORBIDDEN" in str(exc.value)
        assert "NFO" in str(exc.value)
        assert "MARGIN" in str(exc.value)

    def test_fno_explicit_mis_raises_invalid_product_type(self) -> None:
        """MIS is the Zerodha/Fyers spelling of INTRADAY — same rule."""
        with pytest.raises(InvalidProductTypeError):
            _resolve_product_type(_signal("MIS"), Exchange.NFO)

    def test_bfo_cds_mcx_all_default_margin(self) -> None:
        """Permanent rule 1 covers all F&O segments."""
        for ex in (Exchange.BFO, Exchange.CDS, Exchange.MCX):
            assert _resolve_product_type(_signal(), ex) is ProductType.MARGIN, (
                f"{ex.value} should default to MARGIN"
            )

    def test_bfo_intraday_raises(self) -> None:
        with pytest.raises(InvalidProductTypeError):
            _resolve_product_type(_signal("INTRADAY"), Exchange.BFO)


class TestResolveProductTypeEquity:
    def test_nse_missing_payload_defaults_delivery(self) -> None:
        """Equity should NOT default INTRADAY post-fix; default is DELIVERY."""
        assert (
            _resolve_product_type(_signal(), Exchange.NSE)
            is ProductType.DELIVERY
        )

    def test_nse_explicit_intraday_allowed(self) -> None:
        """Equity intraday is legitimate — rule 1 only covers F&O."""
        assert (
            _resolve_product_type(_signal("INTRADAY"), Exchange.NSE)
            is ProductType.INTRADAY
        )

    def test_nse_explicit_cnc_returns_delivery(self) -> None:
        assert (
            _resolve_product_type(_signal("CNC"), Exchange.NSE)
            is ProductType.DELIVERY
        )

    def test_bse_explicit_mis_allowed_equity(self) -> None:
        """Equity MIS (intraday) for BSE — allowed."""
        assert (
            _resolve_product_type(_signal("MIS"), Exchange.BSE)
            is ProductType.INTRADAY
        )


# ═══════════════════════════════════════════════════════════════════════
# Layer 2: Dhan adapter last-chance trap
# ═══════════════════════════════════════════════════════════════════════


def _creds() -> BrokerCredentials:
    return BrokerCredentials(
        broker=BrokerName.DHAN,
        user_id="11111111-1111-1111-1111-111111111111",
        client_id="CID",
        api_key="K",
        api_secret="S",
        access_token="TOK",
    )


def _seed_scrip_master(pairs: Iterable[tuple[str, str, str]]) -> None:
    sm = dhan_mod._SCRIP_MASTER
    sm._by_symbol = {(s.upper(), seg): sid for s, seg, sid in pairs}
    sm._by_id = {sid: (s.upper(), seg) for s, seg, sid in pairs}
    sm._loaded_at = datetime.now(UTC)


@pytest.fixture(autouse=True)
def _fresh_scrip_master() -> None:
    sm = dhan_mod._SCRIP_MASTER
    sm._by_symbol.clear()
    sm._by_id.clear()
    sm._lot_sizes.clear()
    sm._loaded_at = None


def _broker(handler: Callable[[httpx.Request], httpx.Response]) -> DhanBroker:
    broker = DhanBroker(_creds())
    broker._http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://mock",
        headers={"access-token": "TOK"},
    )
    return broker


class TestDhanAdapterFnOIntradayTrap:
    async def test_nfo_intraday_raises_in_build_payload(self) -> None:
        """Last-chance trap fires for NSE_FNO + INTRADAY at HTTP-body
        construction time."""
        _seed_scrip_master([("NIFTY25MAY-FUT", "NSE_FNO", "12345")])
        # Mock transport — should NEVER be hit because the trap fires
        # in _build_order_payload before the HTTP call.
        broker = _broker(lambda r: httpx.Response(500, json={}))

        order = OrderRequest(
            symbol="NIFTY25MAY-FUT",
            exchange=Exchange.NFO,
            side=OrderSide.BUY,
            quantity=75,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,  # ← FORBIDDEN
        )

        with pytest.raises(BrokerOrderRejectedError) as exc:
            await broker.place_order(order)
        assert "FORBIDDEN" in str(exc.value)
        assert exc.value.reason == "permanent_rule_intraday_for_fno"
        await broker.aclose()

    async def test_bfo_intraday_raises_in_build_payload(self) -> None:
        """BSE_FNO + INTRADAY also blocked."""
        _seed_scrip_master([("BSESTOCK-FUT", "BSE_FNO", "99999")])
        broker = _broker(lambda r: httpx.Response(500, json={}))

        order = OrderRequest(
            symbol="BSESTOCK-FUT",
            exchange=Exchange.BFO,
            side=OrderSide.BUY,
            quantity=75,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
        )

        with pytest.raises(BrokerOrderRejectedError):
            await broker.place_order(order)
        await broker.aclose()

    async def test_nfo_margin_passes_through(self) -> None:
        """F&O + MARGIN — happy path, payload reaches HTTP."""
        _seed_scrip_master([("NIFTY25MAY-FUT", "NSE_FNO", "12345")])
        captured: dict[str, Any] = {}

        def handler(req: httpx.Request) -> httpx.Response:
            import json as _json

            captured["body"] = _json.loads(req.content.decode())
            return httpx.Response(
                200, json={"orderId": "OK-1", "orderStatus": "PENDING"}
            )

        broker = _broker(handler)
        order = OrderRequest(
            symbol="NIFTY25MAY-FUT",
            exchange=Exchange.NFO,
            side=OrderSide.BUY,
            quantity=75,
            order_type=OrderType.MARKET,
            product_type=ProductType.MARGIN,
        )
        resp = await broker.place_order(order)
        assert resp.broker_order_id == "OK-1"
        assert captured["body"]["productType"] == "MARGIN"
        await broker.aclose()

    async def test_nse_equity_intraday_passes_through(self) -> None:
        """Equity INTRADAY is legitimate — rule 1 only covers F&O.
        Regression: must not false-positive on equity."""
        _seed_scrip_master([("RELIANCE", "NSE_EQ", "11536")])
        captured: dict[str, Any] = {}

        def handler(req: httpx.Request) -> httpx.Response:
            import json as _json

            captured["body"] = _json.loads(req.content.decode())
            return httpx.Response(
                200, json={"orderId": "EQ-1", "orderStatus": "PENDING"}
            )

        broker = _broker(handler)
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
        )
        resp = await broker.place_order(order)
        assert resp.broker_order_id == "EQ-1"
        assert captured["body"]["productType"] == "INTRADAY"
        await broker.aclose()
