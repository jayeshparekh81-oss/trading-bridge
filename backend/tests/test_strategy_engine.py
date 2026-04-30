"""Strategy execution engine — unit tests.

Covers four moving parts:

    * AI validator         — bot's faithful port: weighted scoring,
                             tier resolution, VIX modulation, full
                             validate_signal() flow with crafted
                             indicator dicts.
    * Strategy executor    — paper mode end-to-end + AI-recommended-lots
                             wiring (use AI tier; cap by strategy.entry_lots).
    * Position manager     — apply_tick covers partial profit, trailing
                             SL, and hard SL transitions.
    * Kill-switch helper   — close_position_now writes a closing
                             execution and marks the row closed.

The webhook endpoint test (HMAC, time-of-day, quantity ceiling) is the
day-1 follow-up — the helper functions it depends on are unit-tested
here so the integration test can stay thin.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio

# Disable strategy-paper mode env-var for live tests; default True.
os.environ.setdefault("STRATEGY_PAPER_MODE", "true")

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.schemas.ai_decision import AIDecisionStatus
from app.schemas.broker import BrokerName, OrderSide
from app.services import ai_validator, position_manager
from app.services.ai_validator import (
    LONG_THRESHOLD,
    LONG_THRESHOLD_4LOT,
    SHORT_THRESHOLD,
    _resolve_tier,
    compute_score,
    detect_regime,
    validate_signal,
    vix_adjust_qty,
)
from app.services.position_manager import (
    apply_tick,
    close_position_now,
    manage_open_positions,
    simulate_paper_ltp,
)
from app.services.strategy_executor import (
    QUANTITY_CEILING,
    StrategyExecutorError,
    place_strategy_orders,
)

# Indicator values that PASS every LONG side weight test (score ≈ 100).
_ALL_PASS_LONG: dict[str, float] = {
    "PriceSpd": 5.0,        # >= 4.72 * 0.8
    "ATR": 5.0,             # >= 5.0 * 0.8
    "LongMA": 800.0,        # >= 736.49 * 0.85
    "GaussL": 800.0,
    "SlowMA": 800.0,
    "GaussS": 800.0,
    "FastMA": 800.0,
    "VWAPDist": 1.0,        # >= 0.77 * 0.8
    "BullGap": 200.0,       # >= 179 * 0.85
    "Squeeze": 6.0,         # >= 5.5 * 0.8
    "BodyPct": 70.0,        # >= 64.2 * 0.8
    "Vol": 400000.0,        # >= 332669 * 0.85
    "DeltaPwr": 5.0,        # > 3.0
    "BearGap": 110.0,       # >= 106 * 0.85
    "RVOL": 2.0,            # >= 1.66 * 0.8
    "OFInten": 2.0,         # >= 1.6 * 0.85
    "RSI": 60.0,            # >= 54.82 * 0.8
}

# ═══════════════════════════════════════════════════════════════════════
# Fixtures — sqlite in-memory + seeded user/cred/strategy
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """Fresh in-memory aiosqlite DB with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(db: AsyncSession) -> dict[str, Any]:
    """User + active broker credential + strategy with risk config."""
    user = User(email="trader@example.com", password_hash="x", is_active=True)
    db.add(user)
    await db.flush()

    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.FYERS,
        client_id_enc=encrypt_credential("CID"),
        api_key_enc=encrypt_credential("KEY"),
        api_secret_enc=encrypt_credential("SECRET"),
        access_token_enc=encrypt_credential("TOK"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    db.add(cred)
    await db.flush()

    strategy = Strategy(
        user_id=user.id,
        name="test-strat",
        broker_credential_id=cred.id,
        entry_lots=4,
        partial_profit_lots=2,
        partial_profit_target_pct=Decimal("1.000"),  # +1%
        trail_lots=2,
        trail_offset_pct=Decimal("0.500"),  # 0.5%
        hard_sl_pct=Decimal("1.000"),  # -1%
        ai_validation_enabled=False,  # bypass validator in executor tests
        is_active=True,
    )
    db.add(strategy)
    await db.flush()

    signal = StrategySignal(
        user_id=user.id,
        strategy_id=strategy.id,
        raw_payload={"price": "100"},
        symbol="NIFTY24500CE",
        action="BUY",
        quantity=4,
        order_type="market",
        status="received",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    await db.refresh(strategy)
    await db.refresh(cred)

    return {
        "user_id": user.id,
        "credential_id": cred.id,
        "strategy": strategy,
        "signal": signal,
    }


# ═══════════════════════════════════════════════════════════════════════
# AI validator — pure scoring unit tests
# ═══════════════════════════════════════════════════════════════════════


def test_compute_score_all_pass_long_hits_max() -> None:
    """All-pass LONG indicators sum to roughly the full weight total (~100)."""
    score = compute_score(_ALL_PASS_LONG, "LONG")
    # Total of LONG_W weights is ~100; all-pass should be near-max.
    assert score >= 99.0
    assert score <= 100.5


def test_compute_score_all_fail_long_baseline_30() -> None:
    """Empty indicators → every test fails → 30% of total weight ≈ 30."""
    score = compute_score({}, "LONG")
    assert 29.0 <= score <= 31.0


def test_compute_score_all_fail_short_baseline_30() -> None:
    """Truly-all-fail SHORT indicators → ~30 baseline.

    Empty dict alone leaves RSI=0 which trivially satisfies the SHORT
    pass test ``val <= target*0.8`` (since 0 <= 43.86). We seed RSI
    above the cutoff so it actually fails along with everything else.
    """
    score = compute_score({"RSI": 100.0}, "SHORT")
    assert 29.0 <= score <= 31.0


def test_resolve_tier_long_4lot() -> None:
    """Score ≥ 85 on LONG → 4-lot tier."""
    assert _resolve_tier(LONG_THRESHOLD_4LOT, "LONG") == (True, 4, "long_4lot")
    assert _resolve_tier(90.0, "LONG") == (True, 4, "long_4lot")


def test_resolve_tier_long_2lot() -> None:
    """Score ≥ 51 and < 85 on LONG → 2-lot tier."""
    assert _resolve_tier(LONG_THRESHOLD, "LONG") == (True, 2, "long_2lot")
    assert _resolve_tier(65.0, "LONG") == (True, 2, "long_2lot")
    assert _resolve_tier(84.99, "LONG") == (True, 2, "long_2lot")


def test_resolve_tier_long_rejected() -> None:
    """Score < 51 on LONG → rejected."""
    assert _resolve_tier(45.0, "LONG") == (False, 0, "long_rejected")
    assert _resolve_tier(0.0, "LONG") == (False, 0, "long_rejected")


def test_resolve_tier_short_2lot() -> None:
    """Score ≥ 55 on SHORT → 2-lot tier (only one tier exists)."""
    assert _resolve_tier(SHORT_THRESHOLD, "SHORT") == (True, 2, "short_2lot")
    assert _resolve_tier(95.0, "SHORT") == (True, 2, "short_2lot")


def test_resolve_tier_short_rejected() -> None:
    """Score < 55 on SHORT → rejected."""
    assert _resolve_tier(50.0, "SHORT") == (False, 0, "short_rejected")


def test_vix_adjust_full_band() -> None:
    """VIX in [11.5, 20.0] → full qty."""
    assert vix_adjust_qty(4, 15.0) == (4, "vix_full")
    assert vix_adjust_qty(2, 11.5) == (2, "vix_full")
    assert vix_adjust_qty(2, 20.0) == (2, "vix_full")


def test_vix_adjust_halves_outside_band() -> None:
    """VIX < 11.5 OR > 20.0 → halve qty (rounded)."""
    assert vix_adjust_qty(4, 22.0) == (2, "vix_half")
    assert vix_adjust_qty(4, 10.0) == (2, "vix_half")
    # Odd qty halves to ceil(0.5*qty)
    assert vix_adjust_qty(3, 25.0) == (2, "vix_half")


def test_vix_adjust_missing_returns_full() -> None:
    """VIX None → vix_missing tag, qty unchanged."""
    assert vix_adjust_qty(4, None) == (4, "vix_missing")


# ═══════════════════════════════════════════════════════════════════════
# Regime detection — pure unit tests
# ═══════════════════════════════════════════════════════════════════════


def test_detect_regime_off_when_toggle_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """USE_REGIME_DETECTION default OFF → ('off', 1.0) regardless of indicators."""
    monkeypatch.delenv("USE_REGIME_DETECTION", raising=False)
    assert detect_regime({"IndiaVIX": 25.0, "ADX": 30.0}) == ("off", 1.0)


def test_detect_regime_volatile_high_vix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toggle ON + VIX > 22 → ('volatile', 1.10)."""
    monkeypatch.setenv("USE_REGIME_DETECTION", "1")
    assert detect_regime({"IndiaVIX": 25.0, "ADX": 30.0}) == ("volatile", 1.10)


def test_detect_regime_trending_high_adx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toggle ON + ADX ≥ 25 + VIX normal → ('trending', 1.0)."""
    monkeypatch.setenv("USE_REGIME_DETECTION", "1")
    assert detect_regime({"IndiaVIX": 15.0, "ADX": 30.0}) == ("trending", 1.0)


def test_detect_regime_ranging_low_adx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toggle ON + ADX ≤ 15 + VIX normal → ('ranging', 1.15)."""
    monkeypatch.setenv("USE_REGIME_DETECTION", "1")
    assert detect_regime({"IndiaVIX": 15.0, "ADX": 10.0}) == ("ranging", 1.15)


def test_detect_regime_normal_fallthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toggle ON + VIX normal + ADX in (15, 25) → ('normal', 1.0)."""
    monkeypatch.setenv("USE_REGIME_DETECTION", "1")
    assert detect_regime({"IndiaVIX": 15.0, "ADX": 20.0}) == ("normal", 1.0)


def test_resolve_tier_with_volatile_mult_raises_threshold() -> None:
    """LONG score 87 with regime mult 1.10 → eff_4lot=93.5 → falls to 2lot tier.

    Without regime (mult=1.0): 87 ≥ 85 → long_4lot.
    With volatile mult 1.10: 87 < 93.5 BUT 87 ≥ 56.1 → long_2lot.
    """
    # Without regime
    assert _resolve_tier(87.0, "LONG") == (True, 4, "long_4lot")
    # With volatile mult — drops to 2-lot tier
    assert _resolve_tier(87.0, "LONG", regime_mult=1.10) == (True, 2, "long_2lot")


def test_resolve_tier_with_ranging_mult_can_reject() -> None:
    """LONG score 55 + ranging mult 1.15 → eff_2lot=58.65 → REJECTED.

    Without regime: 55 ≥ 51 → long_2lot.
    With ranging 1.15: 55 < 58.65 → long_rejected.
    """
    assert _resolve_tier(55.0, "LONG") == (True, 2, "long_2lot")
    assert _resolve_tier(55.0, "LONG", regime_mult=1.15) == (False, 0, "long_rejected")


@pytest.mark.asyncio
async def test_validate_signal_regime_volatile_demotes_tier(
    seeded: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: regime ON + score 87 + VIX 25 → 4-lot tier raised → demoted to 2-lot.

    VIX 25 is also outside the qty-modulation band, so the 2-lot base
    halves to 1 lot via vix_adjust_qty. Validates both regime + VIX
    layers fire on the same call coherently.
    """
    monkeypatch.setenv("USE_REGIME_DETECTION", "1")
    seeded["strategy"].ai_validation_enabled = True
    monkeypatch.setattr(ai_validator, "compute_score", lambda *_a, **_kw: 87.0)
    decision = await validate_signal(
        seeded["signal"],
        seeded["strategy"],
        indicators={"IndiaVIX": 25.0, "ADX": 20.0},
        vix=25.0,
    )
    assert decision.decision is AIDecisionStatus.APPROVED
    # eff_4lot = 85 * 1.10 = 93.5; 87 < 93.5 → long_2lot tier
    # base 2-lot then halved by VIX 25 → 1 lot
    assert decision.recommended_lots == 1
    assert "volatile" in decision.reasoning
    assert "long_2lot" in decision.reasoning


@pytest.mark.asyncio
async def test_validate_signal_regime_off_keeps_existing_behaviour(
    seeded: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regime master toggle OFF (default) → mult=1.0 → identical to pre-regime path."""
    monkeypatch.delenv("USE_REGIME_DETECTION", raising=False)
    seeded["strategy"].ai_validation_enabled = True
    monkeypatch.setattr(ai_validator, "compute_score", lambda *_a, **_kw: 87.0)
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], indicators={}, vix=15.0
    )
    assert decision.decision is AIDecisionStatus.APPROVED
    assert decision.recommended_lots == 4
    # Reasoning still surfaces regime tag (now "off"), but tier is unchanged
    assert "long_4lot" in decision.reasoning


# ═══════════════════════════════════════════════════════════════════════
# AI validator — full validate_signal() flow
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_validate_signal_bypass_when_disabled(seeded: dict[str, Any]) -> None:
    """ai_validation_enabled=False → APPROVED with strategy.entry_lots."""
    decision = await validate_signal(seeded["signal"], seeded["strategy"])
    assert decision.decision is AIDecisionStatus.APPROVED
    assert decision.confidence == Decimal("1.000")
    # strategy.entry_lots = 4 in the seeded fixture
    assert decision.recommended_lots == 4


@pytest.mark.asyncio
async def test_validate_signal_long_4lot_full_vix(
    seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """LONG score 87 + VIX 15 → APPROVED, 4 lots."""
    seeded["strategy"].ai_validation_enabled = True
    monkeypatch.setattr(ai_validator, "compute_score", lambda *_a, **_kw: 87.0)
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], indicators={}, vix=15.0
    )
    assert decision.decision is AIDecisionStatus.APPROVED
    assert decision.recommended_lots == 4
    assert "long_4lot" in decision.reasoning
    assert decision.confidence == Decimal("0.87")


