"""Razorpay payment-lifecycle robustness — Phase 2 Module 4 (MOCKED Razorpay).

Proves the money lifecycle never silently diverges:
    (a) cancel-at-period-end keeps access until plan_expires_at, then the webhook
        expires it; cancel-immediate revokes now
    (b) dunning: a failed renewal -> past_due (access denied), a recovered charge
        -> active; idempotent
    (c) plan change: next-cycle (start_at set => no double charge), correct
        entitlement, and the OLD sub's events are superseded (don't clobber)
    (d) reconciliation flags an injected drift (read-only) + an explicit admin
        apply fixes it
    (e) the SHARED signature-verified webhook handles the new events
    (f) zero trading/broker calls across the whole lifecycle

No live Razorpay calls (client mocked); no broker is ever constructed.
"""

from __future__ import annotations

import asyncio
import json
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.entitlements import plan_is_active
from app.core.security import compute_hmac_signature
from app.db.models.razorpay_payment import RazorpayPayment
from app.db.models.subscription_plan import SubscriptionPlan
from app.db.models.user import User
from app.services import razorpay_billing

_FUTURE = 4102444800  # 2100-01-01 epoch


def _run(coro: Any) -> Any:
    return asyncio.get_event_loop().run_until_complete(coro)


class _Subscription:
    def __init__(self) -> None:
        self.create_calls: list[dict] = []
        self.cancel_calls: list[tuple[str, dict]] = []
        self.fetch_calls: list[str] = []
        self._next_id = "sub_NEW"
        self._fetch: dict[str, dict] = {}

    def create(self, data: dict) -> dict:
        self.create_calls.append(data)
        return {"id": self._next_id, "status": "created", "short_url": "https://rzp/x"}

    def cancel(self, sub_id: str, data: dict) -> dict:
        self.cancel_calls.append((sub_id, data))
        return {"id": sub_id, "status": "cancelled"}

    def fetch(self, sub_id: str) -> dict:
        self.fetch_calls.append(sub_id)
        return self._fetch.get(sub_id, {"id": sub_id, "status": "active"})

    def set_fetch(self, sub_id: str, entity: dict) -> None:
        self._fetch[sub_id] = entity


class _Plan:
    def create(self, data: dict) -> dict:
        return {"id": "plan_X"}


class _FakeRazorpay:
    def __init__(self) -> None:
        self.subscription = _Subscription()
        self.plan = _Plan()


def _configure(monkeypatch: Any, fake: _FakeRazorpay) -> None:
    monkeypatch.setattr(
        "app.services.razorpay_billing.get_razorpay_client", lambda: fake
    )
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_PUBLIC")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "rzp_test_SECRET")
    from app.core import config as _config

    _config.get_settings.cache_clear()


async def _seed_plan(maker: async_sessionmaker[AsyncSession], tier: str) -> Any:
    async with maker() as s:
        plan = SubscriptionPlan(
            name=tier.title(), tier=f"{tier}-{_uuid.uuid4().hex[:6]}",
            price_monthly_inr=Decimal("2499"), price_yearly_inr=Decimal("24990"),
            feature_limits={}, is_active=True, sort_order=1,
        )
        s.add(plan)
        await s.commit()
        return plan.id


async def _seed_active_user(
    maker: async_sessionmaker[AsyncSession],
    *,
    plan_id: Any,
    sub_id: str = "sub_A",
    expires_in_days: int = 30,
) -> Any:
    async with maker() as s:
        user = User(
            email=f"life-{_uuid.uuid4().hex}@t.com", password_hash="x", is_active=True,
            plan_status="active", active_plan_id=plan_id,
            plan_expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
            razorpay_subscription_id=sub_id,
        )
        s.add(user)
        await s.flush()
        s.add(RazorpayPayment(
            user_id=user.id, plan_id=plan_id, kind="platform_plan",
            razorpay_subscription_id=sub_id, status="active",
            amount_inr=Decimal("2499"),
        ))
        await s.commit()
        return user.id


def _event(event_type: str, sub_id: str, *, pay_id: str | None = None) -> dict:
    payload: dict[str, Any] = {
        "subscription": {"entity": {"id": sub_id, "current_end": _FUTURE}}
    }
    if pay_id:
        payload["payment"] = {"entity": {"id": pay_id}}
    return payload


# ── (a) cancellation ─────────────────────────────────────────────────


def test_cancel_at_period_end_keeps_access_then_webhook_expires(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    _configure(monkeypatch, fake)

    async def _inner() -> tuple[dict, bool, str]:
        pid = await _seed_plan(db_session_maker, "pro")
        uid = await _seed_active_user(db_session_maker, plan_id=pid, sub_id="sub_A")
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            res = await razorpay_billing.cancel_subscription_for_user(s, user=user)
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            access_after_cancel = plan_is_active(user)  # still active (future expiry)
        # Webhook fires at cycle end -> cancelled.
        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_cxl", event_type="subscription.cancelled",
                payload=_event("subscription.cancelled", "sub_A"),
            )
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            return res, access_after_cancel, user.plan_status

    res, access_after_cancel, final_status = _run(_inner())
    __import__("app.core.config", fromlist=["x"]).get_settings.cache_clear()

    assert res["at_cycle_end"] is True
    assert res["plan_status"] == "active"          # not revoked at request time
    assert access_after_cancel is True             # access retained until period end
    assert fake.subscription.cancel_calls == [("sub_A", {"cancel_at_cycle_end": 1})]
    assert final_status == "cancelled"             # webhook flipped it at cycle end


