"""Phase 2 Billing B3.0 — ``require_active_plan`` entitlement gate.

Pins the inert-plumbing contract:

    * Flag OFF (default) ⇒ pure pass-through for EVERY status (none / active /
      expired / cancelled) — attaching the dep is behavior-neutral.
    * Flag ON ⇒ only a genuinely ``active`` + non-expired plan is granted;
      everything else (none / expired / cancelled / lapsed-active) is treated
      as free-tier and blocked from premium with a machine-distinguishable
      ``402 PLAN_REQUIRED``.
    * Billing ⟂ RBAC: the gate reads plan_status + plan_expires_at ONLY —
      role / live_trading_enabled never grant or deny premium.
    * ``UserResponse`` surfaces plan_status / plan_tier / plan_expires_at
      without breaking /me serialization.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.auth.entitlements as ent
from app.auth.entitlements import (
    PAYWALL_STATUS_CODE,
    PLAN_REQUIRED_CODE,
    require_active_plan,
)
from app.db.models.user import User
from app.schemas.auth import UserResponse

# ── helpers ───────────────────────────────────────────────────────────

_FUTURE = datetime(2099, 1, 1, tzinfo=UTC)
_PAST = datetime(2000, 1, 1, tzinfo=UTC)


def _user(**kw: object) -> User:
    """Transient User carrying just the billing fields the gate reads."""
    base: dict[str, object] = {
        "email": "u@x",
        "password_hash": "p",
        "is_active": True,
    }
    base.update(kw)
    return User(**base)


def _set_flag(monkeypatch: pytest.MonkeyPatch, *, on: bool) -> None:
    """Point the entitlements module's settings reader at a stub flag."""
    monkeypatch.setattr(ent, "get_settings", lambda: SimpleNamespace(paywall_enforced=on))


# ── 1. Flag OFF ⇒ pass-through for every status ───────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("plan_status", ["none", "active", "expired", "cancelled"])
async def test_flag_off_is_passthrough_for_every_status(
    monkeypatch: pytest.MonkeyPatch, plan_status: str
) -> None:
    _set_flag(monkeypatch, on=False)
    user = _user(plan_status=plan_status, plan_expires_at=_PAST)
    assert await require_active_plan(user) is user


# ── 2. Flag ON ⇒ only active + non-expired is granted ─────────────────


@pytest.mark.asyncio
async def test_flag_on_active_no_expiry_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_flag(monkeypatch, on=True)
    user = _user(plan_status="active", plan_expires_at=None)
    assert await require_active_plan(user) is user


@pytest.mark.asyncio
async def test_flag_on_active_future_expiry_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_flag(monkeypatch, on=True)
    user = _user(plan_status="active", plan_expires_at=_FUTURE)
    assert await require_active_plan(user) is user


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("plan_status", "plan_expires_at"),
    [
        ("none", None),
        ("cancelled", None),
        ("expired", None),
        ("active", _PAST),  # lapsed expiry ⇒ expired-treated-free
        ("active", datetime.now(UTC) - timedelta(seconds=1)),
    ],
)
async def test_flag_on_non_entitled_is_blocked(
    monkeypatch: pytest.MonkeyPatch, plan_status: str, plan_expires_at: datetime | None
) -> None:
    _set_flag(monkeypatch, on=True)
    user = _user(plan_status=plan_status, plan_expires_at=plan_expires_at)
    with pytest.raises(HTTPException) as excinfo:
        await require_active_plan(user)
    assert excinfo.value.status_code == PAYWALL_STATUS_CODE == 402
    assert isinstance(excinfo.value.detail, dict)
    assert excinfo.value.detail["code"] == PLAN_REQUIRED_CODE == "PLAN_REQUIRED"
    assert excinfo.value.detail["upgrade_url"] == "/pricing"


# ── 3. Billing ⟂ RBAC — role / live_trading never decide premium ──────


@pytest.mark.asyncio
async def test_admin_with_no_plan_is_still_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """role=admin + live_trading_enabled=True but plan_status='none' ⇒ blocked.
    Proves the gate ignores RBAC / live-trading and reads plan only."""
    _set_flag(monkeypatch, on=True)
    user = _user(
        plan_status="none",
        role="admin",
        is_admin=True,
        live_trading_enabled=True,
    )
    with pytest.raises(HTTPException) as excinfo:
        await require_active_plan(user)
    assert excinfo.value.status_code == 402


@pytest.mark.asyncio
async def test_plain_user_with_active_plan_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """role=user + live_trading_enabled=False but plan_status='active' ⇒ passes.
    Premium is driven by the plan, not the role/live flag."""
    _set_flag(monkeypatch, on=True)
    user = _user(
        plan_status="active",
        plan_expires_at=_FUTURE,
        role="user",
        is_admin=False,
        live_trading_enabled=False,
    )
    assert await require_active_plan(user) is user


# ── 4. UserResponse surfaces the new fields without breaking /me ──────


def test_user_response_defaults_to_free_tier() -> None:
    """Direct construction: a profile with no billing fields set serialises
    as free-tier (status 'none', tier None, no expiry)."""
    resp = UserResponse(
        id=uuid.uuid4(),
        email="free@x",
        full_name=None,
        phone=None,
        is_active=True,
        is_admin=False,
        created_at=datetime.now(UTC),
    )
    assert resp.plan_status == "none"
    assert resp.plan_tier is None
    assert resp.plan_expires_at is None


def test_user_response_coerces_null_plan_status() -> None:
    """A NULL plan_status (e.g. a pre-flush ORM object) coerces to 'none'
    rather than tripping str validation — so /me never 500s."""
    resp = UserResponse(
        id=uuid.uuid4(),
        email="null@x",
        full_name=None,
        phone=None,
        is_active=True,
        is_admin=False,
        created_at=datetime.now(UTC),
        plan_status=None,  # type: ignore[arg-type]
    )
    assert resp.plan_status == "none"


def test_user_response_carries_active_plan_fields() -> None:
    resp = UserResponse(
        id=uuid.uuid4(),
        email="pro@x",
        full_name=None,
        phone=None,
        is_active=True,
        is_admin=False,
        created_at=datetime.now(UTC),
        plan_status="active",
        plan_tier="pro",
        plan_expires_at=_FUTURE,
    )
    assert resp.plan_status == "active"
    assert resp.plan_tier == "pro"
    assert resp.plan_expires_at == _FUTURE


# ── 5. Inert + contract guarantees ────────────────────────────────────


def test_require_active_plan_is_async_callable() -> None:
    import inspect

    assert inspect.iscoroutinefunction(require_active_plan)


def test_plan_tier_property_is_lazy_load_safe_on_transient_user() -> None:
    """``User.plan_tier`` must return None (not raise / not lazy-load) when
    ``active_plan`` is unloaded — the property the /me path relies on."""
    assert _user(plan_status="active").plan_tier is None
