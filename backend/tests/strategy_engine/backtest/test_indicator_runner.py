"""Short-window padding contract for ``precompute_indicators``.

Phase 1 calculation functions return ``[]`` when the configured period
exceeds the available candle count. Phase 3's simulator looks up values
by ``(indicator_id, bar_index)`` via :func:`values_at`, which raises
``IndexError`` against an empty series — surfacing as a crash rather
than the intended "warmup-style" None semantics.

These two tests pin the runner's responsibility: regardless of what a
calc returns, every series stored under an indicator id (and any
multi-output sub-id) must be exactly ``len(candles)`` long, with
``None`` filling the gaps.
"""

from __future__ import annotations

from app.strategy_engine.backtest.indicator_runner import (
    precompute_indicators,
    values_at,
)
from tests.strategy_engine.backtest.conftest import make_flat_candles, make_strategy


def test_single_output_short_window_pads_to_candle_length() -> None:
    """SMA with period > len(candles) is padded to N Nones, not [].

    Without this fix, ``values_at(0)`` would IndexError against the
    empty list returned by Phase 1's ``sma`` calc when 10 > 5.
    """
    candles = make_flat_candles(5, price=100.0)
    strategy = make_strategy(
        indicators=[{"id": "sma_long", "type": "sma", "params": {"period": 10}}],
    )

    series, warnings = precompute_indicators(candles, strategy)

    assert series["sma_long"] == [None] * 5
    assert warnings == []
    # Hot-loop access at every bar must not raise.
    for i in range(len(candles)):
        assert values_at(series, i) == {"sma_long": None}


def test_multi_output_short_window_pads_primary_and_sub_series() -> None:
    """MACD with slow_period > len(candles) pads primary AND each sub-series.

    Phase 1 MACD returns ``([], [], [])`` when slow exceeds candle count.
    The runner must pad the primary (``macd_default``) and every dotted
    sub-id (``.macd``, ``.signal``, ``.histogram``) to ``len(candles)``
    so the simulator's per-bar lookups stay total. The multi-output
    warning still fires — it describes the indicator shape, not the
    presence of data.
    """
    candles = make_flat_candles(5, price=100.0)
    strategy = make_strategy(
        indicators=[
            {
                "id": "macd_default",
                "type": "macd",
                "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            }
        ],
    )

    series, warnings = precompute_indicators(candles, strategy)

    expected_padding = [None] * 5
    assert series["macd_default"] == expected_padding
    assert series["macd_default.macd"] == expected_padding
    assert series["macd_default.signal"] == expected_padding
    assert series["macd_default.histogram"] == expected_padding
    assert len(warnings) == 1
    assert "macd_default" in warnings[0]
    # Per-bar access must succeed for every stored id.
    snapshot = values_at(series, 4)
    assert snapshot == {
        "macd_default": None,
        "macd_default.macd": None,
        "macd_default.signal": None,
        "macd_default.histogram": None,
    }
