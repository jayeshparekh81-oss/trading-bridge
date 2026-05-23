"""Async-contract tests for ``POST /api/webhook/strategy/{token}`` — Bug #2 (Phase 2C).

These pin the two-phase async behaviour that ALREADY ships on ``main``
(foundational commit ``cda3cb6`` + the 2026-05-20 fix series). The earlier
``feat/webhook-async-refactor`` branch implemented Bug #2 with a Celery
worker; ``main`` instead uses FastAPI ``BackgroundTasks`` (the approach the
Phase 2C work-order now mandates — Celery worker is unhealthy per CLAUDE.md
§2). See ``WEBHOOK_ASYNC_NOTES.md`` at the repo root.

    Phase 1 (sync)       — auth → rate-limit → HMAC → idempotency claim →
                           persist ``StrategySignal`` (status='received') →
                           ``background.add_task`` → return 202.
    Phase 2 (background) — ``_process_signal_in_background`` runs AI-validate
                           → ``place_strategy_orders`` in its own DB session.

Everything below exercises the REAL handler (``app.main.create_app``) and
the REAL background coroutine via the shared integration harness
(aiosqlite + fakeredis, paper mode). Only the broker boundary
(``place_strategy_orders``) is faked, mirroring the ``_FakeBroker`` pattern
from the test-debt PR — never the handler under test.

The live BSE-LTD 89423ecc execution path is NOT modified by this branch.

Status vocabulary note: ``StrategySignal.status`` is a free ``String(32)``
(no DB enum/CHECK). ``main`` writes the *documented* lifecycle values —
``received | validating | executing | executed | rejected | failed`` — so
the work-order's ``queued``/``completed`` map onto ``received``/``executed``.
These tests assert the values ``main`` actually writes. See NOTES §enum-gap.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.ext.compiler import compiles

import app.api.strategy_webhook as webhook_mod
from app.api.strategy_webhook import _process_signal_in_background
from app.core.exceptions import BrokerError, BrokerOrderRejectedError
from app.core.signal_idempotency import (
    SIGNAL_IDEMPOTENCY_TTL_SECONDS,
    check_and_set_signal_idempotent,
    signal_idempotency_key,
)
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.schemas.broker import Exchange, ProductType
from app.services.strategy_executor import (
    ExecutionResult,
    InvalidProductTypeError,
    _resolve_product_type,
)
from app.services.telegram_alerts import AlertLevel
from tests.integration.conftest import HMAC_HEADER, _sign


# ═══════════════════════════════════════════════════════════════════════
# SQLite shim for the Postgres-only JSONB columns (pre-existing harness gap).
#
# ``app.main`` registers ``app.templates.models.StrategyTemplate`` whose
# ``config_json`` etc. use ``postgresql.JSONB``. The integration harness'
# ``Base.metadata.create_all`` runs against in-memory aiosqlite, and SQLite's
# type compiler cannot render JSONB → every ``client``-based integration test
# errors at table creation. This is environment-level (the suite is built for
# Postgres in CI, where JSONB is native) and predates this branch — see
# WEBHOOK_ASYNC_NOTES.md §blocker. Rendering JSONB as SQLite ``JSON`` (TEXT
# affinity) lets ``create_all`` succeed locally. The shim is dialect-scoped
# to "sqlite", so Postgres runs are unaffected.
# ═══════════════════════════════════════════════════════════════════════
@compiles(JSONB, "sqlite")
def _render_jsonb_as_sqlite_json(element: Any, compiler: Any, **kw: Any) -> str:
    return "JSON"


# ═══════════════════════════════════════════════════════════════════════
# Helpers — mirror the proven paper-e2e / idempotency fixtures
# ═══════════════════════════════════════════════════════════════════════


def _payload(**overrides: Any) -> bytes:
    base: dict[str, Any] = {
        "action": "BUY",
        "symbol": "NIFTY",
        "quantity": 1,
        "order_type": "market",
        "price": 22500.0,
    }
    base.update(overrides)
    return json.dumps(base).encode("utf-8")


def _url(token: str) -> str:
    return f"/api/webhook/strategy/{token}"


def _post(client: TestClient, token: str, body: bytes) -> Any:
    return client.post(
        _url(token),
        content=body,
        headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
    )


def _run(coro: Any) -> Any:
    """Drive a coroutine to completion on the test thread's loop.

    Mirrors :mod:`tests.integration.test_strategy_webhook_paper_e2e`: the
    StaticPool + shared-cache aiosqlite engine tolerates the cross-loop
    access this implies.
    """
    return asyncio.get_event_loop().run_until_complete(coro)


async def _noop_background(signal_id: str) -> None:
    """Stand-in for ``_process_signal_in_background`` so a latency / Phase-1
    test measures only the synchronous request path."""
    return None


class _AlertRecorder:
    """Async stand-in for ``telegram_alerts.send_alert`` that records calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[AlertLevel, str]] = []

    async def __call__(self, level: AlertLevel, message: str) -> None:
        self.calls.append((level, message))

    def levels(self) -> list[AlertLevel]:
        return [lvl for lvl, _ in self.calls]

    def find(self, level: AlertLevel) -> list[str]:
        return [msg for lvl, msg in self.calls if lvl == level]


