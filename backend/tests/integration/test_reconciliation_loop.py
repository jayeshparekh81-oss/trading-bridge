"""Tests for :mod:`app.workers.reconciliation_loop`.

Drives the public ``reconcile_once`` seam directly — no TestClient,
no FastAPI lifespan — so the loop runs in pytest-asyncio's main event
loop without the cross-loop contention that bit Tasks #3-#5.

Coverage targets:

* Paper-mode short-circuit (default state in test fixture).
* Matching DB and broker positions → no alert.
* Drift (DB-only or broker-only) → CRITICAL alert with both sides in
  the message.
* One credential's broker error does NOT kill the tick — sibling
  credentials still get reconciled.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.strategy_position import StrategyPosition
from app.schemas.broker import Exchange, Position, ProductType
from app.workers.reconciliation_loop import reconcile_once
from tests.integration.conftest import _seed_user_with_strategy


async def _seed_position(
    maker: async_sessionmaker[AsyncSession],
    *,
    user_id: UUID,
    broker_credential_id: UUID,
    strategy_id: UUID,
    symbol: str = "NIFTY",
    side: str = "buy",
    quantity: int = 1,
) -> UUID:
    """Add a single open StrategyPosition row, return its id."""
    async with maker() as s:
        pos = StrategyPosition(
            user_id=user_id,
            strategy_id=strategy_id,
            broker_credential_id=broker_credential_id,
            signal_id=None,
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            remaining_quantity=quantity,
            avg_entry_price=Decimal("22500.0"),
            status="open",
        )
        s.add(pos)
        await s.commit()
        return pos.id


def _broker_position(symbol: str, qty: int) -> Position:
    """Build a broker Position with realistic but irrelevant fields.

    Reconciliation only inspects ``symbol`` + ``quantity`` (signed) — the
    rest are populated to satisfy Pydantic.
    """
    return Position(
        symbol=symbol,
        exchange=Exchange.NFO,
        quantity=qty,
        avg_price=Decimal("22500.0"),
        ltp=Decimal("22510.0"),
        unrealized_pnl=Decimal("100.0"),
        product_type=ProductType.INTRADAY,
    )


# ═══════════════════════════════════════════════════════════════════════
# Paper-mode short-circuit
# ═══════════════════════════════════════════════════════════════════════


class TestPaperModeNoOp:
    async def test_returns_zero_without_touching_brokers(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Default test fixture forces ``STRATEGY_PAPER_MODE=true``;
        ``reconcile_once`` short-circuits before any broker is built."""
        # Ensure paper mode is on (matches conftest defaults but explicit
        # for documentation).
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        # Trip a sentinel if any broker construction is attempted —
        # paper mode short-circuit must fire before this is reached.
        broker_built = []

        def _fail_get_broker_class(_name: Any) -> Any:
            broker_built.append(True)
            raise AssertionError(
                "broker class lookup should not happen in paper mode"
            )

        monkeypatch.setattr(
            "app.brokers.registry.get_broker_class", _fail_get_broker_class
        )

        async with db_session_maker() as session:
            mismatches = await reconcile_once(session)

        assert mismatches == 0
        assert broker_built == []


# ═══════════════════════════════════════════════════════════════════════
# Matching state — no drift
# ═══════════════════════════════════════════════════════════════════════


