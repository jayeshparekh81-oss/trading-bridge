"""Per-tier strategy quota (Stage 2a) — inert while ``paywall_enforced`` is False."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

import app.auth.entitlements as ent
import app.auth.plan_limits as pl
from app.auth.plan_limits import (
    FREE_STRATEGY_LIMIT,
    cap_from_feature_limits,
    enforce_strategy_quota,
    strategy_cap_for,
)


def _user(**over: Any) -> SimpleNamespace:
    base = dict(
        id=uuid.uuid4(),
        plan_status="none",
        plan_expires_at=None,
        active_plan_id=None,
        paywall_grace_until=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


class _Session:
    """Counts executes/commits; returns a fixed strategy count and plan."""

    def __init__(self, count: int = 0, plan: Any = None) -> None:
        self.count, self.plan, self.executes, self.commits = count, plan, 0, 0

    async def execute(self, _stmt: Any) -> Any:
        self.executes += 1
        n = self.count

        class R:
            def scalar_one(self_inner) -> int:
                return n

        return R()

    async def get(self, _model: Any, _id: Any) -> Any:
        return self.plan

    async def commit(self) -> None:
        self.commits += 1


def _settings(monkeypatch: pytest.MonkeyPatch, *, on: bool, grace_days: int = 14) -> None:
    ns = SimpleNamespace(paywall_enforced=on, paywall_grace_days=grace_days)
    monkeypatch.setattr(ent, "get_settings", lambda: ns)
    monkeypatch.setattr(pl, "get_settings", lambda: ns)


# ── feature_limits parsing: 1 / 3 / "all" (a STRING) ─────────────────


def test_cap_parsing_matches_live_tier_values() -> None:
    assert cap_from_feature_limits({"strategies": 1}) == 1
    assert cap_from_feature_limits({"strategies": 3}) == 3
    assert cap_from_feature_limits({"strategies": "all"}) is None  # premium → unlimited
    assert cap_from_feature_limits({"strategies": True}) is None
    assert cap_from_feature_limits({"strategies": 0}) is None  # never lock out on a bad value
    assert cap_from_feature_limits(None) is None
    assert cap_from_feature_limits({}) is None


# ── flag OFF: nothing changes for anyone, not even a query ────────────


@pytest.mark.asyncio
async def test_flag_off_is_a_no_op_with_no_db_access(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, on=False)
    db = _Session(count=999)
    await enforce_strategy_quota(db, _user())  # type: ignore[arg-type]
    assert db.executes == 0 and db.commits == 0


# ── flag ON ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_free_user_outside_grace_is_capped_at_free_limit_with_upgrade_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _settings(monkeypatch, on=True, grace_days=0)  # no grace → free limit applies
    db = _Session(count=FREE_STRATEGY_LIMIT)
    with pytest.raises(HTTPException) as exc:
        await enforce_strategy_quota(db, _user())  # type: ignore[arg-type]
    assert exc.value.status_code == 402
    body = exc.value.detail
    assert body["code"] == "PLAN_REQUIRED" and body["upgrade_url"] == "/pricing"
    assert body["limit"] == FREE_STRATEGY_LIMIT and body["used"] == FREE_STRATEGY_LIMIT
    assert "Upgrade" in body["message"] or "upgrade" in body["message"].lower()


@pytest.mark.asyncio
async def test_free_user_in_grace_has_no_cap_and_clock_starts_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _settings(monkeypatch, on=True, grace_days=14)
    user = _user()
    db = _Session(count=50)
    await enforce_strategy_quota(db, user)  # type: ignore[arg-type]  # no raise: full access during grace
    assert user.paywall_grace_until is not None and db.commits == 1
    first = user.paywall_grace_until
    await enforce_strategy_quota(db, user)  # type: ignore[arg-type]
    assert user.paywall_grace_until == first and db.commits == 1  # never extended


@pytest.mark.asyncio
async def test_expired_grace_falls_back_to_free_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, on=True)
    user = _user(paywall_grace_until=datetime.now(UTC) - timedelta(seconds=1))
    assert await strategy_cap_for(_Session(), user) == FREE_STRATEGY_LIMIT  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limits", "used", "blocked"),
    [
        ({"strategies": 1}, 0, False),
        ({"strategies": 1}, 1, True),
        ({"strategies": 3}, 2, False),
        ({"strategies": 3}, 3, True),
        ({"strategies": "all"}, 500, False),
    ],
)
async def test_active_plan_caps_follow_feature_limits(
    monkeypatch: pytest.MonkeyPatch, limits: dict, used: int, blocked: bool
) -> None:
    _settings(monkeypatch, on=True)
    plan = SimpleNamespace(feature_limits=limits)
    user = _user(plan_status="active", active_plan_id=uuid.uuid4())
    db = _Session(count=used, plan=plan)
    if blocked:
        with pytest.raises(HTTPException) as exc:
            await enforce_strategy_quota(db, user)  # type: ignore[arg-type]
        assert exc.value.status_code == 402
    else:
        await enforce_strategy_quota(db, user)  # type: ignore[arg-type]


# ── all three creation paths call the quota, before any write ─────────


def test_all_three_creation_paths_are_gated() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "app"
    for rel, fn in [
        ("strategy_engine/api/strategies.py", "async def create_strategy"),
        ("api/users.py", "async def create_strategy"),
        ("templates/api.py", "async def clone_route"),
    ]:
        src = (root / rel).read_text()
        body = src[src.index(fn) :]
        assert "await enforce_strategy_quota(db," in body[:1800], rel
        # the quota check precedes the first db.add / clone
        assert (
            body.index("await enforce_strategy_quota(db,") < body.index("db.add(")
            if "db.add(" in body[:2500]
            else True
        ), rel


@pytest.mark.asyncio
async def test_active_plan_without_linked_plan_row_is_unlimited_fail_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """plan_status='active' but active_plan_id NULL (razorpay plan_id SET NULL) → never capped at the free limit."""
    _settings(monkeypatch, on=True)
    user = _user(plan_status="active", active_plan_id=None)
    assert await strategy_cap_for(_Session(), user) is None  # type: ignore[arg-type]
    user2 = _user(plan_status="active", active_plan_id=uuid.uuid4())
    assert (
        await strategy_cap_for(_Session(plan=None), user2) is None
    )  # deleted plan row → unlimited