def _insert_signal(
    maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    *,
    action: str = "ENTRY",
    raw_payload: dict[str, Any] | None = None,
    quantity: int | None = 1,
) -> uuid.UUID:
    """Persist a ``StrategySignal`` (status='received') the way Phase 1 would,
    so a test can drive Phase 2 (``_process_signal_in_background``) directly."""
    payload = raw_payload or {
        "action": "ENTRY",
        "symbol": "NIFTY",
        "quantity": 1,
        "side": "long",
        "order_type": "market",
        "price": 22500.0,
    }

    async def _do() -> uuid.UUID:
        async with maker() as s:
            sig = StrategySignal(
                user_id=seed["user_id"],
                strategy_id=seed["strategy_id"],
                raw_payload=payload,
                symbol=payload.get("symbol", "NIFTY"),
                action=action,
                quantity=quantity,
                order_type="market",
                status="received",
                received_at=datetime.now(UTC),
            )
            s.add(sig)
            await s.commit()
            await s.refresh(sig)
            return sig.id

    return _run(_do())


def _get_signal(maker: async_sessionmaker[AsyncSession], signal_id: uuid.UUID) -> StrategySignal:
    async def _do() -> StrategySignal:
        async with maker() as s:
            row = await s.get(StrategySignal, signal_id)
            assert row is not None, f"signal {signal_id} vanished"
            return row

    return _run(_do())


def _count_positions(maker: async_sessionmaker[AsyncSession], signal_id: uuid.UUID) -> int:
    async def _do() -> int:
        async with maker() as s:
            stmt = (
                select(func.count())
                .select_from(StrategyPosition)
                .where(StrategyPosition.signal_id == signal_id)
            )
            return int((await s.execute(stmt)).scalar_one())

    return _run(_do())


def _count_signals(maker: async_sessionmaker[AsyncSession], user_id: uuid.UUID) -> int:
    async def _do() -> int:
        async with maker() as s:
            stmt = (
                select(func.count())
                .select_from(StrategySignal)
                .where(StrategySignal.user_id == user_id)
            )
            return int((await s.execute(stmt)).scalar_one())

    return _run(_do())


# ═══════════════════════════════════════════════════════════════════════
# Phase 1 — synchronous fast path
# ═══════════════════════════════════════════════════════════════════════