@pytest.mark.asyncio
async def test_validate_signal_long_2lot_full_vix(
    seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """LONG score 65 + VIX 15 → APPROVED, 2 lots."""
    seeded["strategy"].ai_validation_enabled = True
    monkeypatch.setattr(ai_validator, "compute_score", lambda *_a, **_kw: 65.0)
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], indicators={}, vix=15.0
    )
    assert decision.decision is AIDecisionStatus.APPROVED
    assert decision.recommended_lots == 2
    assert "long_2lot" in decision.reasoning


@pytest.mark.asyncio
async def test_validate_signal_honours_payload_score(
    seeded: dict[str, Any],
) -> None:
    """raw_payload.score=65 is honoured directly — no compute_score fallback."""
    seeded["strategy"].ai_validation_enabled = True
    seeded["signal"].raw_payload = {"score": 65, "price": "100"}
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], indicators={}, vix=15.0
    )
    assert decision.decision is AIDecisionStatus.APPROVED
    assert decision.recommended_lots == 2
    assert "long_2lot" in decision.reasoning


@pytest.mark.asyncio
async def test_validate_signal_long_rejected_below_threshold(
    seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """LONG score 45 → REJECTED, 0 lots."""
    seeded["strategy"].ai_validation_enabled = True
    monkeypatch.setattr(ai_validator, "compute_score", lambda *_a, **_kw: 45.0)
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], indicators={}, vix=15.0
    )
    assert decision.decision is AIDecisionStatus.REJECTED
    assert decision.recommended_lots == 0


