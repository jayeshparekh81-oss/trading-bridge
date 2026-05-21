"""Bug #4 parity tests — Fyers ``place_order`` rejection catching.

Mirror suite of ``test_dhan_broker.py::TestPlaceOrder`` rejection cluster
(2026-05-20 incident). The Dhan adapter was fixed last night to raise
:class:`BrokerOrderRejectedError` when Fyers / Dhan return ``s=ok`` (or
HTTP 200) together with a status field that already encodes a
rejection. This file pins the same guarantee on the Fyers adapter so a
future switch of any live strategy to Fyers cannot reproduce the
phantom-position pattern.

Fyers ``place_order`` response shapes covered here:

* ``s=ok`` + ``status=5`` (REJECTED)         → BrokerOrderRejectedError
* ``s=ok`` + ``status=1`` (CANCELLED)        → BrokerOrderRejectedError
* ``s=ok`` + ``status=7`` (EXPIRED)          → BrokerOrderRejectedError
                                              (maps to CANCELLED via _STATUS_FROM_FYERS;
                                              raw 7 preserved in metadata)
* ``s=ok`` + ``status=4`` (PENDING / transit) → OK, status=PENDING
* ``s=ok`` + ``status=6`` (OPEN)             → OK, status=OPEN
* ``s=ok`` + ``status=2`` (COMPLETE / filled) → OK, status=COMPLETE
* ``s=ok`` with no ``status`` field          → OK, status=PENDING (back-compat)
* Malformed status (None / "garbage")        → defaults to PENDING (no raise)
* Network failure                            → BrokerConnectionError
* Non-dict / empty payload                   → BrokerOrderError
* Reason-fallback chain (message → emsg → reason → default)

The reused ``fake_sdk`` / ``fake_client`` / ``broker`` fixtures are
imported from :mod:`tests.test_fyers_broker` so this file does NOT
re-declare them — any drift in the shared seed stays in one place.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.brokers.fyers import FyersBroker
from app.core.exceptions import (
    BrokerConnectionError,
    BrokerOrderError,
    BrokerOrderRejectedError,
)
from app.schemas.broker import (
    Exchange,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
)
from tests.test_fyers_broker import (  # noqa: F401 — pytest fixture discovery
    broker,
    fake_client,
    fake_sdk,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _order(**overrides) -> OrderRequest:
    base = {
        "symbol": "RELIANCE",
        "exchange": Exchange.NSE,
        "side": OrderSide.BUY,
        "quantity": 10,
        "order_type": OrderType.MARKET,
        "product_type": ProductType.INTRADAY,
    }
    base.update(overrides)
    return OrderRequest(**base)


# ═══════════════════════════════════════════════════════════════════════
# Tests — rejection cluster (mirrors test_dhan_broker.py L340-436)
# ═══════════════════════════════════════════════════════════════════════


class TestFyersStatusRejectedRaises:
    """``s=ok`` + numeric status indicating rejection MUST raise."""

    async def test_status_5_rejected_with_message_raises(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """Fyers status=5 (REJECTED) + descriptive message → typed error.

        Direct mirror of test_dhan_broker.py::
        test_place_order_raises_on_http200_rejected_with_oms_description.
        Pre-fix this slipped through to strategy_executor as a
        ``status=PENDING`` OrderResponse and birthed a phantom position.
        """
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "FYERS-PHANTOM-1",
            "status": 5,
            "message": "Insufficient balance to place order",
        }
        with pytest.raises(BrokerOrderRejectedError) as exc:
            await broker.place_order(_order())

        assert "Insufficient balance" in exc.value.reason
        assert exc.value.metadata.get("order_status") == 5
        assert exc.value.metadata.get("broker_order_id") == "FYERS-PHANTOM-1"
        assert exc.value.metadata.get("operation") == "place_order"

    async def test_status_1_cancelled_raises(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """status=1 (CANCELLED) with s=ok still raises — same phantom risk."""
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "FYERS-CANC-1",
            "status": 1,
            "message": "Cancelled by exchange",
        }
        with pytest.raises(BrokerOrderRejectedError) as exc:
            await broker.place_order(_order())

        assert "Cancelled by exchange" in exc.value.reason
        assert exc.value.metadata.get("order_status") == 1

    async def test_status_7_expired_raises_and_preserves_raw_status(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """status=7 (EXPIRED) maps to CANCELLED — must raise.

        Mirror of Dhan's EXPIRED→CANCELLED handling. The raw broker
        status (7) is preserved in metadata for audit clarity, NOT
        the normalised CANCELLED constant — operators investigating a
        Fyers incident need to grep the broker's vocabulary.
        """
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "FYERS-EXP-1",
            "status": 7,
            "message": "Order expired before fill",
        }
        with pytest.raises(BrokerOrderRejectedError) as exc:
            await broker.place_order(_order())

        assert "expired" in exc.value.reason.lower()
        assert exc.value.metadata.get("order_status") == 7

    async def test_status_rejected_reason_fallback_chain(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """When ``message`` is absent, the reason falls back to
        ``emsg`` → ``reason`` → a default that includes the raw status."""
        # No message / emsg / reason fields — must fall back to default.
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "FYERS-FALLBACK-1",
            "status": 5,
        }
        with pytest.raises(BrokerOrderRejectedError) as exc:
            await broker.place_order(_order())
        assert "5" in exc.value.reason  # default includes status code

        # emsg branch.
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "FYERS-FALLBACK-2",
            "status": 5,
            "emsg": "Price band exceeded",
        }
        with pytest.raises(BrokerOrderRejectedError) as exc:
            await broker.place_order(_order())
        assert "Price band" in exc.value.reason


# ═══════════════════════════════════════════════════════════════════════
# Tests — legitimate non-rejection statuses must NOT raise
# ═══════════════════════════════════════════════════════════════════════


class TestFyersStatusOkPaths:
    async def test_status_4_pending_returns_pending(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """status=4 (PENDING / transit) is the legitimate queued state.

        TradingView's GTC orders sit here for seconds-to-minutes; raising
        on PENDING would block every market-hours signal. Regression
        target: the bug is ONLY ``REJECTED`` / ``CANCELLED`` — not any
        non-terminal status.
        """
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "FYERS-PEND-1",
            "status": 4,
            "message": "placed",
        }
        resp = await broker.place_order(_order())
        assert resp.broker_order_id == "FYERS-PEND-1"
        assert resp.status is OrderStatus.PENDING

    async def test_status_6_open_returns_open(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """status=6 (OPEN) — limit order resting on the book. Not a rejection."""
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "FYERS-OPEN-1",
            "status": 6,
        }
        resp = await broker.place_order(
            _order(order_type=OrderType.LIMIT, price=Decimal("2500"))
        )
        assert resp.broker_order_id == "FYERS-OPEN-1"
        assert resp.status is OrderStatus.OPEN

    async def test_status_2_complete_returns_complete(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """status=2 (COMPLETE / filled) — market order that filled instantly."""
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "FYERS-FILL-1",
            "status": 2,
            "message": "filled",
        }
        resp = await broker.place_order(_order())
        assert resp.broker_order_id == "FYERS-FILL-1"
        assert resp.status is OrderStatus.COMPLETE


# ═══════════════════════════════════════════════════════════════════════
# Tests — back-compat & robustness
# ═══════════════════════════════════════════════════════════════════════


class TestFyersStatusFieldAbsentOrMalformed:
    async def test_no_status_field_defaults_to_pending(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """Pre-fix shape: ``{"s": "ok", "id": "..."}`` without a status.

        The fix must NOT regress this — the Fyers SDK has historically
        emitted bare ``{"s":"ok","id":"…"}`` for accepted orders. Treat
        absence of ``status`` as PENDING, never as an error.
        """
        fake_client.place_order.return_value = {"s": "ok", "id": "FYERS-BARE-1"}
        resp = await broker.place_order(_order())
        assert resp.broker_order_id == "FYERS-BARE-1"
        assert resp.status is OrderStatus.PENDING

    async def test_garbage_status_value_defaults_to_pending(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """Non-numeric / unparseable status string ⇒ default PENDING.

        A malformed status from Fyers must NOT trigger a phantom rejection.
        The conservative default is PENDING: caller treats the order as
        live, and the reconciliation loop catches any divergence on the
        next sweep. Raising on parse-failure here would crash legitimate
        orders during a Fyers schema drift.
        """
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "FYERS-GARBAGE-1",
            "status": "not-a-number",
        }
        resp = await broker.place_order(_order())
        assert resp.broker_order_id == "FYERS-GARBAGE-1"
        assert resp.status is OrderStatus.PENDING

    async def test_unknown_numeric_status_defaults_to_pending(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """A numeric status not in _STATUS_FROM_FYERS (e.g. 99 future code)
        also defaults to PENDING — same fail-safe rationale."""
        fake_client.place_order.return_value = {
            "s": "ok",
            "id": "FYERS-UNKNOWN-1",
            "status": 99,
        }
        resp = await broker.place_order(_order())
        assert resp.status is OrderStatus.PENDING


# ═══════════════════════════════════════════════════════════════════════
# Tests — network / payload corruption boundaries
# ═══════════════════════════════════════════════════════════════════════


class TestFyersTransportFailures:
    async def test_network_failure_raises_connection_error_not_silent(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """A transport-level failure (TCP / DNS / SSL) must surface as
        :class:`BrokerConnectionError` — NOT a silently-successful
        OrderResponse. Mirrors the spirit of test_dhan_broker.py's
        ``TestErrorSurfaces::test_timeout_maps_to_connection_error``.
        """
        import httpx

        fake_client.place_order.side_effect = httpx.ConnectError(
            "DNS resolution failed"
        )
        with pytest.raises(BrokerConnectionError):
            await broker.place_order(_order())

    async def test_non_dict_payload_raises_order_error(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """A non-dict response body (string / list / None) → BrokerOrderError.

        Goes through ``_raise_for_response`` which guards explicitly
        against non-dict payloads. The bug we're guarding against:
        treating ``"OK"`` (string) or ``None`` as success would create
        a phantom position with an empty broker_order_id.
        """
        fake_client.place_order.return_value = "not-a-dict-payload"
        with pytest.raises(BrokerOrderError, match="non-dict"):
            await broker.place_order(_order())

    async def test_ok_response_without_order_id_raises(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """``s=ok`` but no ``id`` / ``orderId`` field → BrokerOrderError.

        Same defence as the existing ``test_place_order_missing_id_raises``
        in test_fyers_broker.py — kept here for the Bug-#4-cluster
        completeness (the rejection-detection block runs AFTER the no-id
        guard, so verifying both interact correctly belongs in this file)."""
        fake_client.place_order.return_value = {
            "s": "ok",
            "status": 4,  # PENDING — would normally be a happy path
            "message": "no id field",
        }
        with pytest.raises(BrokerOrderError, match="no order id"):
            await broker.place_order(_order())

    async def test_s_error_rejection_still_uses_existing_path(
        self, broker: FyersBroker, fake_client: MagicMock
    ) -> None:
        """Regression: the legacy ``s=error`` rejection path must keep
        raising via ``_raise_for_response`` (NOT via the new
        status-field check). This guards against the new code path
        accidentally swallowing the ``s=error`` shape — which would
        silently mask broker-side validation failures."""
        fake_client.place_order.return_value = {
            "s": "error",
            "code": -9999,
            "message": "freeze qty exceeded",
        }
        with pytest.raises(BrokerOrderRejectedError) as exc:
            await broker.place_order(_order())
        assert exc.value.reason == "freeze qty exceeded"
        # Came through _raise_for_response, not the new status-check
        # block — so metadata should NOT carry the new fields.
        assert exc.value.metadata.get("operation") == "place_order"
        # The new block writes "order_status"; the _raise_for_response
        # path doesn't — confirm we hit the legacy branch.
        assert "order_status" not in exc.value.metadata
