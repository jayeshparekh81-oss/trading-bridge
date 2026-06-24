"""Razorpay marketplace subscriptions — Phase 2 Module 2 (MOCKED Razorpay).

Proves, against the real (sqlite) schema, that the M1 Razorpay plumbing is
REUSED for marketplace per-strategy subscriptions:

    (a) subscribe creates a PENDING sub (NOT active) + a Razorpay subscription;
        subscriber_count is NOT bumped until payment confirms
    (b) the ONE webhook, routed by ``kind='marketplace'``, flips charged -> active
        (+ access_until, + paid amount, + subscriber_count) and leaves the
        platform entitlement (``users.plan_status``) untouched
    (c) cancelled -> cancelled (+ subscriber_count decremented)
    (d) idempotent: a duplicate event_id has a SINGLE effect (no double count)
    (e) the SHARED, signature-verified webhook endpoint rejects a bad signature
        (no activation) and accepts a good one
    (f) PAYING != REAL TRADING — across the full subscribe + activate cycle the
        broker order entrypoints are NEVER called and ``paywall_enforced`` /
        fan-out stay OFF.

No live Razorpay calls — the client is mocked; no broker is ever constructed.
"""

from __future__ import annotations

import asyncio
import json
import uuid as _uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import compute_hmac_signature
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.razorpay_payment import RazorpayPayment
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.services import razorpay_billing

_FUTURE_EPOCH = 4102444800  # 2100-01-01 — a fixed future "current_end"


def _run(coro: Any) -> Any:
    return asyncio.get_event_loop().run_until_complete(coro)


class _Resource:
    def __init__(self, created: dict) -> None:
        self._created = created
        self.calls: list[dict] = []

    def create(self, data: dict) -> dict:
        self.calls.append(data)
        return self._created


class _FakeRazorpay:
    """Stand-in for ``razorpay.Client`` — records calls, returns canned ids."""

    def __init__(self) -> None:
        self.plan = _Resource({"id": "plan_MKT123"})
        self.subscription = _Resource(
            {"id": "sub_MKT123", "status": "created", "short_url": "https://rzp.test/m"}
        )


def _configure_razorpay(monkeypatch: Any, fake: _FakeRazorpay) -> None:
    """Point the service at the fake client + set PUBLIC/secret keys."""
    monkeypatch.setattr(
        "app.services.razorpay_billing.get_razorpay_client", lambda: fake
    )
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_PUBLICKEY")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "rzp_test_SECRET")
    from app.core import config as _config

    _config.get_settings.cache_clear()


async def _seed_listing(
    maker: async_sessionmaker[AsyncSession], *, price: Decimal = Decimal("499")
) -> tuple[Any, Any, Any]:
    """A creator + a published, priced listing + a separate subscriber.

    Returns ``(subscriber_id, listing_id, creator_id)``.
    """
    async with maker() as s:
        creator = User(email=f"mk-c-{_uuid.uuid4().hex}@t.com", password_hash="x", is_active=True)
        subscriber = User(email=f"mk-s-{_uuid.uuid4().hex}@t.com", password_hash="x", is_active=True)
        s.add_all([creator, subscriber])
        await s.flush()
        strat = Strategy(user_id=creator.id, name="mk-strat")
        s.add(strat)
        await s.flush()
        listing = MarketplaceListing(
            strategy_id=strat.id,
            creator_id=creator.id,
            title="RSI scalper",
            description="d",
            price_inr=price,
            tags=[],
            status="published",
            subscriber_count=0,
        )
        s.add(listing)
        await s.commit()
        return subscriber.id, listing.id, creator.id


def _event(event_type: str, sub_id: str, *, pay_id: str | None = None) -> dict:
    payload: dict[str, Any] = {
        "subscription": {"entity": {"id": sub_id, "current_end": _FUTURE_EPOCH}}
    }
    if pay_id:
        payload["payment"] = {"entity": {"id": pay_id}}
    return payload


# ── (a) subscribe creates PENDING (not active) + a Razorpay subscription ──


