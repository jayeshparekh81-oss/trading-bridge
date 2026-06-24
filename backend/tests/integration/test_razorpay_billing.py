"""Razorpay billing — Phase 2 Module 1 (MOCKED Razorpay, no live calls).

Proves, against the real (sqlite) schema:
    (a) subscription creation persists the row + handles, reuses create-if-absent plan map
    (b) webhook signature: valid passes, invalid rejected (no plan granted)
    (c) webhook endpoint gate (TestClient): bad signature -> 400, grants nothing
    (d) idempotent webhook: a duplicate event_id has a SINGLE effect
    (e) plan_status transitions drive the EXISTING entitlement (plan_is_active)
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.entitlements import plan_is_active
from app.core.security import compute_hmac_signature
from app.db.models.razorpay_payment import RazorpayPayment
from app.db.models.razorpay_webhook_event import RazorpayWebhookEvent
from app.db.models.subscription_plan import SubscriptionPlan
from app.db.models.user import User
from app.services import razorpay_billing
from app.services.razorpay_client import verify_webhook_signature

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
        self.plan = _Resource({"id": "plan_TEST123"})
        self.subscription = _Resource(
            {"id": "sub_TEST123", "status": "created", "short_url": "https://rzp.test/x"}
        )


async def _seed_user_and_plan(
    maker: async_sessionmaker[AsyncSession], *, tier: str = "pro"
) -> tuple[Any, Any]:
    import uuid as _uuid

    async with maker() as s:
        user = User(email=f"bill-{_uuid.uuid4().hex}@t.com", password_hash="x", is_active=True)
        s.add(user)
        plan = SubscriptionPlan(
            name="Pro", tier=f"{tier}-{_uuid.uuid4().hex[:6]}",
            price_monthly_inr=Decimal("2499"), price_yearly_inr=Decimal("24990"),
            feature_limits={}, is_active=True, sort_order=1,
        )
        s.add(plan)
        await s.commit()
        return user.id, plan.id


def _event(event_type: str, sub_id: str, *, pay_id: str | None = None) -> dict:
    payload: dict[str, Any] = {
        "subscription": {"entity": {"id": sub_id, "current_end": _FUTURE_EPOCH}}
    }
    if pay_id:
        payload["payment"] = {"entity": {"id": pay_id}}
    return payload


# ── (a) subscription creation ─────────────────────────────────────────


def test_create_subscription_persists_and_returns_handle(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    monkeypatch.setattr(
        "app.services.razorpay_billing.get_razorpay_client", lambda: fake
    )
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_PUBLICKEY")
    from app.core import config as _config

    _config.get_settings.cache_clear()

    async def _inner() -> tuple[dict, Any, Any, Any]:
        uid, pid = await _seed_user_and_plan(db_session_maker)
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            plan = await s.get(SubscriptionPlan, pid)
            result = await razorpay_billing.create_subscription_for_user(
                s, user=user, plan=plan
            )
            row = await s.scalar(
                select(RazorpayPayment).where(RazorpayPayment.user_id == uid)
            )
            return result, row, user.razorpay_subscription_id, plan.razorpay_plan_id

    result, row, user_sub, plan_rzp = _run(_inner())
    _config.get_settings.cache_clear()

    assert result["razorpay_subscription_id"] == "sub_TEST123"
    assert result["razorpay_key_id"] == "rzp_test_PUBLICKEY"  # PUBLIC key only
    assert row is not None and row.razorpay_subscription_id == "sub_TEST123"
    assert row.status == "created"
    assert user_sub == "sub_TEST123"           # handle persisted on the user
    assert plan_rzp == "plan_TEST123"          # plan create-if-absent mapped
    assert len(fake.subscription.calls) == 1   # exactly one Razorpay subscription


# ── (b) signature verification (unit) ─────────────────────────────────


def test_verify_webhook_signature_valid_and_invalid() -> None:
    body = b'{"event":"subscription.charged"}'
    secret = "whsec_test"
    good = compute_hmac_signature(body, secret)
    assert verify_webhook_signature(body, good, secret) is True
    assert verify_webhook_signature(body, "deadbeef", secret) is False
    assert verify_webhook_signature(body, None, secret) is False  # missing header
    assert verify_webhook_signature(body, good, "") is False       # no secret => reject


# ── (c) webhook ENDPOINT signature gate (TestClient) ──────────────────


def test_webhook_endpoint_rejects_bad_signature_grants_nothing(
    client: Any,
    db_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: Any,
) -> None:
    secret = "whsec_endpoint_test"
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", secret)
    from app.core import config as _config

    _config.get_settings.cache_clear()

    async def _seed() -> Any:
        uid, pid = await _seed_user_and_plan(db_session_maker)
        async with db_session_maker() as s:
            s.add(RazorpayPayment(
                user_id=uid, plan_id=pid, razorpay_subscription_id="sub_EP",
                status="created", amount_inr=Decimal("2499"),
            ))
            await s.commit()
        return uid

    uid = _run(_seed())
    body = json.dumps({"event": "subscription.charged", "created_at": 1,
                       "payload": _event("subscription.charged", "sub_EP", pay_id="pay_EP")}).encode()

    # INVALID signature -> 400, no entitlement.
    bad = client.post("/api/billing/webhook/razorpay", content=body,
                      headers={"X-Razorpay-Signature": "not-a-real-sig"})
    assert bad.status_code == 400, bad.text

    # VALID signature -> 200 + entitlement applied (reuses plan_status).
    good_sig = compute_hmac_signature(body, secret)
    ok = client.post("/api/billing/webhook/razorpay", content=body,
                     headers={"X-Razorpay-Signature": good_sig})
    assert ok.status_code == 200, ok.text
    assert ok.json()["applied"] is True

    async def _check() -> str:
        async with db_session_maker() as s:
            u = await s.get(User, uid)
            return u.plan_status

    assert _run(_check()) == "active"
    _config.get_settings.cache_clear()


# ── (d) idempotent webhook — single effect ────────────────────────────


def test_duplicate_webhook_event_has_single_effect(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async def _inner() -> tuple[str, str, int]:
        uid, pid = await _seed_user_and_plan(db_session_maker)
        async with db_session_maker() as s:
            s.add(RazorpayPayment(
                user_id=uid, plan_id=pid, razorpay_subscription_id="sub_DUP",
                status="created",
            ))
            await s.commit()

        async with db_session_maker() as s:
            # First delivery (charged) -> active.
            r1 = await razorpay_billing.handle_webhook_event(
                s, event_id="evt_DUP", event_type="subscription.charged",
                payload=_event("subscription.charged", "sub_DUP", pay_id="pay_1"),
            )
        async with db_session_maker() as s:
            # SAME event_id, but a 'cancelled' body — must be DEDUPED (no effect).
            r2 = await razorpay_billing.handle_webhook_event(
                s, event_id="evt_DUP", event_type="subscription.cancelled",
                payload=_event("subscription.cancelled", "sub_DUP"),
            )
        async with db_session_maker() as s:
            u = await s.get(User, uid)
            n_events = await s.scalar(
                select(__import__("sqlalchemy").func.count()).select_from(RazorpayWebhookEvent)
            )
            return r1["status"], (u.plan_status, r2["status"]), n_events

    s1, (final_status, s2), n_events = _run(_inner())
    assert s1 == "applied"
    assert s2 == "duplicate"          # second delivery deduped
    assert final_status == "active"   # the cancelled NEVER applied => single effect
    assert n_events == 1              # only one ledger row for the event_id


# ── (e) plan_status transitions reuse the entitlement model ───────────


def test_plan_status_transitions_reuse_entitlement(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async def _inner() -> tuple[bool, bool]:
        uid, pid = await _seed_user_and_plan(db_session_maker)
        async with db_session_maker() as s:
            s.add(RazorpayPayment(
                user_id=uid, plan_id=pid, razorpay_subscription_id="sub_TRANS",
                status="created",
            ))
            await s.commit()

        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_charged", event_type="subscription.charged",
                payload=_event("subscription.charged", "sub_TRANS", pay_id="pay_T"),
            )
        async with db_session_maker() as s:
            u = await s.get(User, uid)
            active_ok = (
                u.plan_status == "active"
                and u.active_plan_id == pid
                and plan_is_active(u) is True
            )

        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_cancelled", event_type="subscription.cancelled",
                payload=_event("subscription.cancelled", "sub_TRANS"),
            )
        async with db_session_maker() as s:
            u = await s.get(User, uid)
            cancelled_ok = u.plan_status == "cancelled" and plan_is_active(u) is False

        return active_ok, cancelled_ok

    active_ok, cancelled_ok = _run(_inner())
    assert active_ok, "subscription.charged must drive plan_status=active (entitlement)"
    assert cancelled_ok, "subscription.cancelled must drive plan_status=cancelled"