@pytest.mark.asyncio
async def test_validate_signal_short_2lot_full_vix(
    seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """SELL signal → SHORT side; score 60 → APPROVED, 2 lots."""
    seeded["strategy"].ai_validation_enabled = True
    seeded["signal"].action = "SELL"
    monkeypatch.setattr(ai_validator, "compute_score", lambda *_a, **_kw: 60.0)
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], indicators={}, vix=15.0
    )
    assert decision.decision is AIDecisionStatus.APPROVED
    assert decision.recommended_lots == 2
    assert "short_2lot" in decision.reasoning


@pytest.mark.asyncio
async def test_validate_signal_short_rejected_below_threshold(
    seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """SHORT score 50 → REJECTED."""
    seeded["strategy"].ai_validation_enabled = True
    seeded["signal"].action = "SELL"
    monkeypatch.setattr(ai_validator, "compute_score", lambda *_a, **_kw: 50.0)
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], indicators={}, vix=15.0
    )
    assert decision.decision is AIDecisionStatus.REJECTED
    assert decision.recommended_lots == 0


@pytest.mark.asyncio
async def test_validate_signal_vix_halves_recommendation(
    seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """LONG score 87 + VIX 22 (high) → APPROVED, 4-lot tier halved → 2 lots."""
    seeded["strategy"].ai_validation_enabled = True
    monkeypatch.setattr(ai_validator, "compute_score", lambda *_a, **_kw: 87.0)
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], indicators={}, vix=22.0
    )
    assert decision.decision is AIDecisionStatus.APPROVED
    assert decision.recommended_lots == 2
    assert "vix_half" in decision.reasoning