def test_subscribe_creates_pending_subscription_and_razorpay_sub(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    _configure_razorpay(monkeypatch, fake)

    async def _inner() -> tuple[dict, Any, Any, int]:
        sub_uid, listing_id, _creator = await _seed_listing(db_session_maker)
        async with db_session_maker() as s:
            user = await s.get(User, sub_uid)
            listing = await s.get(MarketplaceListing, listing_id)
            result = await razorpay_billing.create_subscription_for_listing(
                s, user=user, listing=listing
            )
        async with db_session_maker() as s:
            msub = await s.scalar(
                select(MarketplaceSubscription).where(
                    MarketplaceSubscription.subscriber_id == sub_uid
                )
            )
            pay = await s.scalar(
                select(RazorpayPayment).where(
                    RazorpayPayment.razorpay_subscription_id == "sub_MKT123"
                )
            )
            listing2 = await s.get(MarketplaceListing, listing_id)
            return result, msub, pay, listing2.subscriber_count

    result, msub, pay, count = _run(_inner())
    _from = __import__("app.core.config", fromlist=["get_settings"])
    _from.get_settings.cache_clear()

    # Returned checkout handle.
    assert result["razorpay_subscription_id"] == "sub_MKT123"
    assert result["razorpay_key_id"] == "rzp_test_PUBLICKEY"  # PUBLIC key only
    assert result["amount_inr"] == 499.0

    # PENDING — not active, nothing captured, handle stored.
    assert msub is not None
    assert msub.status == "pending"
    assert msub.amount_paid_inr == Decimal("0")
    assert msub.razorpay_subscription_id == "sub_MKT123"

    # The payment row is the marketplace router back to the sub.
    assert pay is not None
    assert pay.kind == "marketplace"
    assert pay.marketplace_subscription_id == msub.id
    assert pay.status == "created"

    # subscriber_count NOT bumped for a pending sub.
    assert count == 0
    # Exactly one Razorpay plan + one subscription created.
    assert len(fake.plan.calls) == 1
    assert len(fake.subscription.calls) == 1


# ── (b) webhook charged -> active; platform entitlement untouched ─────────


def test_webhook_charged_activates_marketplace_sub_only(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    _configure_razorpay(monkeypatch, fake)

    async def _inner() -> tuple[str, Any, int, str]:
        sub_uid, listing_id, _creator = await _seed_listing(db_session_maker)
        async with db_session_maker() as s:
            user = await s.get(User, sub_uid)
            listing = await s.get(MarketplaceListing, listing_id)
            await razorpay_billing.create_subscription_for_listing(
                s, user=user, listing=listing
            )
        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_mk_charged", event_type="subscription.charged",
                payload=_event("subscription.charged", "sub_MKT123", pay_id="pay_1"),
            )
        async with db_session_maker() as s:
            msub = await s.scalar(
                select(MarketplaceSubscription).where(
                    MarketplaceSubscription.subscriber_id == sub_uid
                )
            )
            listing2 = await s.get(MarketplaceListing, listing_id)
            user2 = await s.get(User, sub_uid)
            return msub.status, msub.access_until, listing2.subscriber_count, user2.plan_status

    status_, access_until, count, plan_status = _run(_inner())
    __import__("app.core.config", fromlist=["get_settings"]).get_settings.cache_clear()

    assert status_ == "active"          # charged -> active
    assert access_until is not None     # access window set from current_end
    assert count == 1                   # counted exactly once on activation
    # The marketplace charge must NOT have leaked into the PLATFORM entitlement.
    assert plan_status == "none"


# ── (c) webhook cancelled -> cancelled (+ count decremented) ──────────────


def test_webhook_cancelled_marks_marketplace_sub_cancelled(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    _configure_razorpay(monkeypatch, fake)

    async def _inner() -> tuple[str, int]:
        sub_uid, listing_id, _creator = await _seed_listing(db_session_maker)
        async with db_session_maker() as s:
            user = await s.get(User, sub_uid)
            listing = await s.get(MarketplaceListing, listing_id)
            await razorpay_billing.create_subscription_for_listing(
                s, user=user, listing=listing
            )
        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_mk_charged2", event_type="subscription.charged",
                payload=_event("subscription.charged", "sub_MKT123", pay_id="pay_2"),
            )
        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_mk_cancelled", event_type="subscription.cancelled",
                payload=_event("subscription.cancelled", "sub_MKT123"),
            )
        async with db_session_maker() as s:
            msub = await s.scalar(
                select(MarketplaceSubscription).where(
                    MarketplaceSubscription.subscriber_id == sub_uid
                )
            )
            listing2 = await s.get(MarketplaceListing, listing_id)
            return msub.status, listing2.subscriber_count

    status_, count = _run(_inner())
    __import__("app.core.config", fromlist=["get_settings"]).get_settings.cache_clear()

    assert status_ == "cancelled"
    assert count == 0  # active -> cancelled releases the counted seat


# ── (d) idempotent: a duplicate event_id has a SINGLE effect ──────────────


