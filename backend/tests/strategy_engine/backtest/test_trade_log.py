"""Trade + EquityPoint tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.strategy_engine.backtest.trade_log import EquityPoint, Trade
from app.strategy_engine.schema.strategy import Side

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def test_trade_minimum_required_fields() -> None:
    trade = Trade(
        entry_time=T0,
        exit_time=T0 + timedelta(minutes=15),
        side=Side.BUY,
        entry_price=100.0,
        exit_price=102.0,
        quantity=10,
        pnl=20.0,
        exit_reason="target",
    )
    assert trade.entry_reasons == ()
    assert trade.side is Side.BUY


def test_trade_with_entry_reasons_round_trips() -> None:
    reasons = ("indicator: ema_20 > ema_50", "price: > 100")
    trade = Trade(
        entry_time=T0,
        exit_time=T0 + timedelta(minutes=15),
        side=Side.BUY,
        entry_price=100,
        exit_price=102,
        quantity=10,
        pnl=20,
        exit_reason="target",
        entry_reasons=reasons,
    )
    dumped = trade.model_dump()
    rehydrated = Trade.model_validate(dumped)
    assert rehydrated == trade


def test_trade_rejects_zero_or_negative_prices() -> None:
    with pytest.raises(ValidationError):
        Trade(
            entry_time=T0,
            exit_time=T0,
            side=Side.BUY,
            entry_price=0,
            exit_price=100,
            quantity=10,
            pnl=0,
            exit_reason="x",
        )
    with pytest.raises(ValidationError):
        Trade(
            entry_time=T0,
            exit_time=T0,
            side=Side.BUY,
            entry_price=100,
            exit_price=-1,
            quantity=10,
            pnl=0,
            exit_reason="x",
        )


def test_trade_rejects_zero_quantity() -> None:
    with pytest.raises(ValidationError):
        Trade(
            entry_time=T0,
            exit_time=T0,
            side=Side.BUY,
            entry_price=100,
            exit_price=102,
            quantity=0,
            pnl=0,
            exit_reason="x",
        )


def test_trade_rejects_extra_fields() -> None:
    """``extra='forbid'`` rejects unknown keys at validation time."""
    payload = {
        "entry_time": T0,
        "exit_time": T0,
        "side": "BUY",
        "entry_price": 100,
        "exit_price": 102,
        "quantity": 10,
        "pnl": 20,
        "exit_reason": "x",
        "unexpected": "oops",
    }
    with pytest.raises(ValidationError):
        Trade.model_validate(payload)


def test_trade_is_frozen() -> None:
    trade = Trade(
        entry_time=T0,
        exit_time=T0,
        side=Side.BUY,
        entry_price=100,
        exit_price=102,
        quantity=10,
        pnl=20,
        exit_reason="target",
    )
    with pytest.raises((TypeError, ValueError)):
        trade.pnl = 999  # type: ignore[misc]


def test_equity_point_basic() -> None:
    point = EquityPoint(timestamp=T0, equity=100_500.0)
    assert point.equity == 100_500.0


def test_equity_point_allows_negative_equity() -> None:
    """A blown-up account is still representable — no constraint on equity sign."""
    EquityPoint(timestamp=T0, equity=-5000.0)


def test_equity_point_is_frozen() -> None:
    point = EquityPoint(timestamp=T0, equity=100_000)
    with pytest.raises((TypeError, ValueError)):
        point.equity = 999  # type: ignore[misc]