@pytest.mark.asyncio
async def test_validate_signal_unsupported_action(
    seeded: dict[str, Any]
) -> None:
    """EXIT-style action → REJECTED at validator (not the executor's job)."""
    seeded["strategy"].ai_validation_enabled = True
    seeded["signal"].action = "EXIT"
    decision = await validate_signal(seeded["signal"], seeded["strategy"])
    assert decision.decision is AIDecisionStatus.REJECTED
    assert decision.recommended_lots == 0


# ═══════════════════════════════════════════════════════════════════════
# Strategy executor — paper mode
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_executor_paper_mode_opens_position(
    db: AsyncSession, seeded: dict[str, Any], monkeypatch
) -> None:
    """Paper mode writes 4 entry rows and one position with computed levels."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    result = await place_strategy_orders(
        db, signal=seeded["signal"], strategy=seeded["strategy"]
    )
    await db.commit()

    assert result.success
    assert result.paper_mode is True
    assert len(result.execution_ids) == 4

    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    assert pos.status == "open"
    assert pos.total_quantity == 4
    assert pos.remaining_quantity == 4
    # avg=100, +1% target = 101, -1% SL = 99, 0.5% trail offset = 0.50
    assert pos.avg_entry_price == Decimal("100")
    assert pos.target_price == Decimal("101.000")
    assert pos.stop_loss_price == Decimal("99.000")
    assert pos.trail_offset == Decimal("0.500")


@pytest.mark.asyncio
async def test_executor_rejects_quantity_above_ceiling(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """Day-1 ceiling: anything > 4 lots is rejected."""
    seeded["signal"].quantity = QUANTITY_CEILING + 1
    with pytest.raises(StrategyExecutorError):
        await place_strategy_orders(
            db, signal=seeded["signal"], strategy=seeded["strategy"]
        )


@pytest.mark.asyncio
async def test_executor_rejects_unsupported_action(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """EXIT is owned by the position manager, not the executor."""
    seeded["signal"].action = "EXIT"
    with pytest.raises(StrategyExecutorError):
        await place_strategy_orders(
            db, signal=seeded["signal"], strategy=seeded["strategy"]
        )


@pytest.mark.asyncio
async def test_executor_uses_ai_recommended_lots(
    db: AsyncSession, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AI says 2 lots; strategy max=4 — executor places 2."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    result = await place_strategy_orders(
        db,
        signal=seeded["signal"],
        strategy=seeded["strategy"],
        recommended_lots=2,
    )
    await db.commit()

    assert result.success
    # 2 entry-leg rows (one per lot)
    assert len(result.execution_ids) == 2

    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    assert pos.total_quantity == 2


@pytest.mark.asyncio
async def test_executor_caps_ai_lots_to_strategy_max(
    db: AsyncSession, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AI says 8 lots; strategy.entry_lots=4 — executor caps to 4."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    # Seeded strategy has entry_lots=4
    result = await place_strategy_orders(
        db,
        signal=seeded["signal"],
        strategy=seeded["strategy"],
        recommended_lots=8,
    )
    await db.commit()

    assert result.success
    assert len(result.execution_ids) == 4

    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    assert pos.total_quantity == 4


@pytest.mark.asyncio
async def test_executor_rejects_zero_recommended_lots(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """recommended_lots=0 means the validator rejected — should never reach exec."""
    with pytest.raises(StrategyExecutorError):
        await place_strategy_orders(
            db,
            signal=seeded["signal"],
            strategy=seeded["strategy"],
            recommended_lots=0,
        )


# ═══════════════════════════════════════════════════════════════════════
# Position manager — state transitions
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def open_position(db: AsyncSession, seeded: dict[str, Any]) -> StrategyPosition:
    """Long position: entry 100, target 101, SL 99, trail 0.5."""
    monkeypatch_paper = "true"
    os.environ["STRATEGY_PAPER_MODE"] = monkeypatch_paper
    get_settings.cache_clear()

    result = await place_strategy_orders(
        db, signal=seeded["signal"], strategy=seeded["strategy"]
    )
    await db.commit()
    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    return pos


@pytest.mark.asyncio
async def test_apply_tick_books_partial_profit(
    db: AsyncSession, open_position: StrategyPosition
) -> None:
    """LTP at target → 2 lots booked partial, status=partial."""
    outcome = await apply_tick(db, position=open_position, ltp=Decimal("101"))
    await db.commit()

    assert "partial_target" in outcome.triggered
    assert open_position.remaining_quantity == 2
    assert open_position.status == "partial"


@pytest.mark.asyncio
async def test_apply_tick_hits_hard_sl_closes_all(
    db: AsyncSession, open_position: StrategyPosition
) -> None:
    """LTP at hard SL → entire position closed, no partial."""
    outcome = await apply_tick(db, position=open_position, ltp=Decimal("99"))
    await db.commit()

    assert "hard_sl" in outcome.triggered
    assert open_position.remaining_quantity == 0
    assert open_position.status == "closed"
    assert outcome.closed is True


@pytest.mark.asyncio
async def test_apply_tick_trailing_sl_after_high(
    db: AsyncSession, open_position: StrategyPosition
) -> None:
    """Walk price up to 102, then back to 101.4 → trail (102-0.5=101.5) breached."""
    # First tick: drives partial profit at 101
    await apply_tick(db, position=open_position, ltp=Decimal("101"))
    # Push higher to 102 — updates highest_price_seen
    await apply_tick(db, position=open_position, ltp=Decimal("102"))
    # Pullback to 101.4 — breaches trail (102 - 0.5)
    outcome = await apply_tick(db, position=open_position, ltp=Decimal("101.4"))
    await db.commit()

    assert "trailing_sl" in outcome.triggered
    assert open_position.remaining_quantity == 0
    assert open_position.status == "closed"


# ═══════════════════════════════════════════════════════════════════════
# Kill switch
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_close_position_now_writes_exit_and_marks_closed(
    db: AsyncSession, open_position: StrategyPosition
) -> None:
    """Force-close path: one exit row, status=closed, remaining=0."""
    starting_qty = open_position.remaining_quantity
    exit_row = await close_position_now(
        db, position=open_position, reason="kill_switch", ltp=Decimal("100.5")
    )
    await db.commit()

    assert exit_row.quantity == starting_qty
    assert exit_row.leg_role == "kill_switch"
    assert exit_row.side == OrderSide.SELL.value  # opposite of long entry
    assert open_position.status == "closed"
    assert open_position.remaining_quantity == 0


@pytest.mark.asyncio
async def test_close_position_now_idempotent_when_already_closed(
    db: AsyncSession, open_position: StrategyPosition
) -> None:
    """Calling close on an already-closed position is a no-op."""
    open_position.remaining_quantity = 0
    open_position.status = "closed"
    await db.commit()

    exit_row = await close_position_now(
        db, position=open_position, reason="kill_switch"
    )
    # No new row should be flushed; the returned object has quantity=0
    assert exit_row.quantity == 0


# ═══════════════════════════════════════════════════════════════════════
# Paper-mode LTP simulator + position-manager loop
# ═══════════════════════════════════════════════════════════════════════


def _walk_until(
    position: StrategyPosition,
    *,
    rng,
    predicate,
    max_ticks: int = 5000,
    volatility: float = 0.005,
) -> tuple[int, Decimal]:
    """Step the simulator until ``predicate(price)`` is True or budget exhausted."""
    last = position.avg_entry_price
    for i in range(max_ticks):
        last = simulate_paper_ltp(position, rng=rng, volatility=volatility)
        position.best_price = last
        if predicate(last):
            return i + 1, last
    return max_ticks, last


@pytest.mark.asyncio
async def test_paper_ltp_drifts_to_target(open_position: StrategyPosition) -> None:
    """Positive bias toward target_price — must reach it within budget."""
    import random

    rng = random.Random(7)
    open_position.best_price = open_position.avg_entry_price
    ticks, last = _walk_until(
        open_position,
        rng=rng,
        predicate=lambda p: p >= open_position.target_price,
    )
    assert last >= open_position.target_price, (ticks, last)
    assert ticks < 5000


@pytest.mark.asyncio
async def test_paper_ltp_can_hit_sl(open_position: StrategyPosition) -> None:
    """Adverse seeds must be capable of walking the price down to SL."""
    import random

    rng = random.Random(123456789)
    open_position.best_price = open_position.avg_entry_price
    open_position.target_price = None  # remove drift bias for this test
    ticks, last = _walk_until(
        open_position,
        rng=rng,
        predicate=lambda p: p <= open_position.stop_loss_price,
    )
    assert last <= open_position.stop_loss_price, (ticks, last)
    assert ticks < 5000


@pytest.mark.asyncio
async def test_position_manager_partial_books_at_target(
    db: AsyncSession,
    open_position: StrategyPosition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: paper loop with a deterministic simulator hits target → partial."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    # Pin the simulator output to the target so the loop fires partial_target
    # on the first tick — keeps the test fast and deterministic without
    # dropping the real loop wiring.
    target = open_position.target_price
    monkeypatch.setattr(
        position_manager,
        "simulate_paper_ltp",
        lambda pos, **_kw: target,
    )

    outcomes = await manage_open_positions(db)
    await db.commit()

    assert len(outcomes) == 1
    assert "partial_target" in outcomes[0].triggered
    refreshed = await db.get(StrategyPosition, open_position.id)
    assert refreshed is not None
    assert refreshed.status == "partial"
    assert refreshed.remaining_quantity == 2
