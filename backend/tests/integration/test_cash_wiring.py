"""CASH Module B — cash executor wired into signal_execution's seams.

Test-FIRST. Contract (mirror of options Module B):
  * CASH flag OFF → seam behaves BYTE-IDENTICALLY to today (same skip note),
    cash executor never invoked;
  * flag ON + paper cash strategy → execute_cash_entry/exit through the REAL
    worker path;
  * flag ON + live → executor refuse path;
  * FUTURES and OPTIONS routing untouched — including CROSS-FLAG isolation
    (cash flag must not leak into options routing and vice versa).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal

from tests.integration.conftest import HMAC_HEADER, _sign

_SKIP_NOTE = "options execution not yet implemented — skipped"  # instrument-interpolated
_CASH_SKIP_NOTE = "cash execution not yet implemented — skipped"


def _await(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_cash_strategy(db_session_maker, seed, *, is_paper: bool,
                        entry_shares: int = 4) -> None:
    async def _upd():
        async with db_session_maker() as s:
            strat = await s.get(Strategy, seed["strategy_id"])
            strat.strategy_json = {"instrument_type": "cash",
                                   "entry_shares": entry_shares}
            strat.is_paper = is_paper
            strat.allowed_symbols = ["RELIANCE"]
            await s.commit()

    _await(_upd())


def _make_options_strategy(db_session_maker, seed) -> None:
    async def _upd():
        async with db_session_maker() as s:
            strat = await s.get(Strategy, seed["strategy_id"])
            strat.strategy_json = {"options": {
                "option_type": "auto",
                "strike_selection": {"method": "ATM", "offset": 0},
                "expiry": "current_week", "premium_budget_per_lot": 18000,
                "product_type": "NRML", "carry_forward": True,
                "expiry_day_force_close": True, "no_intraday_squareoff": True}}
            strat.is_paper = True
            strat.allowed_symbols = ["NSE:BSE"]
            await s.commit()

    _await(_upd())


def _post(client: TestClient, token: str, body: dict) -> Any:
    raw = json.dumps(body).encode()
    return client.post(f"/api/webhook/strategy/{token}", content=raw,
                       headers={HMAC_HEADER: _sign(raw),
                                "Content-Type": "application/json"})


def _entry_body(symbol: str = "RELIANCE", **over: Any) -> dict:
    body = {"action": "BUY", "symbol": symbol, "quantity": 1,
            "order_type": "market", "price": 2885.0,
            "timestamp": f"2026-07-14T09:20:00.{uuid.uuid4().int % 10**6:06d}+00:00"}
    body.update(over)
    return body


def _exit_body(action: str, **over: Any) -> dict:
    body = {"action": action, "side": "long", "symbol": "RELIANCE",
            "order_type": "market", "signal_id": str(uuid.uuid4()),
            "price": 2985.0}
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
def cash_flag_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "cash_execution_enabled", True)


@pytest.fixture
def options_flag_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "options_execution_enabled", True)


# ═══════════════════════════════════════════════════════════════════════
# (a) flag OFF — byte-identical skip, executor never invoked
# ═══════════════════════════════════════════════════════════════════════


def test_cash_flag_off_entry_skips_exactly_like_today(
    client: TestClient, seed, db_session_maker, monkeypatch
):
    assert get_settings().cash_execution_enabled is False
    _make_cash_strategy(db_session_maker, seed, is_paper=True)
    spy = AsyncMock(name="execute_cash_entry")
    monkeypatch.setattr("app.services.cash_executor.execute_cash_entry", spy)

    resp = _post(client, seed["token_plain"], _entry_body())
    assert resp.status_code == 202, resp.text
    sig = _sig(db_session_maker, resp.json()["signal_id"])
    assert sig.status == "skipped"
    assert sig.notes == _CASH_SKIP_NOTE                # today's note, byte-identical
    spy.assert_not_called()
    assert _positions(db_session_maker, seed["strategy_id"]) == []


# ═══════════════════════════════════════════════════════════════════════
# (b) flag ON + paper — real path
# ═══════════════════════════════════════════════════════════════════════


def test_cash_flag_on_paper_entry_executes(
    client: TestClient, seed, db_session_maker, cash_flag_on, monkeypatch
):
    _make_cash_strategy(db_session_maker, seed, is_paper=True, entry_shares=4)

    calls: list[dict] = []
    from app.services import cash_executor as CE
    real = CE.execute_cash_entry

    async def _wrapped(session, **kw):
        calls.append({"strategy_id": kw["strategy"].id,
                      "signal_id": kw["signal"].id})
        return await real(session, **kw)

    monkeypatch.setattr("app.services.cash_executor.execute_cash_entry", _wrapped)

    resp = _post(client, seed["token_plain"], _entry_body())
    assert resp.status_code == 202, resp.text
    sig = _sig(db_session_maker, resp.json()["signal_id"])
    assert sig.status == "executed", sig.notes

    assert len(calls) == 1
    assert calls[0]["strategy_id"] == seed["strategy_id"]
    assert calls[0]["signal_id"] == uuid.UUID(resp.json()["signal_id"])

    rows = _positions(db_session_maker, seed["strategy_id"])
    assert len(rows) == 1
    assert rows[0].symbol == "RELIANCE"                # AS-IS
    assert rows[0].total_quantity == 4                 # SHARES


# ═══════════════════════════════════════════════════════════════════════
# (c) flag ON + LIVE — refuse (worker-direct; live POSTs market-hours gated)
# ═══════════════════════════════════════════════════════════════════════


def test_cash_flag_on_live_strategy_refused(
    client: TestClient, seed, db_session_maker, cash_flag_on
):
    _make_cash_strategy(db_session_maker, seed, is_paper=False)

    async def _seed_signal():
        async with db_session_maker() as s:
            sig = StrategySignal(
                id=uuid.uuid4(), user_id=seed["user_id"],
                strategy_id=seed["strategy_id"], symbol="RELIANCE",
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
# (d) exit kinds — execute_cash_exit per kind
# ═══════════════════════════════════════════════════════════════════════


def test_cash_exit_kinds_route(
    client: TestClient, seed, db_session_maker, cash_flag_on, monkeypatch
):
    _make_cash_strategy(db_session_maker, seed, is_paper=True, entry_shares=8)

    kinds: list[str] = []
    from app.services import cash_executor as CE
    real_exit = CE.execute_cash_exit

    async def _wrapped(session, **kw):
        kinds.append(kw["action_kind"])
        return await real_exit(session, **kw)

    monkeypatch.setattr("app.services.cash_executor.execute_cash_exit", _wrapped)

    entry = _post(client, seed["token_plain"], _entry_body())
    assert _sig(db_session_maker, entry.json()["signal_id"]).status == "executed"

    r_partial = _post(client, seed["token_plain"], _exit_body("PARTIAL", closePct=50))
    r_exit = _post(client, seed["token_plain"], _exit_body("EXIT"))
    r_sl = _post(client, seed["token_plain"], _exit_body("SL_HIT"))
    for r in (r_partial, r_exit, r_sl):
        assert r.status_code == 202, r.text

    assert kinds == ["partial", "exit", "sl_hit"]
    pos = _positions(db_session_maker, seed["strategy_id"])[0]
    assert pos.status == "closed"
    assert pos.remaining_quantity == 0
    assert pos.symbol == "RELIANCE"                    # stored symbol
    assert _sig(db_session_maker, r_sl.json()["signal_id"]).status == "ignored"


# ═══════════════════════════════════════════════════════════════════════
# (e) futures + cash flag ON — cash code untouched
# ═══════════════════════════════════════════════════════════════════════


def test_futures_entry_with_cash_flag_on_untouched(
    client: TestClient, seed, db_session_maker, cash_flag_on, monkeypatch
):
    # seed strategy stays FUTURES (strategy_json None)
    entry_spy = AsyncMock(name="execute_cash_entry")
    exit_spy = AsyncMock(name="execute_cash_exit")
    monkeypatch.setattr("app.services.cash_executor.execute_cash_entry", entry_spy)
    monkeypatch.setattr("app.services.cash_executor.execute_cash_exit", exit_spy)

    body = {"action": "BUY", "symbol": "NIFTY", "quantity": 1,
            "order_type": "market", "price": 22500.0}
    resp = _post(client, seed["token_plain"], body)
    assert resp.status_code == 202, resp.text
    sig = _sig(db_session_maker, resp.json()["signal_id"])
    assert sig.status == "executed", sig.notes         # futures paper path
    entry_spy.assert_not_called()
    exit_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# (f) CROSS-FLAG ISOLATION — neither flag leaks into the other's routing
# ═══════════════════════════════════════════════════════════════════════


def test_options_signal_with_cash_flag_on_still_skips(
    client: TestClient, seed, db_session_maker, cash_flag_on, monkeypatch
):
    """OPTIONS strategy + CASH flag ON + options flag OFF → options skip
    unchanged; NEITHER executor invoked."""
    assert get_settings().options_execution_enabled is False
    _make_options_strategy(db_session_maker, seed)
    opt_spy = AsyncMock(name="execute_options_entry")
    cash_spy = AsyncMock(name="execute_cash_entry")
    monkeypatch.setattr("app.services.options_executor.execute_options_entry", opt_spy)
    monkeypatch.setattr("app.services.cash_executor.execute_cash_entry", cash_spy)

    resp = _post(client, seed["token_plain"],
                 _entry_body(symbol="NSE:BSE",
                             signal_direction="LONG_ENTRY", spot_price="2437"))
    assert resp.status_code == 202, resp.text
    sig = _sig(db_session_maker, resp.json()["signal_id"])
    assert sig.status == "skipped"
    assert sig.notes == _SKIP_NOTE                     # options note, unchanged
    opt_spy.assert_not_called()
    cash_spy.assert_not_called()


def test_cash_signal_with_options_flag_on_still_skips(
    client: TestClient, seed, db_session_maker, options_flag_on, monkeypatch
):
    """CASH strategy + OPTIONS flag ON + cash flag OFF → cash skip unchanged;
    NEITHER executor invoked."""
    assert get_settings().cash_execution_enabled is False
    _make_cash_strategy(db_session_maker, seed, is_paper=True)
    opt_spy = AsyncMock(name="execute_options_entry")
    cash_spy = AsyncMock(name="execute_cash_entry")
    monkeypatch.setattr("app.services.options_executor.execute_options_entry", opt_spy)
    monkeypatch.setattr("app.services.cash_executor.execute_cash_entry", cash_spy)

    resp = _post(client, seed["token_plain"], _entry_body())
    assert resp.status_code == 202, resp.text
    sig = _sig(db_session_maker, resp.json()["signal_id"])
    assert sig.status == "skipped"
    assert sig.notes == _CASH_SKIP_NOTE
    opt_spy.assert_not_called()
    cash_spy.assert_not_called()
