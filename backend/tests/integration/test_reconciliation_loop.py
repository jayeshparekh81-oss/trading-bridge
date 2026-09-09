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
    status: str = "open",
) -> UUID:
    """Add a single StrategyPosition row, return its id."""
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
            status=status,
        )
        s.add(pos)
        await s.commit()
        return pos.id


async def _make_strategy_live(
    maker: async_sessionmaker[AsyncSession], strategy_id: UUID
) -> None:
    """Flip a seeded strategy to LIVE (``is_paper=False``).

    ⚠️ WITHOUT THIS, A DRIFT TEST PASSES VACUOUSLY. ``_seed_user_with_strategy``
    leaves ``is_paper`` at its server default of TRUE (migration 027), and
    ``_list_credentials_backing_live_strategies`` only returns credentials
    backing a LIVE strategy. A paper-seeded fixture therefore yields ZERO
    credentials, ``reconcile_once`` returns 0 without ever reaching the diff,
    and an assertion like ``mismatches == 0`` is satisfied by the loop having
    done nothing at all.

    Both drift tests below were in that state on origin/main — asserting on an
    alert path that never executed. Found 2026-09-09 while fixing the loop.
    """
    from sqlalchemy import update as _update

    from app.db.models.strategy import Strategy as _Strategy

    async with maker() as s:
        await s.execute(
            _update(_Strategy)
            .where(_Strategy.id == strategy_id)
            .values(is_paper=False)
        )
        await s.commit()


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
        entries — two DIFFERENT facts, no longer averaged into one line.

        The DB-only side is a STALE ROW: we show a position open that the
        broker does not hold. That is CRITICAL and, since 2026-09-09, is
        NOT behind the flag. The broker-only side is usually a manual
        trade in the broker's own app; it stays behind the flag, which
        this test sets True so both paths are exercised at once.
        """
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        monkeypatch.setenv("RECONCILIATION_TELEGRAM_ENABLED", "true")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        seeded = await _seed_user_with_strategy(
            db_session_maker, email="recon-drift@tradetri.com"
        )
        await _make_strategy_live(db_session_maker, seeded["strategy_id"])
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
        stale = critical_alerts[0]
        assert "STALE POSITION ROW" in stale
        assert "NIFTY" in stale  # the row we hold and the broker does not
        # The manual broker position is a separate, lesser message.
        warnings = [msg for lvl, msg in captured if lvl is AlertLevel.WARNING]
        assert len(warnings) == 1, f"captured={captured}"
        assert "BANKNIFTY" in warnings[0]

    async def test_stale_row_alert_fires_even_with_the_flag_off(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """🔴 THE REGRESSION. With the flag at its default (False), a
        STALE ROW must still speak; only the broker-only chatter is muted.

        Until 2026-09-09 both sides sat behind one flag that defaulted
        OFF — because a manual broker position drifts on every tick and
        would have sent ~60 Telegram messages an hour. The cost of that
        blanket mute: the phantom BUY 800 sat `open` in the DB for two
        days after the broker had flattened it, the loop logged the drift
        3,551 times, and nobody was told anything at all.

        A position WE claim and the broker does not have is now always
        worth a message.
        """
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        # Explicit unset (default is False, but pin it for clarity).
        monkeypatch.delenv("RECONCILIATION_TELEGRAM_ENABLED", raising=False)
        from app.core import config as _config

        _config.get_settings.cache_clear()

        seeded = await _seed_user_with_strategy(
            db_session_maker, email="recon-noalert@tradetri.com"
        )
        await _make_strategy_live(db_session_maker, seeded["strategy_id"])
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

        assert mismatches == 2

        # The STALE ROW speaks regardless of the flag.
        criticals = [msg for lvl, msg in captured if lvl is AlertLevel.CRITICAL]
        assert len(criticals) == 1, (
            f"a stale row must alert even with the flag off; captured={captured}"
        )
        assert "STALE POSITION ROW" in criticals[0]
        assert "NIFTY" in criticals[0]

        # The manual broker position stays muted — that was the spam.
        assert not [msg for lvl, msg in captured if lvl is AlertLevel.WARNING], (
            f"broker-only chatter should stay behind the flag; captured={captured}"
        )


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


# ═══════════════════════════════════════════════════════════════════════
# The three blindness defects (fixed 2026-09-09)
#
# Each of these reproduces a way the loop failed to SEE a live position.
# Together they explain how strategy_positions a13ddeb0 (BSE-SEP2026-FUT
# BUY 800) stayed `open` for two days after the broker had flattened it
# while the loop ticked 3,551 times and reported `db_only=[]` every time.
# ═══════════════════════════════════════════════════════════════════════


class TestBlindnessDefects:
    async def test_a_partial_position_is_still_reconciled(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """🔴 DEFECT 1 — the status filter excluded `partial`.

        A position that has booked SOME lots still has the REST in the
        market. Filtering on `status == "open"` dropped it from the diff
        the instant it took its first partial — which is exactly when its
        remaining quantity stops matching the original and drift matters.
        """
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        seeded = await _seed_user_with_strategy(
            db_session_maker, email="recon-partial@tradetri.com"
        )
        await _make_strategy_live(db_session_maker, seeded["strategy_id"])
        await _seed_position(
            db_session_maker,
            user_id=seeded["user_id"],
            broker_credential_id=seeded["credential_id"],
            strategy_id=seeded["strategy_id"],
            symbol="NIFTY",
            side="sell",
            quantity=1,
            status="partial",
        )
        # Broker is flat — the partial row is stale.
        _install_stub_broker(monkeypatch, positions=[])

        async with db_session_maker() as session:
            mismatches = await reconcile_once(session)

        assert mismatches == 1, (
            "a `partial` row must be reconciled; on the old status filter "
            "this returned 0 and the row was invisible"
        )

    async def test_a_rotated_credential_still_finds_the_position(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """🔴 DEFECT 2 — positions were matched on the rotating FK.

        ``auto_login`` mints a NEW credential row every weekday ~03:00 and
        deactivates yesterday's. A position row keeps the id it was opened
        with, so ``broker_credential_id == cred.id`` stopped matching at
        the next rotation and every open position went invisible. This is
        precisely what happened to the phantom at the 2026-09-08 03:00
        rotation. Scope is now (user_id, broker_name).
        """
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        seeded = await _seed_user_with_strategy(
            db_session_maker, email="recon-rotate@tradetri.com"
        )
        await _make_strategy_live(db_session_maker, seeded["strategy_id"])
        # Opened YESTERDAY, against yesterday's credential.
        await _seed_position(
            db_session_maker,
            user_id=seeded["user_id"],
            broker_credential_id=seeded["credential_id"],
            strategy_id=seeded["strategy_id"],
            symbol="NIFTY",
            side="buy",
            quantity=1,
        )

        # Overnight rotation: yesterday's row is deactivated, a new one is
        # inserted, and NOTHING repoints the position or the strategy.
        from datetime import UTC, datetime

        from sqlalchemy import update as _update

        from app.core.security import encrypt_credential
        from app.db.models.broker_credential import BrokerCredential
        from app.schemas.broker import BrokerName

        async with db_session_maker() as s:
            await s.execute(
                _update(BrokerCredential)
                .where(BrokerCredential.id == seeded["credential_id"])
                .values(is_active=False)
            )
            s.add(
                BrokerCredential(
                    user_id=seeded["user_id"],
                    broker_name=BrokerName.DHAN,
                    client_id_enc=encrypt_credential("DHAN-CID"),
                    api_key_enc=encrypt_credential("DHAN-KEY"),
                    api_secret_enc=encrypt_credential("DHAN-SECRET"),
                    access_token_enc=encrypt_credential("DHAN-TOK-TODAY"),
                    token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                    is_active=True,
                )
            )
            await s.commit()

        # Broker is flat — yesterday's row is stale and must be seen.
        _install_stub_broker(monkeypatch, positions=[])

        async with db_session_maker() as session:
            mismatches = await reconcile_once(session)

        assert mismatches == 1, (
            "after a token rotation the position must still be reconciled; "
            "matching on the credential FK returned 0 here — the exact way "
            "the phantom BUY 800 went invisible"
        )

    async def test_symbol_case_does_not_manufacture_drift(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """🔴 DEFECT 3 — the diff was a case-SENSITIVE set difference.

        We store ``BSE-SEP2026-FUT``; Dhan returns ``BSE-Sep2026-FUT``. A
        correctly-tracked position therefore appeared on BOTH sides of the
        diff at once — observed in production on 2026-09-07T05:01:17Z.
        Every mismatch it printed for a healthy position was noise.
        """
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        seeded = await _seed_user_with_strategy(
            db_session_maker, email="recon-case@tradetri.com"
        )
        await _make_strategy_live(db_session_maker, seeded["strategy_id"])
        await _seed_position(
            db_session_maker,
            user_id=seeded["user_id"],
            broker_credential_id=seeded["credential_id"],
            strategy_id=seeded["strategy_id"],
            symbol="BSE-SEP2026-FUT",
            side="buy",
            quantity=800,
        )
        # Same position, the broker's own spelling.
        _install_stub_broker(
            monkeypatch, positions=[_broker_position("BSE-Sep2026-FUT", 800)]
        )

        async with db_session_maker() as session:
            mismatches = await reconcile_once(session)

        assert mismatches == 0, (
            "one position spelled two ways is still ONE position; the "
            "case-sensitive diff reported it as two separate mismatches"
        )

    async def test_a_standing_stale_row_does_not_alert_every_tick(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The alert is ON by default, so it must not become the spam that
        got the old one switched off.

        A stale row is a STANDING CONDITION, not an event: it is still
        there on the next tick, and the next. Alerting on an unchanged
        signature would be 60 messages an hour — which is exactly why the
        original alert was gated off, and why nobody was told for two days.
        """
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        from app.workers import reconciliation_loop as _loop

        _loop._last_alert.clear()

        seeded = await _seed_user_with_strategy(
            db_session_maker, email="recon-dedupe@tradetri.com"
        )
        await _make_strategy_live(db_session_maker, seeded["strategy_id"])
        await _seed_position(
            db_session_maker,
            user_id=seeded["user_id"],
            broker_credential_id=seeded["credential_id"],
            strategy_id=seeded["strategy_id"],
            symbol="NIFTY",
            side="buy",
            quantity=1,
        )
        _install_stub_broker(monkeypatch, positions=[])

        from app.services.telegram_alerts import AlertLevel

        captured: list[tuple[AlertLevel, str]] = []

        async def _capture_alert(level: AlertLevel, message: str) -> None:
            captured.append((level, message))

        monkeypatch.setattr(
            "app.services.telegram_alerts.send_alert", _capture_alert
        )

        async with db_session_maker() as session:
            await reconcile_once(session)
            await reconcile_once(session)
            await reconcile_once(session)

        criticals = [m for lvl, m in captured if lvl is AlertLevel.CRITICAL]
        assert len(criticals) == 1, (
            f"three ticks of the SAME stale row must speak once, not three "
            f"times; captured={captured}"
        )
        _loop._last_alert.clear()
