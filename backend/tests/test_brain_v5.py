"""Server v5 brain port + brain-wins precedence tests.

Pinned post Sun 2026-05-03 update:
  * 17-indicator weights rebalanced to server's v5 values.
  * 5 new indicators added (ADX/MFI/STDir/OIBuild/MACDH).
  * SHORT_THRESHOLD lowered 55→51.
  * Brain qty authoritative when ``strategy.ai_validation_enabled=True``;
    overrides Pine's ``signal.quantity`` (server-style filter).

These tests pin the contract; existing test_strategy_engine.py covers
the broader scoring + executor flow.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio

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
from app.schemas.broker import BrokerName
from app.services.ai_validator import (
    AVG_VALUES,
    LONG_THRESHOLD,
    LONG_THRESHOLD_4LOT,
    LONG_W,
    SHORT_THRESHOLD,
    SHORT_W,
    _long_passed,
    _short_passed,
    compute_score,
)
from app.services.strategy_executor import place_strategy_orders


# ═══════════════════════════════════════════════════════════════════════
# 1-4. Weight + threshold pins
# ═══════════════════════════════════════════════════════════════════════


def test_v5_weights_long_match_server() -> None:
    """LONG_W must equal server_final30mar.py v5 verbatim."""
    expected = {
        "PriceSpd": 13.5, "ATR": 11.0, "LongMA": 8.0, "GaussL": 7.7,
        "SlowMA": 7.6, "GaussS": 7.6, "FastMA": 7.6, "VWAPDist": 5.7,
        "BullGap": 4.6, "Squeeze": 3.6, "BodyPct": 3.2, "Vol": 1.6,
        "DeltaPwr": 1.4, "BearGap": 1.2, "RVOL": 0.8, "OFInten": 0.5,
        "RSI": 0.2,
        "ADX": 5.5, "MFI": 3.5, "STDir": 3.0, "OIBuild": 3.5, "MACDH": 2.0,
    }
    assert LONG_W == expected


def test_v5_weights_short_match_server() -> None:
    expected = {
        "PriceSpd": 9.3, "ATR": 8.7, "GaussL": 7.8, "LongMA": 7.8,
        "SlowMA": 7.8, "GaussS": 7.8, "FastMA": 7.8, "BearGap": 4.6,
        "Vol": 3.9, "Squeeze": 3.9, "VWAPDist": 3.8, "RSI": 3.0,
        "BullGap": 2.8, "RVOL": 2.4, "OFInten": 2.0, "DeltaPwr": 1.1,
        "BodyPct": 0.8,
        "ADX": 5.5, "MFI": 3.5, "STDir": 3.0, "OIBuild": 3.5, "MACDH": 2.0,
    }
    assert SHORT_W == expected


def test_avg_values_includes_v5_indicators() -> None:
    for k, v in [("ADX", 22.0), ("MFI", 50.0), ("STDir", 0.0),
                 ("OIBuild", 0.0), ("MACDH", 0.0)]:
        assert AVG_VALUES[k] == v


def test_short_threshold_updated_to_51() -> None:
    assert SHORT_THRESHOLD == 51.0
    assert LONG_THRESHOLD == 51.0
    assert LONG_THRESHOLD_4LOT == 85.0


# ═══════════════════════════════════════════════════════════════════════
# 5-8. v5 indicator pass-rule unit tests
# ═══════════════════════════════════════════════════════════════════════


def test_v5_indicator_pass_rules_long() -> None:
    """LONG-side pass rules for the 5 v5 indicators."""
    # ADX >= 20 passes
    assert _long_passed("ADX", 25.0, AVG_VALUES["ADX"]) is True
    assert _long_passed("ADX", 19.9, AVG_VALUES["ADX"]) is False
    # MFI in [40, 80] passes
    assert _long_passed("MFI", 60.0, AVG_VALUES["MFI"]) is True
    assert _long_passed("MFI", 39.9, AVG_VALUES["MFI"]) is False
    assert _long_passed("MFI", 80.1, AVG_VALUES["MFI"]) is False
    # STDir > 0 passes
    assert _long_passed("STDir", 1.0, AVG_VALUES["STDir"]) is True
    assert _long_passed("STDir", 0.0, AVG_VALUES["STDir"]) is False
    # OIBuild >= 1.0 passes
    assert _long_passed("OIBuild", 1.5, AVG_VALUES["OIBuild"]) is True
    assert _long_passed("OIBuild", 0.99, AVG_VALUES["OIBuild"]) is False
    # MACDH > 0 passes
    assert _long_passed("MACDH", 0.1, AVG_VALUES["MACDH"]) is True
    assert _long_passed("MACDH", 0.0, AVG_VALUES["MACDH"]) is False


def test_v5_indicator_pass_rules_short() -> None:
    """SHORT-side pass rules — mirrored direction for STDir/OIBuild/MACDH."""
    # ADX >= 20 same on both sides
    assert _short_passed("ADX", 25.0, AVG_VALUES["ADX"]) is True
    # MFI in [20, 60] for SHORT
    assert _short_passed("MFI", 40.0, AVG_VALUES["MFI"]) is True
    assert _short_passed("MFI", 19.9, AVG_VALUES["MFI"]) is False
    assert _short_passed("MFI", 60.1, AVG_VALUES["MFI"]) is False
    # STDir < 0 for SHORT
    assert _short_passed("STDir", -1.0, AVG_VALUES["STDir"]) is True
    assert _short_passed("STDir", 0.0, AVG_VALUES["STDir"]) is False
    # OIBuild <= -1.0 for SHORT
    assert _short_passed("OIBuild", -1.5, AVG_VALUES["OIBuild"]) is True
    assert _short_passed("OIBuild", -0.99, AVG_VALUES["OIBuild"]) is False
    # MACDH < 0 for SHORT
    assert _short_passed("MACDH", -0.1, AVG_VALUES["MACDH"]) is True
    assert _short_passed("MACDH", 0.0, AVG_VALUES["MACDH"]) is False


def test_score_with_all_22_indicators_passing() -> None:
    """Sanity: full-pass score equals sum of weights (~103.3 for LONG)."""
    indicators = {
        "PriceSpd": 5.0, "ATR": 5.0, "LongMA": 800, "GaussL": 800,
        "SlowMA": 800, "GaussS": 800, "FastMA": 800, "VWAPDist": 1.0,
        "BullGap": 200, "Squeeze": 6.0, "BodyPct": 70, "Vol": 400000,
        "DeltaPwr": 5.0, "BearGap": 110, "RVOL": 2.0, "OFInten": 2.0,
        "RSI": 60.0,
        "ADX": 25, "MFI": 60, "STDir": 1, "OIBuild": 2, "MACDH": 1.5,
    }
    score = compute_score(indicators, "LONG")
    assert score >= 103.0
    assert score <= 103.5


def test_v5_weights_replace_old_values() -> None:
    """Regression guard: the v5 PriceSpd weight is 13.5, not 15.67 (old)."""
    assert LONG_W["PriceSpd"] == 13.5
    assert SHORT_W["PriceSpd"] == 9.3
    # Old values that must NOT be present
    assert LONG_W["PriceSpd"] != 15.67
    assert SHORT_W["PriceSpd"] != 10.86


# ═══════════════════════════════════════════════════════════════════════
# Brain-wins precedence — service-level (DB-backed)
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_ai_enabled(db: AsyncSession) -> dict[str, Any]:
    """Strategy with ai_validation_enabled=True (brain-wins active)."""
    user = User(email="brain-on@example.com", password_hash="x", is_active=True)
    db.add(user)
    await db.flush()
    cred = BrokerCredential(
        user_id=user.id, broker_name=BrokerName.DHAN,
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
        user_id=user.id, name="brain-on", broker_credential_id=cred.id,
        entry_lots=4, partial_profit_lots=2,
        ai_validation_enabled=True,  # ← brain-wins flag ON
        is_active=True, exit_strategy_type="direct_exit",
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return {"user_id": user.id, "strategy": strategy}


@pytest_asyncio.fixture
async def seeded_ai_disabled(db: AsyncSession) -> dict[str, Any]:
    """Strategy with ai_validation_enabled=False (Pine-wins, backward compat)."""
    user = User(email="brain-off@example.com", password_hash="x", is_active=True)
    db.add(user)
    await db.flush()
    cred = BrokerCredential(
        user_id=user.id, broker_name=BrokerName.DHAN,
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
        user_id=user.id, name="brain-off", broker_credential_id=cred.id,
        entry_lots=4, partial_profit_lots=2,
        ai_validation_enabled=False,  # ← AI off
        is_active=True, exit_strategy_type="direct_exit",
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return {"user_id": user.id, "strategy": strategy}


def _signal(seeded: dict[str, Any], *, qty_lots: int) -> StrategySignal:
    """Pine-shaped signal: quantity in lots, lot_size_hint=375."""
    return StrategySignal(
        user_id=seeded["user_id"],
        strategy_id=seeded["strategy"].id,
        raw_payload={
            "action": "ENTRY",
            "side": "long",
            "symbol": "BSE-MAY2026-FUT",
            "quantity_unit": "lots",
            "lot_size_hint": 375,
            "price": 3800,
            "signal_id": f"brain-test-{qty_lots}-{uuid.uuid4().hex[:6]}",
        },
        symbol="BSE-MAY2026-FUT",
        action="ENTRY",
        quantity=qty_lots,
        order_type="market",
        status="received",
    )


@pytest.mark.asyncio
async def test_brain_qty_overrides_pine_qty_when_ai_enabled(
    db: AsyncSession,
    seeded_ai_enabled: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI enabled, Pine sends 2 lots, brain says 4 (high score) → 4 lots fire.

    This is the headline server-style filter: AI re-evaluates Pine's
    signal and can size UP based on its own scoring.
    """
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    sig = _signal(seeded_ai_enabled, qty_lots=2)
    db.add(sig)
    await db.flush()

    # Simulate brain decision: 4 lots from a high score
    result = await place_strategy_orders(
        db, signal=sig, strategy=seeded_ai_enabled["strategy"],
        recommended_lots=4,  # brain's tier
    )
    await db.commit()

    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    # 4 (brain) × 375 = 1500 — NOT 2 × 375 = 750 (Pine)
    assert pos.total_quantity == 1500


