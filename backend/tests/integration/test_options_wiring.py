"""Brick #3 Module B — options executor wired into signal_execution's seams.

Test-FIRST for the live-path wiring. Contract:
  * flag OFF → the seam behaves BYTE-IDENTICALLY to today (same skip note),
    and the options executor is never invoked;
  * flag ON + paper options strategy → execute_options_entry/exit run through
    the REAL _process_entry/_process_direct_exit path;
  * flag ON + live options strategy → executor's refuse path (no order);
  * FUTURES strategies never touch options code, flag ON or OFF.

Runs on the integration harness (aiosqlite + fakeredis + eager Celery).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.brokers.dhan import ScripMeta
from app.core.config import get_settings
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal

from tests.integration.conftest import HMAC_HEADER, _sign

_NRML_OPTIONS: dict[str, Any] = {
    "option_type": "auto",
    "strike_selection": {"method": "ATM", "offset": 0},
    "expiry": "current_week",
    "premium_budget_per_lot": 18000,
    "product_type": "NRML",
    "carry_forward": True,
    "expiry_day_force_close": True,
    "no_intraday_squareoff": True,
}

_EXPIRY = date.today() + timedelta(days=5)
_SKIP_NOTE = "options execution not yet implemented — skipped"


class _FakeScripMaster:
    def __init__(self, *metas: ScripMeta) -> None:
        self._meta = {m.security_id: m for m in metas}

    def lot_size(self, security_id: str) -> int | None:
        m = self._meta.get(security_id)
        return m.lot_size if m else None


def _fake_master() -> _FakeScripMaster:
    return _FakeScripMaster(
        ScripMeta(
            security_id="44321",
            symbol=f"BSE-{_EXPIRY:%d%b%Y}-2400-CE".upper(),
            segment="NSE_FNO", instrument="OPTSTK", lot_size=375,
            option_type="CE", strike_price=Decimal("2400"), expiry_date=_EXPIRY,
        ),
        ScripMeta(
            security_id="44322",
            symbol=f"BSE-{_EXPIRY:%d%b%Y}-2400-PE".upper(),
            segment="NSE_FNO", instrument="OPTSTK", lot_size=375,
            option_type="PE", strike_price=Decimal("2400"), expiry_date=_EXPIRY,
        ),
    )


def _await(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_options_strategy(db_session_maker, seed, *, is_paper: bool) -> None:
    async def _upd():
        async with db_session_maker() as s:
            strat = await s.get(Strategy, seed["strategy_id"])
            strat.strategy_json = {"options": _NRML_OPTIONS}
            strat.is_paper = is_paper
            strat.allowed_symbols = ["NSE:BSE"]
            await s.commit()

    _await(_upd())


def _post(client: TestClient, token: str, body: dict) -> Any:
    raw = json.dumps(body).encode()
    return client.post(f"/api/webhook/strategy/{token}", content=raw,
                       headers={HMAC_HEADER: _sign(raw),
                                "Content-Type": "application/json"})


def _entry_body(**over: Any) -> dict:
    # signal_direction (not "type") so the webhook's Pine detector does NOT
    # fire — native payload passes through with the options keys intact, and
    # map_pine_to_option_order honours signal_direction as the override.
    body = {"action": "BUY", "symbol": "NSE:BSE", "quantity": 1,
            "order_type": "market", "price": 180.0,
            "signal_direction": "LONG_ENTRY", "spot_price": "2437",
            "timestamp": f"2026-07-13T09:20:00.{uuid.uuid4().int % 10**6:06d}+00:00"}
    body.update(over)
    return body


def _exit_body(action: str, signal_id: str | None = None, **over: Any) -> dict:
    # unique signal_id per request: the webhook's layer-1 idempotency key is
    # {user_id}:{signal_id} when present — reusing one id would (correctly)
    # suppress the later exits as duplicates before they reach the seam.
    body = {"action": action, "side": "long", "symbol": "NSE:BSE",
            "order_type": "market", "signal_id": signal_id or str(uuid.uuid4()),
            "price": 210.0}
    body.update(over)
    return body


def _sig(db_session_maker, signal_id) -> StrategySignal | None:
    async def _load():
        async with db_session_maker() as s:
            return await s.get(StrategySignal, uuid.UUID(str(signal_id)))

    return _await(_load())


def _positions(db_session_maker, strategy_id) -> list[StrategyPosition]:
    async def _load():
        async with db_session_maker() as s:
            return list((await s.execute(
                select(StrategyPosition)
                .where(StrategyPosition.strategy_id == strategy_id))).scalars())

    return _await(_load())


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "options_execution_enabled", True)


@pytest.fixture
def fake_master(monkeypatch):
    """The mapper's default scrip master → fake option chain."""
    import app.brokers.dhan as dhan_mod

    master = _fake_master()
    monkeypatch.setattr(dhan_mod, "_SCRIP_MASTER", master)
    return master


# ═══════════════════════════════════════════════════════════════════════
# (a) flag OFF — byte-identical skip, executor never invoked
# ═══════════════════════════════════════════════════════════════════════


def test_flag_off_entry_skips_exactly_like_today(
    client: TestClient, seed, db_session_maker, monkeypatch
):
    assert get_settings().options_execution_enabled is False
    _make_options_strategy(db_session_maker, seed, is_paper=True)
    spy = AsyncMock(name="execute_options_entry")
    monkeypatch.setattr(
        "app.services.options_executor.execute_options_entry", spy)

    resp = _post(client, seed["token_plain"], _entry_body())
    assert resp.status_code == 202, resp.text
    sig = _sig(db_session_maker, resp.json()["signal_id"])
    assert sig.status == "skipped"
    assert sig.notes == _SKIP_NOTE          # today's note, byte-identical
    spy.assert_not_called()
    assert _positions(db_session_maker, seed["strategy_id"]) == []