def test_access_lapses_when_period_ends(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    _configure(monkeypatch, fake)

    async def _inner() -> bool:
        pid = await _seed_plan(db_session_maker, "pro")
        # expiry already in the PAST -> the period has ended.
        uid = await _seed_active_user(
            db_session_maker, plan_id=pid, sub_id="sub_P", expires_in_days=-1
        )
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            return plan_is_active(user)

    assert _run(_inner()) is False  # access-until-period-end: expired -> denied
    __import__("app.core.config", fromlist=["x"]).get_settings.cache_clear()


def test_cancel_immediate_revokes_now(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    _configure(monkeypatch, fake)

    async def _inner() -> tuple[str, bool]:
        pid = await _seed_plan(db_session_maker, "pro")
        uid = await _seed_active_user(db_session_maker, plan_id=pid, sub_id="sub_I")
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            await razorpay_billing.cancel_subscription_for_user(
                s, user=user, at_cycle_end=False
            )
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            return user.plan_status, plan_is_active(user)

    status_, active = _run(_inner())
    __import__("app.core.config", fromlist=["x"]).get_settings.cache_clear()
    assert status_ == "cancelled"
    assert active is False
    assert fake.subscription.cancel_calls == [("sub_I", {"cancel_at_cycle_end": 0})]


# ── (b) dunning ──────────────────────────────────────────────────────


def test_failed_charge_past_due_then_recovers(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    _configure(monkeypatch, fake)

    async def _inner() -> tuple[str, bool, str, bool, str]:
        pid = await _seed_plan(db_session_maker, "pro")
        uid = await _seed_active_user(db_session_maker, plan_id=pid, sub_id="sub_D")
        # Renewal charge failed -> pending (dunning).
        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_pending", event_type="subscription.pending",
                payload=_event("subscription.pending", "sub_D"),
            )
        async with db_session_maker() as s:
            u = await s.get(User, uid)
            past_due, pd_active = u.plan_status, plan_is_active(u)
        # Duplicate pending -> no double effect.
        async with db_session_maker() as s:
            dup = await razorpay_billing.handle_webhook_event(
                s, event_id="evt_pending", event_type="subscription.pending",
                payload=_event("subscription.pending", "sub_D"),
            )
        # Recovery charge -> active again.
        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_recover", event_type="subscription.charged",
                payload=_event("subscription.charged", "sub_D", pay_id="pay_R"),
            )
        async with db_session_maker() as s:
            u = await s.get(User, uid)
            return past_due, pd_active, dup["status"], plan_is_active(u), u.plan_status

    past_due, pd_active, dup_status, rec_active, final = _run(_inner())
    __import__("app.core.config", fromlist=["x"]).get_settings.cache_clear()
    assert past_due == "past_due"
    assert pd_active is False        # dunning denies access
    assert dup_status == "duplicate"  # idempotent
    assert final == "active"
    assert rec_active is True         # recovered charge re-activates


# ── (c) plan change ──────────────────────────────────────────────────


def test_plan_change_next_cycle_no_double_charge_and_superseded_guard(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    fake.subscription._next_id = "sub_B"
    _configure(monkeypatch, fake)

    async def _inner() -> dict[str, Any]:
        pid_a = await _seed_plan(db_session_maker, "pro")
        pid_b = await _seed_plan(db_session_maker, "premium")
        uid = await _seed_active_user(db_session_maker, plan_id=pid_a, sub_id="sub_A")
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            plan_b = await s.get(SubscriptionPlan, pid_b)
            res = await razorpay_billing.change_plan_for_user(s, user=user, plan=plan_b)
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            handle_after = user.razorpay_subscription_id
            plan_after_change = user.active_plan_id  # still A until B charges
        # OLD sub cancels at cycle end -> superseded -> must NOT clobber.
        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_oldcxl", event_type="subscription.cancelled",
                payload=_event("subscription.cancelled", "sub_A"),
            )
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            status_after_old_cancel = user.plan_status
        # NEW sub's first charge -> entitlement moves to plan B.
        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="evt_newcharge", event_type="subscription.charged",
                payload=_event("subscription.charged", "sub_B", pay_id="pay_B"),
            )
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            return {
                "res": res, "handle_after": handle_after,
                "plan_after_change": plan_after_change, "pid_a": pid_a, "pid_b": pid_b,
                "status_after_old_cancel": status_after_old_cancel,
                "final_plan": user.active_plan_id, "final_status": user.plan_status,
            }

    r = _run(_inner())
    __import__("app.core.config", fromlist=["x"]).get_settings.cache_clear()

    # New sub created with start_at => no overlap / no double charge.
    assert len(fake.subscription.create_calls) == 1
    assert "start_at" in fake.subscription.create_calls[0]
    # Old sub cancelled at cycle end.
    assert ("sub_A", {"cancel_at_cycle_end": 1}) in fake.subscription.cancel_calls
    # Active handle flipped to the new sub immediately.
    assert r["handle_after"] == "sub_B"
    # Entitlement stayed on A through the change + the old sub's cancel (superseded).
    assert r["plan_after_change"] == r["pid_a"]
    assert r["status_after_old_cancel"] == "active"   # old cancel did NOT clobber
    # New charge moved entitlement to B.
    assert r["final_status"] == "active"
    assert r["final_plan"] == r["pid_b"]


