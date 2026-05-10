"""Cost model tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.backtest.costs import (
    CostSettings,
    adjust_for_slippage,
    leg_cost,
)
from app.strategy_engine.schema.strategy import Side

# ─── leg_cost ───────────────────────────────────────────────────────────


def test_leg_cost_fixed_only() -> None:
    settings = CostSettings(fixed_cost=20)
    assert leg_cost(price=100, quantity=10, settings=settings) == 20


def test_leg_cost_percent_only() -> None:
    settings = CostSettings(percent_cost=0.05)  # 0.05% of notional
    # Notional = 100 * 10 = 1000; 0.05% = 0.5
    assert leg_cost(price=100, quantity=10, settings=settings) == pytest.approx(0.5)


def test_leg_cost_combines_fixed_and_percent() -> None:
    settings = CostSettings(fixed_cost=20, percent_cost=0.05)
    assert leg_cost(price=100, quantity=10, settings=settings) == pytest.approx(20.5)


def test_leg_cost_zero_when_settings_default() -> None:
    assert leg_cost(price=100, quantity=10, settings=CostSettings()) == 0


def test_leg_cost_rejects_negative_price_or_quantity() -> None:
    settings = CostSettings(fixed_cost=20)
    with pytest.raises(ValueError):
        leg_cost(price=-1, quantity=10, settings=settings)
    with pytest.raises(ValueError):
        leg_cost(price=100, quantity=-1, settings=settings)


def test_leg_cost_zero_quantity_is_just_fixed() -> None:
    """A simulated zero-qty leg still pays the fixed fee — defensive."""
    settings = CostSettings(fixed_cost=20)
    assert leg_cost(price=100, quantity=0, settings=settings) == 20


# ─── adjust_for_slippage ────────────────────────────────────────────────


def test_slippage_zero_is_identity() -> None:
    assert (
        adjust_for_slippage(price=100, side=Side.BUY, leg="entry", settings=CostSettings()) == 100
    )


def test_buy_entry_pays_more() -> None:
    """1% slippage on a 100-rupee BUY entry fills at 101."""
    s = CostSettings(slippage_percent=1.0)
    assert adjust_for_slippage(price=100, side=Side.BUY, leg="entry", settings=s) == pytest.approx(
        101
    )


def test_buy_exit_receives_less() -> None:
    s = CostSettings(slippage_percent=1.0)
    assert adjust_for_slippage(price=100, side=Side.BUY, leg="exit", settings=s) == pytest.approx(
        99
    )


def test_sell_entry_receives_less() -> None:
    s = CostSettings(slippage_percent=1.0)
    assert adjust_for_slippage(price=100, side=Side.SELL, leg="entry", settings=s) == pytest.approx(
        99
    )


def test_sell_exit_pays_more() -> None:
    s = CostSettings(slippage_percent=1.0)
    assert adjust_for_slippage(price=100, side=Side.SELL, leg="exit", settings=s) == pytest.approx(
        101
    )


def test_slippage_rejects_unknown_leg() -> None:
    s = CostSettings(slippage_percent=1.0)
    with pytest.raises(ValueError):
        adjust_for_slippage(price=100, side=Side.BUY, leg="midway", settings=s)


def test_cost_settings_rejects_negative_values() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CostSettings(fixed_cost=-1)
    with pytest.raises(ValidationError):
        CostSettings(percent_cost=-0.01)
    with pytest.raises(ValidationError):
        CostSettings(slippage_percent=-0.5)
