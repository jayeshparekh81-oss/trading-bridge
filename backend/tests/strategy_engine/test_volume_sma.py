"""Volume SMA tests — thin wrapper over SMA so we mostly verify delegation."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.sma import sma
from app.strategy_engine.indicators.calculations.volume_sma import volume_sma


def test_volume_sma_delegates_to_sma() -> None:
    volumes = [1000.0, 2000.0, 3000.0, 4000.0, 5000.0]
    assert volume_sma(volumes, 3) == sma(volumes, 3)


def test_volume_sma_empty_input() -> None:
    assert volume_sma([], 5) == []


def test_volume_sma_default_period_is_twenty() -> None:
    """Registry default is period=20; the function reflects that."""
    volumes = [100.0] * 25
    out = volume_sma(volumes)
    # First 19 positions are None (period-1 warm-up), then 100.0 thereafter.
    assert out[:19] == [None] * 19
    assert out[19:] == [100.0] * 6


def test_volume_sma_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        volume_sma([1.0, 2.0, 3.0], 0)