# ── (d) reconciliation ───────────────────────────────────────────────


def test_reconcile_flags_drift_and_admin_apply_fixes(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    _configure(monkeypatch, fake)
    # Gateway says cancelled; our DB says active -> drift.
    fake.subscription.set_fetch("sub_R", {"id": "sub_R", "status": "cancelled"})

    async def _inner() -> tuple[dict, dict, str]:
        pid = await _seed_plan(db_session_maker, "pro")
        uid = await _seed_active_user(db_session_maker, plan_id=pid, sub_id="sub_R")
        admin_id = _uuid.uuid4()
        async with db_session_maker() as s:
            report = await razorpay_billing.reconcile_subscription(
                s, razorpay_subscription_id="sub_R"
            )
        async with db_session_maker() as s:
            applied = await razorpay_billing.apply_reconciliation(
                s, razorpay_subscription_id="sub_R", admin_user_id=admin_id
            )
        async with db_session_maker() as s:
            u = await s.get(User, uid)
            return report, applied, u.plan_status

    report, applied, final = _run(_inner())
    __import__("app.core.config", fromlist=["x"]).get_settings.cache_clear()

    assert report["drift"] is True
    assert report["gateway_status"] == "cancelled"
    assert report["local_status"] == "active"
    assert applied["applied"] is True
    assert final == "cancelled"   # explicit admin fix applied the gateway truth


# ── (e) the SHARED signature-verified webhook handles new events ─────


def test_shared_webhook_signature_gate_for_pending_event(
    client: Any,
    db_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: Any,
) -> None:
    secret = "whsec_life"
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", secret)
    from app.core import config as _config

    _config.get_settings.cache_clear()

    async def _seed() -> Any:
        pid = await _seed_plan(db_session_maker, "pro")
        return await _seed_active_user(db_session_maker, plan_id=pid, sub_id="sub_W")

    uid = _run(_seed())
    body = json.dumps({
        "event": "subscription.pending", "created_at": 1,
        "payload": _event("subscription.pending", "sub_W"),
    }).encode()

    bad = client.post("/api/billing/webhook/razorpay", content=body,
                      headers={"X-Razorpay-Signature": "nope"})
    assert bad.status_code == 400, bad.text

    async def _status() -> str:
        async with db_session_maker() as s:
            u = await s.get(User, uid)
            return u.plan_status

    assert _run(_status()) == "active"  # bad sig changed nothing

    good = client.post("/api/billing/webhook/razorpay", content=body,
                       headers={"X-Razorpay-Signature": compute_hmac_signature(body, secret)})
    assert good.status_code == 200, good.text
    assert _run(_status()) == "past_due"  # good sig applied the dunning transition
    _config.get_settings.cache_clear()


# ── (f) paying-lifecycle != trading: zero broker calls ───────────────


def test_lifecycle_triggers_no_broker_calls(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> None:
    fake = _FakeRazorpay()
    fake.subscription._next_id = "sub_B2"
    _configure(monkeypatch, fake)

    from app.brokers import dhan as _dhan
    from app.brokers import fyers as _fyers

    calls: list[str] = []

    async def _boom(self: Any, order: Any) -> Any:  # pragma: no cover - must NOT run
        calls.append("broker")
        raise AssertionError("broker.place_order must not be called by billing")

    monkeypatch.setattr(_dhan.DhanBroker, "place_order", _boom)
    monkeypatch.setattr(_fyers.FyersBroker, "place_order", _boom)

    async def _inner() -> None:
        pid_a = await _seed_plan(db_session_maker, "pro")
        pid_b = await _seed_plan(db_session_maker, "premium")
        uid = await _seed_active_user(db_session_maker, plan_id=pid_a, sub_id="sub_A")
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            await razorpay_billing.cancel_subscription_for_user(s, user=user)
        async with db_session_maker() as s:
            await razorpay_billing.handle_webhook_event(
                s, event_id="e1", event_type="subscription.pending",
                payload=_event("subscription.pending", "sub_A"),
            )
        async with db_session_maker() as s:
            user = await s.get(User, uid)
            plan_b = await s.get(SubscriptionPlan, pid_b)
            await razorpay_billing.change_plan_for_user(s, user=user, plan=plan_b)
        async with db_session_maker() as s:
            await razorpay_billing.reconcile_subscription(s, razorpay_subscription_id="sub_A")

    _run(_inner())
    __import__("app.core.config", fromlist=["x"]).get_settings.cache_clear()
    assert calls == []  # no broker touched across cancel + dunning + change + reconcile