class TestPhase1FastPath:
    def test_phase1_responds_under_200ms(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 1 returns 202 in well under TradingView's 5 s timeout.

        The background coroutine is stubbed to a no-op so ``perf_counter``
        measures only the synchronous request path (TestClient runs
        ``BackgroundTasks`` inline before ``.post`` returns).
        """
        monkeypatch.setattr(webhook_mod, "_process_signal_in_background", _noop_background)

        # Warm-up: prime the token cache, lazy imports, scrip-master path.
        warm = _payload(signal_id="warmup-async-latency")
        assert _post(client, seed["token_plain"], warm).status_code == 202

        body = _payload(signal_id="timed-async-latency", quantity=1)
        started = time.perf_counter()
        resp = _post(client, seed["token_plain"], body)
        elapsed = time.perf_counter() - started

        assert resp.status_code == 202, resp.text
        assert resp.json()["status"] == "accepted"
        assert elapsed < 0.2, f"Phase 1 took {elapsed * 1000:.0f}ms (budget 200ms)"

        # Phase 1 persisted the audit row; background stub left it untouched.
        signal_id = uuid.UUID(resp.json()["signal_id"])
        sig = _get_signal(db_session_maker, signal_id)
        assert sig.status == "received"

    def test_phase1_returns_signal_id_and_queued_flag(
        self, client: TestClient, seed: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The 202 body carries the signal id Phase 2 will act on."""
        monkeypatch.setattr(webhook_mod, "_process_signal_in_background", _noop_background)
        body = _payload(signal_id="contract-shape")
        resp = _post(client, seed["token_plain"], body)
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["queued_for_processing"] is True
        # signal_id must be a parseable UUID.
        uuid.UUID(data["signal_id"])


# ═══════════════════════════════════════════════════════════════════════
# Idempotency — duplicate suppression at Phase 1
# ═══════════════════════════════════════════════════════════════════════


class TestIdempotency:
    def test_duplicate_signal_id_returns_duplicate(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Same ``signal_id`` inside the window → second call short-circuits
        to 200 ``status='duplicate'`` and writes no second audit row."""
        monkeypatch.setattr(webhook_mod, "_process_signal_in_background", _noop_background)
        body = _payload(signal_id="dedupe-me-once")

        first = _post(client, seed["token_plain"], body)
        assert first.status_code == 202
        assert first.json()["status"] == "accepted"

        second = _post(client, seed["token_plain"], body)
        assert second.status_code == 200
        assert second.json()["status"] == "duplicate"

        assert _count_signals(db_session_maker, seed["user_id"]) == 1

    def test_distinct_signal_id_processes_independently(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Different ``signal_id`` → both accepted, two audit rows."""
        monkeypatch.setattr(webhook_mod, "_process_signal_in_background", _noop_background)

        first = _post(client, seed["token_plain"], _payload(signal_id="alpha"))
        second = _post(client, seed["token_plain"], _payload(signal_id="bravo"))

        assert first.status_code == 202 and first.json()["status"] == "accepted"
        assert second.status_code == 202 and second.json()["status"] == "accepted"
        assert _count_signals(db_session_maker, seed["user_id"]) == 2


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 — background outcomes (success / rejection / exception)
# ═══════════════════════════════════════════════════════════════════════


class TestBackgroundOutcomes:
    def test_background_success_marks_executed(
        self,
        client: TestClient,  # applies get_sessionmaker / redis / paper-mode patches
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A clean paper run drives ``received → executed`` and opens a
        position. (Work-order's 'completed' == ``main``'s documented
        'executed'.)"""
        recorder = _AlertRecorder()
        monkeypatch.setattr("app.services.telegram_alerts.send_alert", recorder)

        signal_id = _insert_signal(db_session_maker, seed)
        _run(_process_signal_in_background(str(signal_id)))

        sig = _get_signal(db_session_maker, signal_id)
        assert sig.status == "executed", f"notes={sig.notes!r}"
        assert _count_positions(db_session_maker, signal_id) == 1
        # Paper fill → single INFO "PAPER MODE" alert (Fix #6 taxonomy).
        info_msgs = recorder.find(AlertLevel.INFO)
        assert any("PAPER MODE" in m for m in info_msgs), recorder.calls

    def test_background_broker_rejection_marks_failed_no_phantom_position(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``BrokerOrderRejectedError`` from the executor → status='failed',
        CRITICAL alert carrying the broker reason, and ZERO positions
        (Fix #5 — executor short-circuits before the position INSERT)."""
        reason = "RED:Insufficient margin (BSE LTD)"

        async def _reject(
            session: Any, *, signal: Any, strategy: Any, recommended_lots: Any = None
        ) -> Any:
            raise BrokerOrderRejectedError("order rejected", broker_name="dhan", reason=reason)

        recorder = _AlertRecorder()
        monkeypatch.setattr("app.services.strategy_executor.place_strategy_orders", _reject)
        monkeypatch.setattr("app.services.telegram_alerts.send_alert", recorder)

        signal_id = _insert_signal(db_session_maker, seed)
        _run(_process_signal_in_background(str(signal_id)))

        sig = _get_signal(db_session_maker, signal_id)
        assert sig.status == "failed", f"notes={sig.notes!r}"
        assert "BrokerOrderRejectedError" in (sig.notes or "")
        # Phantom-position guard: rejection must not leave a tracking row.
        assert _count_positions(db_session_maker, signal_id) == 0

        critical = recorder.find(AlertLevel.CRITICAL)
        assert critical, f"expected a CRITICAL alert, got {recorder.calls}"
        assert any("BROKER REJECTED" in m and reason in m for m in critical)

    def test_background_unexpected_exception_marks_failed(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A non-broker ``Exception`` → status='failed' and a CRITICAL
        'Backend error in executor' alert (the operator-visible log)."""

        async def _boom(
            session: Any, *, signal: Any, strategy: Any, recommended_lots: Any = None
        ) -> Any:
            raise ValueError("unexpected kaboom")

        recorder = _AlertRecorder()
        monkeypatch.setattr("app.services.strategy_executor.place_strategy_orders", _boom)
        monkeypatch.setattr("app.services.telegram_alerts.send_alert", recorder)

        signal_id = _insert_signal(db_session_maker, seed)
        _run(_process_signal_in_background(str(signal_id)))

        sig = _get_signal(db_session_maker, signal_id)
        assert sig.status == "failed", f"notes={sig.notes!r}"
        assert (sig.notes or "").startswith("unexpected:")
        assert any("Backend error in executor" in m for m in recorder.find(AlertLevel.CRITICAL)), (
            recorder.calls
        )


# ═══════════════════════════════════════════════════════════════════════
# Fix #6 — status-driven Telegram taxonomy (Placed / Filled / Rejected)
# ═══════════════════════════════════════════════════════════════════════


class TestTelegramTaxonomy:
    @pytest.mark.parametrize(
        ("broker_status", "paper_mode", "expected_level", "expected_substr"),
        [
            ("complete", False, AlertLevel.SUCCESS, "Order filled"),
            ("traded", False, AlertLevel.SUCCESS, "Order filled"),
            ("pending", False, AlertLevel.INFO, "awaiting fill"),
            ("open", False, AlertLevel.INFO, "awaiting fill"),
            ("weird-status", False, AlertLevel.WARNING, "verify manually"),
            ("complete", True, AlertLevel.INFO, "PAPER MODE"),
        ],
    )
    def test_alert_level_matches_broker_status(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
        broker_status: str,
        paper_mode: bool,
        expected_level: AlertLevel,
        expected_substr: str,
    ) -> None:
        """``main``'s success path maps broker_status → alert severity.

        This is Fix #6 (incident 2026-05-20): the pre-fix code fired a
        false 'Order filled' SUCCESS even when the broker reported a
        non-terminal status."""
        fake_result = ExecutionResult(
            success=True,
            position_id=uuid.uuid4(),
            execution_ids=[uuid.uuid4()],
            broker_order_id="ORD-TAXONOMY-1",
            paper_mode=paper_mode,
            message="stub",
            broker_status=broker_status,
        )

        async def _ok(
            session: Any, *, signal: Any, strategy: Any, recommended_lots: Any = None
        ) -> Any:
            return fake_result

        recorder = _AlertRecorder()
        monkeypatch.setattr("app.services.strategy_executor.place_strategy_orders", _ok)
        monkeypatch.setattr("app.services.telegram_alerts.send_alert", recorder)

        signal_id = _insert_signal(db_session_maker, seed)
        _run(_process_signal_in_background(str(signal_id)))

        msgs = recorder.find(expected_level)
        assert any(expected_substr in m for m in msgs), (
            f"broker_status={broker_status!r} paper={paper_mode} "
            f"expected {expected_level} containing {expected_substr!r}; "
            f"got {recorder.calls}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Fix-preservation smoke tests (frozen-module contracts the async path relies on)
# ═══════════════════════════════════════════════════════════════════════


class TestFixPreservationSmoke:
    def test_intraday_product_type_hard_guarded_for_fno(self) -> None:
        """Fix #3 / permanent-rule-1: an explicit INTRADAY/MIS on an F&O
        order raises ``InvalidProductTypeError`` (loud failure, no silent
        downgrade). NRML/MARGIN and an omitted product_type both resolve
        to MARGIN for F&O."""
        for forbidden in ("INTRADAY", "MIS", "intraday"):
            sig = StrategySignal(
                user_id=uuid.uuid4(),
                strategy_id=uuid.uuid4(),
                raw_payload={"product_type": forbidden},
                symbol="BSE-MAY2026-FUT",
                action="ENTRY",
            )
            with pytest.raises(InvalidProductTypeError):
                _resolve_product_type(sig, exchange=Exchange.NFO)

        for allowed in ("NRML", "MARGIN", ""):
            sig = StrategySignal(
                user_id=uuid.uuid4(),
                strategy_id=uuid.uuid4(),
                raw_payload={"product_type": allowed} if allowed else {},
                symbol="BSE-MAY2026-FUT",
                action="ENTRY",
            )
            assert _resolve_product_type(sig, exchange=Exchange.NFO) is ProductType.MARGIN

    def test_broker_rejection_error_contract(self) -> None:
        """Fix #4/#5: the rejection the Dhan adapter raises is a typed
        ``BrokerError`` carrying ``.reason`` — which is exactly what lets the
        background handler's ``isinstance`` branch fire CRITICAL-with-reason
        rather than a generic 'Backend error'. (The adapter's HTTP-200+
        REJECTED parsing lives in the frozen broker tests.)"""
        err = BrokerOrderRejectedError("rejected", broker_name="dhan", reason="margin shortfall")
        assert isinstance(err, BrokerError)
        assert err.reason == "margin shortfall"
        assert "margin shortfall" in str(err)


# ═══════════════════════════════════════════════════════════════════════
# The additive idempotency helper (app.core.signal_idempotency)
# ═══════════════════════════════════════════════════════════════════════


class TestSignalIdempotencyHelper:
    def test_first_call_claims_then_duplicate(self, fake_redis: Any) -> None:
        first = _run(check_and_set_signal_idempotent(fake_redis, "sig-001"))
        second = _run(check_and_set_signal_idempotent(fake_redis, "sig-001"))
        assert first is True
        assert second is False

    def test_key_format_and_ttl(self, fake_redis: Any) -> None:
        assert _run(check_and_set_signal_idempotent(fake_redis, "sig-ttl")) is True
        key = signal_idempotency_key("sig-ttl")
        assert key == "signal:idempotency:sig-ttl"
        assert _run(fake_redis.get(key)) == "1"
        ttl = _run(fake_redis.ttl(key))
        # Allow a small clock margin below the 3600 s ceiling.
        assert 3500 < ttl <= SIGNAL_IDEMPOTENCY_TTL_SECONDS

    def test_distinct_ids_are_independent(self, fake_redis: Any) -> None:
        assert _run(check_and_set_signal_idempotent(fake_redis, "id-a")) is True
        assert _run(check_and_set_signal_idempotent(fake_redis, "id-b")) is True

    def test_nonpositive_ttl_rejected(self, fake_redis: Any) -> None:
        with pytest.raises(ValueError):
            _run(check_and_set_signal_idempotent(fake_redis, "x", ttl_seconds=0))
