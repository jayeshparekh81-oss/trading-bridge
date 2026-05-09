"""Per-check unit tests for the live-orders SafetyChain.

Each test exercises one check in isolation, asserting:

    * ``passed`` flips to the expected boolean given the seeded state.
    * ``reason_hinglish`` matches the spec (exact phrasing where the
      user-facing copy is locked, prefix matching where the variable
      portion is a count or score).
    * ``details`` carries the engineer-facing context the audit log
      surfaces.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import fakeredis.aioredis as fake_aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis_client
from app.core.security import encrypt_credential
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.schemas.broker import BrokerName
from app.strategy_engine.feature_flags import set_flag
from app.strategy_engine.live_orders import safety_checks

# ─── 1. check_auto_kill_switch ────────────────────────────────────────


@pytest.mark.asyncio
async def test_kill_switch_inactive_passes(
    redis: fake_aioredis.FakeRedis, user: User
) -> None:
    result = await safety_checks.check_auto_kill_switch(user_id=user.id)
    assert result.passed is True
    assert result.check_name == "auto_kill_switch"


@pytest.mark.asyncio
async def test_kill_switch_tripped_fails_with_hinglish_reason(
    redis: fake_aioredis.FakeRedis, user: User
) -> None:
    await redis_client.set_kill_switch_status(
        user.id, redis_client.KILL_SWITCH_TRIPPED
    )
    result = await safety_checks.check_auto_kill_switch(user_id=user.id)
    assert result.passed is False
    assert "Auto Kill Switch active hai" in result.reason_hinglish
    assert "loss budget exhaust" in result.reason_hinglish
    assert result.details["redis_status"] == redis_client.KILL_SWITCH_TRIPPED


# ─── 2. check_paper_sessions ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_paper_sessions_count_message_includes_correct_number(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    """Zero seeded → message reports 0/7 with 7 remaining."""
    result = await safety_checks.check_paper_sessions(
        db=db, user_id=user.id, strategy_id=strategy.id
    )
    assert result.passed is False
    assert "Sirf 0/7 paper sessions complete" in result.reason_hinglish
    assert "7 aur karo" in result.reason_hinglish
    assert result.details == {"completed": 0, "required": 7, "remaining": 7}


@pytest.mark.asyncio
async def test_paper_sessions_partial_message_uses_running_count(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    """Three completed sessions → message reports 3/7 with 4 remaining."""
    from datetime import date as _date

    from app.strategy_engine.paper_trading import store as paper_store

    base = _date(2026, 5, 1)
    for i in range(3):
        row = await paper_store.create_session(
            db,
            user_id=user.id,
            strategy_id=strategy.id,
            engine_strategy_id="eng",
            session_date=base + timedelta(days=i),
        )
        await paper_store.complete_session(
            db,
            session_id=row.id,
            total_trades=1,
            total_pnl=Decimal("10"),
        )

    result = await safety_checks.check_paper_sessions(
        db=db, user_id=user.id, strategy_id=strategy.id
    )
    assert result.passed is False
    assert "Sirf 3/7 paper sessions complete" in result.reason_hinglish
    assert "4 aur karo" in result.reason_hinglish


@pytest.mark.asyncio
async def test_paper_sessions_seven_or_more_passes(
    all_passing: tuple[User, Strategy],
    db: AsyncSession,
) -> None:
    user, strategy = all_passing
    result = await safety_checks.check_paper_sessions(
        db=db, user_id=user.id, strategy_id=strategy.id
    )
    assert result.passed is True
    assert result.details["completed"] >= 7


# ─── 3. check_trust_score ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trust_score_missing_says_pehle_backtest(
    db: AsyncSession, strategy: Strategy
) -> None:
    """No cached scores yet → 'Pehle backtest run karo' message."""
    result = await safety_checks.check_trust_score(
        db=db, strategy_id=strategy.id
    )
    assert result.passed is False
    assert "Pehle backtest run karo" in result.reason_hinglish
    assert "Trust Score chahiye" in result.reason_hinglish


@pytest.mark.asyncio
async def test_trust_score_stale_says_24h_purana(
    db: AsyncSession, strategy: Strategy
) -> None:
    """Scores older than 24h → 'Backtest 24h purana hai' message."""
    strategy.last_trust_score = Decimal("90.00")
    strategy.last_truth_score = Decimal("80.00")
    strategy.last_scores_at = datetime.now(UTC) - timedelta(hours=25)
    await db.flush()

    result = await safety_checks.check_trust_score(
        db=db, strategy_id=strategy.id
    )
    assert result.passed is False
    assert "Backtest 24h purana hai" in result.reason_hinglish
    assert "dobara run karo" in result.reason_hinglish


@pytest.mark.asyncio
async def test_trust_score_below_threshold_includes_score(
    db: AsyncSession, strategy: Strategy
) -> None:
    """Score below 70 → message reports the actual score."""
    strategy.last_trust_score = Decimal("65.00")
    strategy.last_truth_score = Decimal("70.00")
    strategy.last_scores_at = datetime.now(UTC) - timedelta(hours=1)
    await db.flush()

    result = await safety_checks.check_trust_score(
        db=db, strategy_id=strategy.id
    )
    assert result.passed is False
    assert "Trust Score 65/100 hai" in result.reason_hinglish
    assert "70+ chahiye live ke liye" in result.reason_hinglish
    assert result.details["trust_score"] == 65.0


@pytest.mark.asyncio
async def test_trust_score_at_threshold_passes(
    db: AsyncSession, strategy: Strategy
) -> None:
    """Score exactly 70 passes (>=, not >)."""
    strategy.last_trust_score = Decimal("70.00")
    strategy.last_truth_score = Decimal("60.00")
    strategy.last_scores_at = datetime.now(UTC) - timedelta(hours=1)
    await db.flush()

    result = await safety_checks.check_trust_score(
        db=db, strategy_id=strategy.id
    )
    assert result.passed is True


# ─── 4. check_truth_score ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_truth_score_below_threshold_references_ai_doctor(
    db: AsyncSession, strategy: Strategy
) -> None:
    """Score below 55 → message references the AI Doctor as the fix path."""
    strategy.last_trust_score = Decimal("80.00")
    strategy.last_truth_score = Decimal("50.00")
    strategy.last_scores_at = datetime.now(UTC) - timedelta(hours=1)
    await db.flush()

    result = await safety_checks.check_truth_score(
        db=db, strategy_id=strategy.id
    )
    assert result.passed is False
    assert "Truth Score 50/100 hai" in result.reason_hinglish
    assert "55+ chahiye" in result.reason_hinglish
    assert "AI Doctor se theek karo" in result.reason_hinglish


# ─── 5. check_live_trading_enabled ────────────────────────────────────


@pytest.mark.asyncio
async def test_per_user_flag_off_fails_with_support_message(
    db: AsyncSession, user: User
) -> None:
    """Per-user column off → block with 'contact support' message."""
    user.live_trading_enabled = False
    await db.flush()
    set_flag("LIVE_TRADING_ENABLED", True)  # global on; per-user wins.

    result = await safety_checks.check_live_trading_enabled(
        db=db, user_id=user.id
    )
    assert result.passed is False
    assert "Live trading abhi enabled nahi hai" in result.reason_hinglish
    assert "Customer support" in result.reason_hinglish


@pytest.mark.asyncio
async def test_global_flag_off_fails_even_when_user_on(
    db: AsyncSession, user: User
) -> None:
    """Defence-in-depth: global flag is the master kill-switch."""
    # ``user`` fixture seeded ``live_trading_enabled=True`` already;
    # global flag default is False.
    result = await safety_checks.check_live_trading_enabled(
        db=db, user_id=user.id
    )
    assert result.passed is False
    assert "Live trading abhi enabled nahi hai" in result.reason_hinglish


# ─── 6. check_broker_connection ───────────────────────────────────────


@pytest.mark.asyncio
async def test_broker_disconnected_fails(
    db: AsyncSession, user: User
) -> None:
    """No active credential rows → block with 'refresh login' message."""
    result = await safety_checks.check_broker_connection(
        db=db, user_id=user.id
    )
    assert result.passed is False
    assert "Broker connection offline" in result.reason_hinglish
    assert "Refresh login" in result.reason_hinglish
    assert result.details["active_count"] == 0


@pytest.mark.asyncio
async def test_broker_inactive_credential_does_not_count(
    db: AsyncSession, user: User
) -> None:
    """Soft-deleted credentials must not satisfy the gate."""
    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.DHAN,
        client_id_enc=encrypt_credential("CID"),
        api_key_enc=encrypt_credential("KEY"),
        api_secret_enc=encrypt_credential("SEC"),
        access_token_enc=encrypt_credential("TOK"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=False,
    )
    db.add(cred)
    await db.flush()

    result = await safety_checks.check_broker_connection(
        db=db, user_id=user.id
    )
    assert result.passed is False
    assert result.details["active_count"] == 0


@pytest.mark.asyncio
async def test_broker_active_credential_passes(
    all_passing: tuple[User, Strategy],
    db: AsyncSession,
) -> None:
    user, _ = all_passing
    result = await safety_checks.check_broker_connection(
        db=db, user_id=user.id
    )
    assert result.passed is True
    assert result.details["active_count"] >= 1


# ─── 7. check_risk_engine_precheck — DEFERRED, fail-open ──────────────


@pytest.mark.asyncio
async def test_risk_engine_precheck_fails_open_with_deferred_note(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    """The risk-engine module does not exist yet — the check passes
    by design and surfaces the deferral in details. This pins the
    fail-open contract so a future implementation can swap the body
    without breaking the chain's audit shape."""
    result = await safety_checks.check_risk_engine_precheck(
        db=db, user_id=user.id, strategy_id=strategy.id
    )
    assert result.passed is True
    assert result.details["deferred"] is True
    assert result.details["phase"] == "8B-3"
    assert "abhi implement nahi hua" in result.reason_hinglish