# ═══════════════════════════════════════════════════════════════════════
# (b) flag ON + paper — real path, position row
# ═══════════════════════════════════════════════════════════════════════


def test_flag_on_paper_entry_executes_through_real_path(
    client: TestClient, seed, db_session_maker, flag_on, fake_master, monkeypatch
):
    _make_options_strategy(db_session_maker, seed, is_paper=True)

    calls: list[dict] = []
    from app.services import options_executor as OE
    real = OE.execute_options_entry

    async def _wrapped(session, **kw):
        calls.append({"strategy_id": kw["strategy"].id,
                      "signal_id": kw["signal"].id})
        return await real(session, **kw)

    monkeypatch.setattr(
        "app.services.options_executor.execute_options_entry", _wrapped)

    resp = _post(client, seed["token_plain"], _entry_body())
    assert resp.status_code == 202, resp.text
    sig = _sig(db_session_maker, resp.json()["signal_id"])
    assert sig.status == "executed", sig.notes

    assert len(calls) == 1                              # called once
    assert calls[0]["strategy_id"] == seed["strategy_id"]
    assert calls[0]["signal_id"] == uuid.UUID(resp.json()["signal_id"])

    rows = _positions(db_session_maker, seed["strategy_id"])
    assert len(rows) == 1
    assert rows[0].symbol == f"BSE-{_EXPIRY:%d%b%Y}-2400-CE".upper()
    assert rows[0].total_quantity == 1 * 375            # seed entry_lots=1


# ═══════════════════════════════════════════════════════════════════════
# (c) flag ON + LIVE strategy — refuse path (worker-direct; live webhook
#     POSTs are market-hours gated, the worker path is what Module B wires)
# ═══════════════════════════════════════════════════════════════════════


def test_flag_on_live_strategy_refused(
    client: TestClient, seed, db_session_maker, flag_on, fake_master
):
    _make_options_strategy(db_session_maker, seed, is_paper=False)

    async def _seed_signal():
        async with db_session_maker() as s:
            sig = StrategySignal(
                id=uuid.uuid4(), user_id=seed["user_id"],
                strategy_id=seed["strategy_id"], symbol="NSE:BSE",
                action="ENTRY", quantity=1, order_type="market",
                status="pending", raw_payload=_entry_body(),
                received_at=datetime.now(UTC))
            s.add(sig)
            await s.commit()
            return sig.id

    sid = _await(_seed_signal())
    from app.tasks import signal_execution as SE
    _await(SE._process_entry(str(sid)))

    sig = _sig(db_session_maker, sid)
    assert sig.status == "skipped"
    assert "paper-only" in (sig.notes or "")
    assert _positions(db_session_maker, seed["strategy_id"]) == []


# ═══════════════════════════════════════════════════════════════════════
# (d) exit kinds — execute_options_exit per kind
# ═══════════════════════════════════════════════════════════════════════


def test_exit_kinds_route_to_options_exit(
    client: TestClient, seed, db_session_maker, flag_on, fake_master, monkeypatch
):
    _make_options_strategy(db_session_maker, seed, is_paper=True)

    kinds: list[str] = []
    from app.services import options_executor as OE
    real_exit = OE.execute_options_exit

    async def _wrapped(session, **kw):
        kinds.append(kw["action_kind"])
        return await real_exit(session, **kw)

    monkeypatch.setattr(
        "app.services.options_executor.execute_options_exit", _wrapped)

    entry = _post(client, seed["token_plain"], _entry_body())
    entry_id = entry.json()["signal_id"]
    assert _sig(db_session_maker, entry_id).status == "executed"

    r_partial = _post(client, seed["token_plain"],
                      _exit_body("PARTIAL", closePct=50))
    r_exit = _post(client, seed["token_plain"], _exit_body("EXIT"))
    r_sl = _post(client, seed["token_plain"], _exit_body("SL_HIT"))
    for r in (r_partial, r_exit, r_sl):
        assert r.status_code == 202, r.text

    assert kinds == ["partial", "exit", "sl_hit"]

    pos = _positions(db_session_maker, seed["strategy_id"])[0]
    assert pos.status == "closed"
    assert pos.remaining_quantity == 0
    assert pos.symbol.endswith("-CE")                   # stored leg symbol

    # after full close, SL_HIT was a no-op → its signal is 'ignored'
    assert _sig(db_session_maker, r_sl.json()["signal_id"]).status == "ignored"


# ═══════════════════════════════════════════════════════════════════════
# (e) futures + flag ON — options code untouched
# ═══════════════════════════════════════════════════════════════════════


def test_futures_entry_with_flag_on_never_touches_options(
    client: TestClient, seed, db_session_maker, flag_on, monkeypatch
):
    # seed strategy stays FUTURES (strategy_json None) — do not convert
    entry_spy = AsyncMock(name="execute_options_entry")
    exit_spy = AsyncMock(name="execute_options_exit")
    monkeypatch.setattr(
        "app.services.options_executor.execute_options_entry", entry_spy)
    monkeypatch.setattr(
        "app.services.options_executor.execute_options_exit", exit_spy)

    body = {"action": "BUY", "symbol": "NIFTY", "quantity": 1,
            "order_type": "market", "price": 22500.0}
    resp = _post(client, seed["token_plain"], body)
    assert resp.status_code == 202, resp.text
    sig = _sig(db_session_maker, resp.json()["signal_id"])
    assert sig.status == "executed", sig.notes          # futures paper path
    entry_spy.assert_not_called()
    exit_spy.assert_not_called()