def test_duplicate_marketplace_webhook_single_effect(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    _configure_razorpay(monkeypatch, fake)

    async def _inner() -> tuple[str, str, str, int]:
        sub_uid, listing_id, _creator = await _seed_listing(db_session_maker)
        async with db_session_maker() as s:
            user = await s.get(User, sub_uid)
            listing = await s.get(MarketplaceListing, listing_id)
            await razorpay_billing.create_subscription_for_listing(
                s, user=user, listing=listing
            )
        async with db_session_maker() as s:
            r1 = await razorpay_billing.handle_webhook_event(
                s, event_id="evt_mk_dup", event_type="subscription.charged",
                payload=_event("subscription.charged", "sub_MKT123", pay_id="pay_a"),
            )
        async with db_session_maker() as s:
            # SAME event_id (re-delivery) -> must be deduped, no second count.
            r2 = await razorpay_billing.handle_webhook_event(
                s, event_id="evt_mk_dup", event_type="subscription.charged",
                payload=_event("subscription.charged", "sub_MKT123", pay_id="pay_a"),
            )
        async with db_session_maker() as s:
            msub = await s.scalar(
                select(MarketplaceSubscription).where(
                    MarketplaceSubscription.subscriber_id == sub_uid
                )
            )
            listing2 = await s.get(MarketplaceListing, listing_id)
            return r1["status"], r2["status"], msub.status, listing2.subscriber_count

    s1, s2, final_status, count = _run(_inner())
    __import__("app.core.config", fromlist=["get_settings"]).get_settings.cache_clear()

    assert s1 == "applied"
    assert s2 == "duplicate"     # second delivery deduped
    assert final_status == "active"
    assert count == 1            # counted exactly once despite two deliveries


# ── (e) the SHARED signature-verified webhook endpoint handles marketplace ─


def test_shared_webhook_endpoint_signature_gate_for_marketplace(
    client: Any,
    db_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: Any,
) -> None:
    fake = _FakeRazorpay()
    _configure_razorpay(monkeypatch, fake)
    secret = "whsec_mk_endpoint"
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", secret)
    from app.core import config as _config

    _config.get_settings.cache_clear()

    async def _seed() -> Any:
        sub_uid, listing_id, _creator = await _seed_listing(db_session_maker)
        async with db_session_maker() as s:
            user = await s.get(User, sub_uid)
            listing = await s.get(MarketplaceListing, listing_id)
            await razorpay_billing.create_subscription_for_listing(
                s, user=user, listing=listing
            )
        return sub_uid

    sub_uid = _run(_seed())
    body = json.dumps({
        "event": "subscription.charged", "created_at": 1,
        "payload": _event("subscription.charged", "sub_MKT123", pay_id="pay_ep"),
    }).encode()

    # INVALID signature -> 400, no activation (still pending).
    bad = client.post("/api/billing/webhook/razorpay", content=body,
                      headers={"X-Razorpay-Signature": "not-a-real-sig"})
    assert bad.status_code == 400, bad.text

    async def _status() -> str:
        async with db_session_maker() as s:
            msub = await s.scalar(
                select(MarketplaceSubscription).where(
                    MarketplaceSubscription.subscriber_id == sub_uid
                )
            )
            return msub.status

    assert _run(_status()) == "pending"  # bad sig granted nothing

    # VALID signature -> 200 + activation (ONE shared webhook, routed to mkt).
    good_sig = compute_hmac_signature(body, secret)
    ok = client.post("/api/billing/webhook/razorpay", content=body,
                     headers={"X-Razorpay-Signature": good_sig})
    assert ok.status_code == 200, ok.text
    assert ok.json()["applied"] is True
    assert _run(_status()) == "active"
    _config.get_settings.cache_clear()


# ── (f) paying != real trading: zero broker calls, fan-out + paywall OFF ───


def test_paid_marketplace_subscription_triggers_no_execution(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    _configure_razorpay(monkeypatch, fake)

    # Install recorders on BOTH broker order entrypoints. Nothing in the
    # payment/subscription path should ever touch a broker.
    from app.brokers import dhan as _dhan
    from app.brokers import fyers as _fyers

    calls: list[str] = []

    async def _record_dhan(self: Any, order: Any) -> Any:  # pragma: no cover - must NOT run
        calls.append("dhan")
        raise AssertionError("broker.place_order must not be called by billing")

    async def _record_fyers(self: Any, order: Any) -> Any:  # pragma: no cover - must NOT run
        calls.append("fyers")
        raise AssertionError("broker.place_order must not be called by billing")

    monkeypatch.setattr(_dhan.DhanBroker, "place_order", _record_dhan)
    monkeypatch.setattr(_fyers.FyersBroker, "place_order", _record_fyers)

    async def _inner() -> str:
        sub_uid, listing_id, _creator = await _seed_listing(db_session_maker)
        async with db_session_maker() as s:
            user = await s.get(User, sub_uid)
            listing = await s.get(MarketplaceListing, listing_id)
            await razorpay_billing.create_subscription_for_listing(
                s, user=user, listing=listing
            )
        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_mk_noexec", event_type="subscription.charged",
                payload=_event("subscription.charged", "sub_MKT123", pay_id="pay_x"),
            )
        async with db_session_maker() as s:
            msub = await s.scalar(
                select(MarketplaceSubscription).where(
                    MarketplaceSubscription.subscriber_id == sub_uid
                )
            )
            return msub.status

    final_status = _run(_inner())

    from app.core.config import get_settings

    settings = get_settings()
    __import__("app.core.config", fromlist=["get_settings"]).get_settings.cache_clear()

    # The subscription is paid + active...
    assert final_status == "active"
    # ...yet ZERO broker calls happened across subscribe + activate.
    assert calls == []
    # ...and the real-execution gates stay OFF (paper-only, no fan-out).
    assert settings.paywall_enforced is False
    assert getattr(settings, "marketplace_fanout_enabled", False) is False
