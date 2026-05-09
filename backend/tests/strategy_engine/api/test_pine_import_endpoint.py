"""Phase 7 frontend wiring — ``POST /api/strategies/pine-import``.

Self-contained: each test builds its own FastAPI app holding only the
pine-import router and overrides the auth dep. The converter itself is
pure / structural (no DB, no network), so no DB plumbing is needed.

The four cases mirror the spec's locked acceptance list (see
``prompts/master-plan-final.md`` "Pine Importer Frontend UI"):

    1. Valid ``ta.ema`` script → success=True
    2. Pine with ``request.security`` → success=False, unsupported lists it
    3. Protected script → success=False, license_status="blocked"
    4. Empty body → 422
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_user
from app.db.models.user import User
from app.strategy_engine.api.pine_import import router as pine_import_router


@pytest.fixture
def client() -> Iterator[TestClient]:
    """FastAPI app + auth override. Reset overrides on teardown so a
    parallel test importing the same router can install its own."""
    app = FastAPI()
    app.include_router(pine_import_router)

    async def _override_user() -> User:
        return User(
            id=uuid.uuid4(),
            email="pine-importer@tradetri.com",
            password_hash="x",
            is_active=True,
        )

    app.dependency_overrides[get_current_active_user] = _override_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ─── 1. Valid ta.ema script → success=True ─────────────────────────────


_VALID_PINE_EMA = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("EMA test", overlay=true)
ema_fast = ta.ema(close, 9)
ema_slow = ta.ema(close, 21)
buy_signal = ta.crossover(ema_fast, ema_slow)
if buy_signal
    strategy.entry("Long", strategy.long)
"""


def test_valid_ta_ema_script_returns_success_true(client: TestClient) -> None:
    resp = client.post("/api/strategies/pine-import", json={"pine_source": _VALID_PINE_EMA})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert "strategy" in body
    indicators = body["strategy"]["indicators"]
    by_id = {ind["id"]: ind for ind in indicators}
    assert "ema_fast" in by_id
    assert by_id["ema_fast"]["type"] == "ema"
    assert by_id["ema_fast"]["params"]["period"] == 9
    assert body["license_status"] in {"permissive", "compliance_required", "needs_review"}


# ─── 2. request.security → success=False, unsupported lists it ────────


_PINE_REQUEST_SECURITY = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Multi-symbol")
htf_close = request.security(syminfo.tickerid, "60", close)
ema_value = ta.ema(htf_close, 14)
"""


def test_request_security_returns_failure_with_unsupported_listed(
    client: TestClient,
) -> None:
    resp = client.post(
        "/api/strategies/pine-import",
        json={"pine_source": _PINE_REQUEST_SECURITY},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is False
    assert any("request.security" in u for u in body["unsupported"])
    assert "request.security" in body["message"]


# ─── 3. Protected script → success=False, license_status="blocked" ────


_PINE_PROTECTED = """\
//@version=5
// @license invite-only
strategy("Secret strategy")
ema_fast = ta.ema(close, 9)
"""


def test_protected_script_blocked_with_license_status_blocked(
    client: TestClient,
) -> None:
    resp = client.post(
        "/api/strategies/pine-import",
        json={"pine_source": _PINE_PROTECTED},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["license_status"] == "blocked"


# ─── 4. Empty body → 422 ──────────────────────────────────────────────


def test_empty_body_returns_422(client: TestClient) -> None:
    """Missing ``pine_source`` is a Pydantic validation failure — the
    request never reaches the converter, no logging happens."""
    resp = client.post("/api/strategies/pine-import", json={})
    assert resp.status_code == 422


# ─── Audit emission — pin the Phase 11 wiring ────────────────────────


def test_pine_import_emits_pine_import_audit_event() -> None:
    """A pine-import request emits a ``pine_import`` audit event
    with success + license_status metadata. Builds its own
    TestClient so the user id can be captured for the event query
    (the shared ``client`` fixture mints an anonymous user inline)."""
    from app.strategy_engine.audit import clear_audit_log, query_events

    clear_audit_log()

    captured_user = User(
        id=uuid.uuid4(),
        email="pine-audit@tradetri.com",
        password_hash="x",
        is_active=True,
    )

    app = FastAPI()
    app.include_router(pine_import_router)

    async def _override_user() -> User:
        return captured_user

    app.dependency_overrides[get_current_active_user] = _override_user
    try:
        with TestClient(app) as c:
            resp = c.post(
                "/api/strategies/pine-import",
                json={"pine_source": _VALID_PINE_EMA},
            )
        assert resp.status_code == 200, resp.text

        events = query_events(
            user_id=captured_user.id,
            event_type="pine_import",
        )
        assert events.filtered_count >= 1
        meta = events.events[-1].metadata
        assert "success" in meta
        assert "license_status" in meta
    finally:
        app.dependency_overrides.clear()
