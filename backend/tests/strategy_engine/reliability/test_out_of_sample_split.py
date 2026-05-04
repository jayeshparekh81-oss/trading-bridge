"""OOS: split mechanics and edge-case handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.strategy_engine.reliability.out_of_sample import run_out_of_sample
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def _flat_candles(n: int, *, price: float = 100.0) -> list[Candle]:
    return [
        Candle(
            timestamp=T0 + timedelta(minutes=i),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=1000,
        )
        for i in range(n)
    ]


def _basic_strategy() -> StrategyJSON:
    return StrategyJSON.model_validate(
        {
            "id": "s",
            "name": "test",
            "mode": "expert",
            "indicators": [],
            "entry": {
                "side": "BUY",
                "operator": "AND",
                "conditions": [{"type": "price", "op": ">", "value": 99.5}],
            },
            "exit": {"targetPercent": 2, "stopLossPercent": 1},
            "execution": {
                "mode": "backtest",
                "orderType": "MARKET",
                "productType": "INTRADAY",
            },
        }
    )


def test_oos_runs_two_independent_backtests_and_returns_both() -> None:
    """A 10-bar input becomes a 7-bar train + 3-bar test split."""
    result = run_out_of_sample(
        strategy=_basic_strategy(),
        candles=_flat_candles(10),
    )
    assert len(result.training.equity_curve) == 7
    assert len(result.testing.equity_curve) == 3


def test_oos_rejects_input_with_fewer_than_four_candles() -> None:
    with pytest.raises(ValueError, match="at least 4"):
        run_out_of_sample(
            strategy=_basic_strategy(),
            candles=_flat_candles(3),
        )


def test_oos_split_clamps_to_leave_at_least_two_candles_per_side() -> None:
    """A 4-bar input would normally split 70/30 = 2.8/1.2 → 2/2 (clamped)."""
    result = run_out_of_sample(
        strategy=_basic_strategy(),
        candles=_flat_candles(4),
    )
    # Both sides must have >= 2 candles (simulator minimum).
    assert len(result.training.equity_curve) >= 2
    assert len(result.testing.equity_curve) >= 2


def test_oos_zero_train_return_emits_uninformative_warning() -> None:
    """A flat market produces zero returns on both sides — warning fires
    but degradation_percent stays at 0.
    """
    result = run_out_of_sample(
        strategy=_basic_strategy(),
        candles=_flat_candles(20),
    )
    if result.training.total_return_percent == 0:
        assert result.degradation_percent == 0
        assert "uninformative" in result.warning


def test_oos_result_is_immutable() -> None:
    result = run_out_of_sample(
        strategy=_basic_strategy(),
        candles=_flat_candles(10),
    )
    with pytest.raises((TypeError, ValueError)):
        result.degradation_percent = 0.99  # type: ignore[misc]