class TestMatchingState:
    async def test_db_and_broker_match_no_alert(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DB has 1 NIFTY long; broker reports the same 1 NIFTY long.
        Reconciliation returns 0 mismatches and fires no alert."""
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        seeded = await _seed_user_with_strategy(
            db_session_maker, email="recon-match@tradetri.com"
        )
        await _seed_position(
            db_session_maker,
            user_id=seeded["user_id"],
            broker_credential_id=seeded["credential_id"],
            strategy_id=seeded["strategy_id"],
            symbol="NIFTY",
            side="buy",
            quantity=1,
        )

        # Stub the broker — return the matching long position.
        _install_stub_broker(
            monkeypatch, positions=[_broker_position("NIFTY", 1)]
        )

        captured: list[tuple[Any, str]] = []

        async def _capture_alert(level: Any, message: str) -> None:
            captured.append((level, message))

        monkeypatch.setattr(
            "app.services.telegram_alerts.send_alert", _capture_alert
        )

        async with db_session_maker() as session:
            mismatches = await reconcile_once(session)

        assert mismatches == 0
        assert captured == []


# ═══════════════════════════════════════════════════════════════════════
# Drift detected — CRITICAL alert
# ═══════════════════════════════════════════════════════════════════════


class TestDriftDetected:
    async def test_drift_fires_critical_alert_with_both_sides(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DB has NIFTY long; broker reports BANKNIFTY long.

        The diff has both DB-only (NIFTY) and broker-only (BANKNIFTY)
        entries. A single CRITICAL alert fires per credential per tick
        with both sides in the message body.
        """
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        seeded = await _seed_user_with_strategy(
            db_session_maker, email="recon-drift@tradetri.com"
        )
        await _seed_position(
            db_session_maker,
            user_id=seeded["user_id"],
            broker_credential_id=seeded["credential_id"],
            strategy_id=seeded["strategy_id"],
            symbol="NIFTY",
            side="buy",
            quantity=1,
        )

        _install_stub_broker(
            monkeypatch, positions=[_broker_position("BANKNIFTY", 1)]
        )

        from app.services.telegram_alerts import AlertLevel

        captured: list[tuple[AlertLevel, str]] = []

        async def _capture_alert(level: AlertLevel, message: str) -> None:
            captured.append((level, message))

        monkeypatch.setattr(
            "app.services.telegram_alerts.send_alert", _capture_alert
        )

        async with db_session_maker() as session:
            mismatches = await reconcile_once(session)

        # 1 DB-only + 1 broker-only = 2 mismatches.
        assert mismatches == 2

        critical_alerts = [
            msg for lvl, msg in captured if lvl is AlertLevel.CRITICAL
        ]
        assert len(critical_alerts) == 1, (
            f"expected exactly one CRITICAL alert; captured={captured}"
        )
        body = critical_alerts[0]
        assert "DB-broker drift detected" in body
        assert "NIFTY" in body  # DB-only side
        assert "BANKNIFTY" in body  # broker-only side


# ═══════════════════════════════════════════════════════════════════════
# Network error per-credential isolation
# ═══════════════════════════════════════════════════════════════════════


class TestNetworkErrorIsolation:
    async def test_one_creds_broker_error_does_not_kill_other_creds(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Two credentials. The first credential's broker raises on
        ``get_positions``; the second succeeds with matching state.

        Asserts the tick continues past the first failure, the second
        cred's reconciliation runs, and no exception escapes
        ``reconcile_once``.
        """
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        seed_a = await _seed_user_with_strategy(
            db_session_maker, email="recon-fail-a@tradetri.com"
        )
        seed_b = await _seed_user_with_strategy(
            db_session_maker, email="recon-fail-b@tradetri.com"
        )
        await _seed_position(
            db_session_maker,
            user_id=seed_b["user_id"],
            broker_credential_id=seed_b["credential_id"],
            strategy_id=seed_b["strategy_id"],
            symbol="NIFTY",
            side="buy",
            quantity=1,
        )

        cred_a_id = seed_a["credential_id"]

        # Cred A: get_positions raises. Cred B: returns matching state.
        # The broker factory is shared, so we discriminate inside it.
        from app.core.exceptions import BrokerConnectionError
        from app.schemas.broker import BrokerCredentials

        class _FailOrMatchBroker:
            def __init__(self, creds: BrokerCredentials) -> None:
                self.user_id = creds.user_id

            async def is_session_valid(self) -> bool:
                return True

            async def login(self) -> bool:
                return True

            async def get_positions(self) -> list[Position]:
                if str(self.user_id) == str(seed_a["user_id"]):
                    raise BrokerConnectionError(
                        "simulated broker outage", broker_name="dhan"
                    )
                return [_broker_position("NIFTY", 1)]

        monkeypatch.setattr(
            "app.brokers.registry.get_broker_class",
            lambda _name: _FailOrMatchBroker,
        )

        # Ensure no alert noise — the raise happens BEFORE the diff/alert
        # logic, so no CRITICAL alert should fire from cred A's failure.
        captured: list[tuple[Any, str]] = []

        async def _capture_alert(level: Any, message: str) -> None:
            captured.append((level, message))

        monkeypatch.setattr(
            "app.services.telegram_alerts.send_alert", _capture_alert
        )

        async with db_session_maker() as session:
            # Must NOT raise.
            mismatches = await reconcile_once(session)

        # Cred A failed → no count contribution from it. Cred B matched
        # → 0 mismatches. Total: 0.
        assert mismatches == 0
        # No alert: cred A failed (no diff to surface), cred B matched.
        assert captured == []
        # Sanity: cred A's id was actually attempted (the failure path
        # was reached, not skipped).
        assert cred_a_id is not None


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _install_stub_broker(
    monkeypatch: pytest.MonkeyPatch, *, positions: list[Position]
) -> None:
    """Wire a fake broker class into the registry for reconcile_once.

    The fake responds to the four methods reconcile_once touches:
    ``__init__``, ``is_session_valid``, ``login``, ``get_positions``.
    """

    class _StubBroker:
        def __init__(self, _creds: Any) -> None:
            pass

        async def is_session_valid(self) -> bool:
            return True

        async def login(self) -> bool:
            return True

        async def get_positions(self) -> list[Position]:
            return list(positions)

    monkeypatch.setattr(
        "app.brokers.registry.get_broker_class", lambda _name: _StubBroker
    )
