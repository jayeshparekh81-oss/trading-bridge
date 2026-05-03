"""Pine v4.8.1 qty-as-lots interpretation tests.

Pine emits ``qty`` in LOTS (server_final30mar.py convention). Without
the mapper / executor multiplying by lot_size, a Pine signal of qty=4
on BSE Ltd. would either be rejected by the lot-multiple validator
(live mode, lot_size=375 → 4 % 375 ≠ 0) or silently fire 4 contracts
instead of 1500 (paper mode, default lot_size=1).

These tests pin the post-fix behaviour: mapper sets
``quantity_unit='lots'``, executor multiplies before contract-validation.
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

from app.brokers import dhan as dhan_mod
from app.core.config import get_settings
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.schemas.broker import BrokerName
from app.services.pine_mapper import map_to_tradetri_payload
from app.services.strategy_executor import (
    StrategyExecutorError,
    place_strategy_orders,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(autouse=True)
async def _patch_dhan_scrip_master() -> None:
    """Seed the in-process Dhan scrip-master cache so the Pine mapper's
    best-effort lot_size_hint lookup hits in paper-mode tests."""
    dhan_mod._SCRIP_MASTER._by_symbol = {
        ("BSE-MAY2026-FUT", "NSE_FNO"): "66109",
        ("NIFTY-MAY2026-FUT", "NSE_FNO"): "66071",
    }
    dhan_mod._SCRIP_MASTER._by_id = {
        "66109": ("BSE-MAY2026-FUT", "NSE_FNO"),
        "66071": ("NIFTY-MAY2026-FUT", "NSE_FNO"),
    }
    dhan_mod._SCRIP_MASTER._lot_sizes = {"66109": 375, "66071": 65}
    dhan_mod._SCRIP_MASTER._loaded_at = datetime.now(UTC)
    yield
    dhan_mod._SCRIP_MASTER._by_symbol.clear()
    dhan_mod._SCRIP_MASTER._by_id.clear()
    dhan_mod._SCRIP_MASTER._lot_sizes.clear()
    dhan_mod._SCRIP_MASTER._loaded_at = None


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
async def seeded_strategy(db: AsyncSession) -> dict[str, Any]:
    """User + DHAN credential + strategy entry_lots=4, partial_profit_lots=2."""
    user = User(email="pine-qty@example.com", password_hash="x", is_active=True)
    db.add(user)
    await db.flush()

    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.DHAN,
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
        name="bse-pine-qty-test",
        broker_credential_id=cred.id,
        entry_lots=4,
        partial_profit_lots=2,
        ai_validation_enabled=False,
        is_active=True,
        exit_strategy_type="direct_exit",
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return {"user_id": user.id, "credential_id": cred.id, "strategy": strategy}


def _pine_payload(*, qty: int, action: str = "ENTRY", pine_type: str = "LONG_ENTRY") -> dict[str, Any]:
    return {
        "action": action,
        "type": pine_type,
        "qty": qty,
        "useDhan": True,
        "indicators": {"PriceSpd": 5.0, "RSI": 60.0, "ATR": 5.0},
        "symbol": "BSE-May2026-FUT",
        "price": 3800,
    }


def _build_signal_from_pine(
    seeded: dict[str, Any], *, qty: int, action: str = "ENTRY",
    pine_type: str = "LONG_ENTRY",
) -> StrategySignal:
    """Run pine_mapper + persist as a StrategySignal (mirrors webhook flow)."""
    raw = _pine_payload(qty=qty, action=action, pine_type=pine_type)
    mapped = map_to_tradetri_payload(raw, seeded["strategy"])
    # Webhook handler uppercases symbol via Pydantic field_validator; do
    # the same here so position lookup matches.
    mapped["symbol"] = mapped["symbol"].upper()
    return StrategySignal(
        user_id=seeded["user_id"],
        strategy_id=seeded["strategy"].id,
        raw_payload=mapped,
        symbol=mapped["symbol"],
        action=mapped["action"],
        quantity=mapped["quantity"],
        order_type="market",
        status="received",
    )


# ═══════════════════════════════════════════════════════════════════════
# 1. Pine qty=4 lots → 1500 contracts (BSE lot_size=375)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_pine_qty_4_lots_becomes_1500_contracts_for_bse_375(
    db: AsyncSession, seeded_strategy: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The headline fix: Pine qty=4 → 1500 contracts (4 × 375)."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    sig = _build_signal_from_pine(seeded_strategy, qty=4)
    db.add(sig)
    await db.flush()
    # Sanity — mapper tagged it correctly
    assert sig.raw_payload["quantity_unit"] == "lots"
    assert sig.raw_payload["lot_size_hint"] == 375
    assert sig.quantity == 4  # raw lots

    result = await place_strategy_orders(
        db, signal=sig, strategy=seeded_strategy["strategy"]
    )
    await db.commit()

    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    assert pos.total_quantity == 1500  # = 4 × 375
    assert pos.remaining_quantity == 1500
    # 4 lots → 4 entry-leg rows of 375 each
    assert len(result.execution_ids) == 4


# ═══════════════════════════════════════════════════════════════════════
# 2. Pine qty=2 lots → 750 contracts
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_pine_qty_2_lots_becomes_750_contracts(
    db: AsyncSession, seeded_strategy: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    sig = _build_signal_from_pine(seeded_strategy, qty=2)
    db.add(sig)
    await db.flush()

    result = await place_strategy_orders(
        db, signal=sig, strategy=seeded_strategy["strategy"]
    )
    await db.commit()

    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    assert pos.total_quantity == 750  # = 2 × 375
    assert len(result.execution_ids) == 2


# ═══════════════════════════════════════════════════════════════════════
# 3. Pine qty=1 lot rejected as odd for partial-profit strategy
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_pine_qty_1_lot_rejected_as_odd_for_partial_profit_strategy(
    db: AsyncSession, seeded_strategy: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """1 lot → 375 contracts → 1 lot count → odd → even-lot rule rejects.

    The strategy.partial_profit_lots > 0 flag triggers the even-lot
    requirement: half of 1 lot can't be cleanly booked at target.
    """
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    sig = _build_signal_from_pine(seeded_strategy, qty=1)
    db.add(sig)
    await db.flush()

    with pytest.raises(StrategyExecutorError, match="even lot count"):
        await place_strategy_orders(
            db, signal=sig, strategy=seeded_strategy["strategy"]
        )


# ═══════════════════════════════════════════════════════════════════════
# 4. Pine PARTIAL flow unchanged — closePct on remaining_quantity
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_pine_partial_action_unchanged_uses_closePct_on_remaining(
    db: AsyncSession, seeded_strategy: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """PARTIAL doesn't carry qty — closePct% of position.remaining_quantity.

    The lots→contracts conversion is purely an ENTRY concern; PARTIAL
    looks up the existing position's remaining_quantity (already in
    contracts) and applies closePct directly.
    """
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    # Open position via Pine ENTRY: qty=2 lots → 750 contracts
    entry_sig = _build_signal_from_pine(seeded_strategy, qty=2)
    db.add(entry_sig)
    await db.flush()
    entry_result = await place_strategy_orders(
        db, signal=entry_sig, strategy=seeded_strategy["strategy"]
    )
    await db.commit()
    pos = await db.get(StrategyPosition, entry_result.position_id)
    assert pos is not None and pos.total_quantity == 750

    # Pine PARTIAL with closePct=50 — should close 375 (50% of 750), not
    # rely on a qty field in the payload.
    raw_partial = {
        "action": "PARTIAL",
        "type": "LONG_PARTIAL",
        "qty": 0,  # legacy/ignored — server_final30mar uses closePct path
        "closePct": 50,
        "useDhan": True,
        "indicators": {},
        "symbol": "BSE-May2026-FUT",
        "price": 3850,
    }
    mapped_partial = map_to_tradetri_payload(raw_partial, seeded_strategy["strategy"])
    mapped_partial["symbol"] = mapped_partial["symbol"].upper()
    assert mapped_partial["closePct"] == 50.0
    assert mapped_partial["action"] == "PARTIAL"

    partial_sig = StrategySignal(
        user_id=seeded_strategy["user_id"],
        strategy_id=seeded_strategy["strategy"].id,
        raw_payload=mapped_partial,
        symbol=mapped_partial["symbol"],
        action="PARTIAL",
        quantity=None,  # PARTIAL doesn't carry quantity
        order_type="market",
        status="received",
    )
    db.add(partial_sig)
    await db.flush()

    from app.services import direct_exit

    result = await direct_exit.execute_partial(
        db, signal=partial_sig, strategy=seeded_strategy["strategy"]
    )
    await db.commit()

    assert result["status"] == "executed"
    assert result["close_qty"] == 375  # 50% of 750
    assert result["remaining"] == 375


# ═══════════════════════════════════════════════════════════════════════
# 5. Native (non-Pine) callers can opt out by sending quantity_unit='contracts'
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_pine_qty_already_in_contracts_via_explicit_unit_field(
    db: AsyncSession, seeded_strategy: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A native caller (or a future Pine variant) can declare
    ``quantity_unit='contracts'`` to bypass the lots×lot_size multiplication.

    Sends quantity=750 with unit='contracts' on the BSE-Ltd strategy.
    Result: 750 contracts (NOT 750×375).
    """
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    sig = StrategySignal(
        user_id=seeded_strategy["user_id"],
        strategy_id=seeded_strategy["strategy"].id,
        raw_payload={
            "action": "ENTRY",
            "side": "long",
            "symbol": "BSE-MAY2026-FUT",
            "price": 3800,
            "lot_size_hint": 375,
            "quantity_unit": "contracts",
            "signal_id": "native-contracts-test",
        },
        symbol="BSE-MAY2026-FUT",
        action="ENTRY",
        quantity=750,
        order_type="market",
        status="received",
    )
    db.add(sig)
    await db.flush()

    result = await place_strategy_orders(
        db, signal=sig, strategy=seeded_strategy["strategy"]
    )
    await db.commit()

    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    # 750 stayed as 750 — no multiplication because unit='contracts'.
    assert pos.total_quantity == 750
    assert len(result.execution_ids) == 2  # 2 lots × 375


# ═══════════════════════════════════════════════════════════════════════
# Bonus: mapper output integrity — quantity_unit + lot_size_hint always set
# ═══════════════════════════════════════════════════════════════════════


def test_pine_mapper_output_carries_quantity_unit_and_lot_size_hint() -> None:
    """Every Pine ENTRY mapped output must carry quantity_unit='lots'
    and lot_size_hint (when the symbol is in the cache)."""
    raw = _pine_payload(qty=4)
    mapped = map_to_tradetri_payload(raw, strategy=None)
    assert mapped["quantity"] == 4
    assert mapped["quantity_unit"] == "lots"
    assert mapped["lot_size_hint"] == 375