@pytest.mark.asyncio
async def test_brain_downsizes_pine_qty_when_score_medium(
    db: AsyncSession,
    seeded_ai_enabled: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI enabled, Pine sends 4 lots, brain returns 2 (medium tier) → 2 fire."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    sig = _signal(seeded_ai_enabled, qty_lots=4)
    db.add(sig)
    await db.flush()

    result = await place_strategy_orders(
        db, signal=sig, strategy=seeded_ai_enabled["strategy"],
        recommended_lots=2,  # brain downsized
    )
    await db.commit()
    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    assert pos.total_quantity == 750  # 2 × 375 not 4 × 375


@pytest.mark.asyncio
async def test_pine_qty_used_when_ai_disabled(
    db: AsyncSession,
    seeded_ai_disabled: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI off → Pine's signal.quantity is authoritative (backward compat)."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    sig = _signal(seeded_ai_disabled, qty_lots=2)
    db.add(sig)
    await db.flush()

    # recommended_lots IS passed but should be ignored because AI is off.
    result = await place_strategy_orders(
        db, signal=sig, strategy=seeded_ai_disabled["strategy"],
        recommended_lots=4,
    )
    await db.commit()
    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    # Pine's 2 lots wins, not brain's 4
    assert pos.total_quantity == 750  # 2 × 375


@pytest.mark.asyncio
async def test_brain_caps_at_strategy_entry_lots_ceiling(
    db: AsyncSession,
    seeded_ai_enabled: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even with AI enabled, brain qty is capped at strategy.entry_lots."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    sig = _signal(seeded_ai_enabled, qty_lots=2)
    db.add(sig)
    await db.flush()

    # Brain wants 8 lots, strategy ceiling is 4 → cap.
    result = await place_strategy_orders(
        db, signal=sig, strategy=seeded_ai_enabled["strategy"],
        recommended_lots=8,
    )
    await db.commit()
    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    # min(8, 4) × 375 = 1500
    assert pos.total_quantity == 1500
