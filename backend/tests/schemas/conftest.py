"""Fixtures for schemas/ tests.

The candle schemas are pure Pydantic — no I/O, no fixtures needed for
the happy path. This conftest is here to anchor the subdir as a pytest
target and to provide a couple of shared sample-data fixtures used by
multiple test cases.
"""

from __future__ import annotations

import pytest

from app.schemas.candle import Candle, TickData, Timeframe
from tests._chart_helpers import make_candle, make_tick


@pytest.fixture
def sample_tick() -> TickData:
    """A valid :class:`TickData` for round-trip serialization tests."""
    return make_tick()


@pytest.fixture
def sample_candle() -> Candle:
    """A valid :class:`Candle` for OHLC invariant tests."""
    return make_candle(timeframe=Timeframe.FIVE_MIN)
