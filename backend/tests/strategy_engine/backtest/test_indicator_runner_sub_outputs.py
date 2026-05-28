"""Runner sub-output emission — Queue MM A2 (synonym resolution).

Covers the additive ``IndicatorConfig.output`` path in
``precompute_indicators`` and the ORB band promotion:

    1. A sub-output config (output set) stores the SELECTED sub-series under
       its own id, matching the parent's dotted sub-id.
    2. ORB now emits ``high``/``low`` band series; an ``orb_15_high`` sub-output
       config resolves to the high band.
    3. Single-output indicators (rsi/ema/sma) are unaffected — no extra keys,
       no multi-output warning (proves the change is additive).
"""

from __future__ import annotations

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.schema.ohlcv import Candle
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

_MACD_PARAMS = {"fast_period": 12, "slow_period": 26, "signal_period": 9}


def _trending(n: int = 60) -> list[Candle]:
    return [
        make_candle(minutes=i, open_=100.0 + i, high=100.5 + i, low=99.5 + i, close=100.0 + i)
        for i in range(n)
    ]


# ─── 1. MACD sub-output selection ──────────────────────────────────────


def test_sub_output_config_selects_named_macd_line() -> None:
    """``signal_line`` (type=macd, output=signal) stores the macd SIGNAL line
    under its own id — identical to the parent's dotted ``.signal`` sub-id —
    and emits no dotted keys / warning of its own."""
    candles = _trending()
    strategy = make_strategy(
        indicators=[
            {"id": "macd_12_26_9", "type": "macd", "params": _MACD_PARAMS},
            {"id": "macd_line", "type": "macd", "params": _MACD_PARAMS, "output": "macd"},
            {"id": "signal_line", "type": "macd", "params": _MACD_PARAMS, "output": "signal"},
            {"id": "macd_histogram", "type": "macd", "params": _MACD_PARAMS, "output": "histogram"},
        ],
    )

    series, warnings = precompute_indicators(candles, strategy)

    assert series["macd_line"] == series["macd_12_26_9.macd"]
    assert series["signal_line"] == series["macd_12_26_9.signal"]
    assert series["macd_histogram"] == series["macd_12_26_9.histogram"]
    # Sub-output configs don't re-emit their own dotted sub-ids or warnings.
    assert not any(k.startswith(("macd_line.", "signal_line.", "macd_histogram.")) for k in series)
    for sub_id in ("macd_line", "signal_line", "macd_histogram"):
        assert not any(sub_id in w for w in warnings)


# ─── 2. ORB band promotion ─────────────────────────────────────────────


def test_orb_emits_high_low_bands_and_sub_output_resolves() -> None:
    """ORB now emits ``high``/``low`` band series; an ``orb_15_high`` sub-output
    config picks the high band. Bars within the 15-min opening window are None;
    later bars carry the range high."""
    candles = _trending(40)  # 1-min bars, single session
    strategy = make_strategy(
        indicators=[
            {"id": "orb_15", "type": "opening_range_breakout", "params": {"range_minutes": 15}},
            {
                "id": "orb_15_high",
                "type": "opening_range_breakout",
                "params": {"range_minutes": 15},
                "output": "high",
            },
        ],
    )

    series, warnings = precompute_indicators(candles, strategy)

    assert "orb_15.high" in series and "orb_15.low" in series
    assert series["orb_15_high"] == series["orb_15.high"]
    # Within the opening-range window → None; after it → the range high.
    assert series["orb_15_high"][5] is None
    assert series["orb_15_high"][20] is not None
    # Opening range high over bars 0..14 (highs 100.5..114.5) is 114.5.
    assert series["orb_15_high"][20] == 114.5


# ─── 3. Single-output indicators unchanged (additive guarantee) ────────


def test_single_output_indicators_unaffected() -> None:
    """rsi/ema/sma (output=None) take the unchanged path: stored under their id
    only, no dotted keys, no multi-output warning."""
    candles = _trending(40)
    strategy = make_strategy(
        indicators=[
            {"id": "rsi_14", "type": "rsi", "params": {"period": 14}},
            {"id": "ema_9", "type": "ema", "params": {"period": 9}},
            {"id": "sma_20", "type": "sma", "params": {"period": 20}},
        ],
    )

    series, warnings = precompute_indicators(candles, strategy)

    assert set(series) == {"rsi_14", "ema_9", "sma_20"}  # no extras leaked in
    assert warnings == []
    for key in ("rsi_14", "ema_9", "sma_20"):
        assert len(series[key]) == len(candles)
        assert series[key][-1] is not None  # non-None past warmup
