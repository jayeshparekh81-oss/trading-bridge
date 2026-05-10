"""Fixtures for the Paper Trading Engine tests.

The engine holds session state in a module-level dict; ``clear_state``
resets it before every test so the suite is order-independent.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.strategy_engine.paper_trading import clear_paper_state
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON


@pytest.fixture(autouse=True)
def _reset_paper_state() -> Iterator[None]:
    """Drop every in-memory session before AND after each test.

    ``autouse=True`` so individual tests don't have to remember; the
    engine's module-level dict is global and would otherwise bleed
    state between tests run in the same interpreter.
    """
    clear_paper_state()
    yield
    clear_paper_state()


T0 = datetime(2026, 5, 5, 9, 30, tzinfo=UTC)


def make_candle(
    *,
    minutes: int = 0,
    open_: float = 100.0,
    high: float | None = None,
    low: float | None = None,
    close: float | None = None,
    volume: float = 1000.0,
    base_ts: datetime = T0,
) -> Candle:
    """Build one Candle. ``high``/``low``/``close`` default to ``open``."""
    h = high if high is not None else open_
    lw = low if low is not None else open_
    c = close if close is not None else open_
    return Candle(
        timestamp=base_ts + timedelta(minutes=minutes),
        open=open_,
        high=h,
        low=lw,
        close=c,
        volume=volume,
    )


def make_strategy(
    *,
    entry_conditions: list[dict[str, Any]] | None = None,
    exit_block: dict[str, Any] | None = None,
    side: str = "BUY",
    indicators: list[dict[str, Any]] | None = None,
) -> StrategyJSON:
    """Build a StrategyJSON with sensible defaults for paper-trading tests."""
    payload: dict[str, Any] = {
        "id": "paper_test_strategy",
        "name": "Paper test strategy",
        "mode": "expert",
        "indicators": indicators or [],
        "entry": {
            "side": side,
            "operator": "AND",
            "conditions": entry_conditions
            or [{"type": "price", "op": ">", "value": 99.5}],
        },
        "exit": exit_block or {"targetPercent": 2.0, "stopLossPercent": 1.0},
        "risk": {},
        "execution": {
            "mode": "paper",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    return StrategyJSON.model_validate(payload)


def fixed_user_id() -> uuid.UUID:
    """Stable UUID so multiple test runs compare apples-to-apples."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")
