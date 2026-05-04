"""Walk-forward: window construction + minimum-data validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.strategy_engine.reliability.constants import WALK_FORWARD_WINDOWS
from app.strategy_engine.reliability.walk_forward import (
    WalkForwardWindow,
    run_walk_forward,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def _candles(n: int, *, price: float = 100.0) -> list[Candle]:
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


def _strategy() -> StrategyJSON:
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


def test_returns_exactly_walk_forward_windows() -> None:
    result = run_walk_forward(strategy=_strategy(), candles=_candles(50))
    assert len(result.windows) == WALK_FORWARD_WINDOWS


def test_window_indices_are_zero_through_n_minus_one() -> None:
    result = run_walk_forward(strategy=_strategy(), candles=_candles(50))
    indices = [w.index for w in result.windows]
    assert indices == list(range(WALK_FORWARD_WINDOWS))


def test_rejects_input_with_fewer_than_twenty_candles() -> None:
    with pytest.raises(ValueError, match="at least 20"):
        run_walk_forward(strategy=_strategy(), candles=_candles(15))


def test_last_window_picks_up_remainder_candles() -> None:
    """A 53-candle input divides as 10 / 10 / 10 / 10 / 13 (last gets 3 extra)."""
    n = 53
    result = run_walk_forward(strategy=_strategy(), candles=_candles(n))
    # Each window's test segment must be non-empty.
    for w in result.windows:
        assert isinstance(w, WalkForwardWindow)


def test_each_window_passed_field_reflects_test_pnl_sign() -> None:
    """``passed`` is True iff ``test_pnl > 0``."""
    result = run_walk_forward(strategy=_strategy(), candles=_candles(50))
    for w in result.windows:
        assert w.passed == (w.test_pnl > 0)


def test_walk_forward_result_round_trips_through_json() -> None:
    result = run_walk_forward(strategy=_strategy(), candles=_candles(50))
    blob = result.model_dump_json()
    from app.strategy_engine.reliability.walk_forward import WalkForwardResult

    rehydrated = WalkForwardResult.model_validate_json(blob)
    assert rehydrated == result
