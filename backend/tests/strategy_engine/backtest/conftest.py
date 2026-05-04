"""Shared fixtures for the backtest test suite.

Helpers here are deliberately lean — each test file builds its own
specific candle sequences so the test reads top-to-bottom without
hopping into a fixture file. The shared bits below are limited to:

    * ``T0`` — a stable starting timestamp every test reuses.
    * ``make_candle`` — minimal-keystroke OHLCV builder.
    * ``make_strategy`` — canonical Phase 1 schema with overrides.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def make_candle(
    *,
    minutes: int = 0,
    open_: float = 100.0,
    high: float = 100.0,
    low: float = 100.0,
    close: float = 100.0,
    volume: float = 1000.0,
    base_ts: datetime = T0,
) -> Candle:
    """Build one Candle at ``base_ts + minutes`` minutes."""
    return Candle(
        timestamp=base_ts + timedelta(minutes=minutes),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def make_flat_candles(n: int, *, price: float = 100.0) -> list[Candle]:
    """``n`` consecutive flat candles at ``price``."""
    return [
        make_candle(minutes=i, open_=price, high=price, low=price, close=price) for i in range(n)
    ]


def make_strategy(
    *,
    entry_conditions: list[dict[str, Any]] | None = None,
    exit_block: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    indicators: list[dict[str, Any]] | None = None,
    side: str = "BUY",
) -> StrategyJSON:
    """Build a StrategyJSON with sensible defaults for backtest tests."""
    payload: dict[str, Any] = {
        "id": "test_strategy",
        "name": "test",
        "mode": "expert",
        "indicators": indicators or [],
        "entry": {
            "side": side,
            "operator": "AND",
            "conditions": entry_conditions or [{"type": "price", "op": ">", "value": 99.5}],
        },
        "exit": exit_block or {"targetPercent": 2, "stopLossPercent": 1},
        "risk": risk or {},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    return StrategyJSON.model_validate(payload)
