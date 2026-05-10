"""Pack 3 — candlestick pattern detector tests.

Each pattern gets:
    * a positive case anchored to a hand-crafted OHLC tuple where
      the pattern is unambiguous;
    * a negative case where the OHLC violates one of the rules;
    * an edge case (empty input or insufficient lookback).

Plus dispatch + registry promotion checks at the bottom.

Series shape: each detector returns a same-length-as-input list
where bars carry 1.0 (pattern detected) / 0.0 (no pattern) / None
(warm-up bar where the pattern's lookback can't be evaluated).
"""

from __future__ import annotations

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack3_active import PACK3_ACTIVE_INDICATORS
from app.strategy_engine.indicators.calculations.bearish_engulfing import (
    bearish_engulfing,
)
from app.strategy_engine.indicators.calculations.bullish_engulfing import (
    bullish_engulfing,
)
from app.strategy_engine.indicators.calculations.dark_cloud_cover import (
    dark_cloud_cover,
)
from app.strategy_engine.indicators.calculations.doji import doji
from app.strategy_engine.indicators.calculations.evening_star import evening_star
from app.strategy_engine.indicators.calculations.hammer import hammer
from app.strategy_engine.indicators.calculations.marubozu import marubozu
from app.strategy_engine.indicators.calculations.morning_star import morning_star
from app.strategy_engine.indicators.calculations.piercing_pattern import (
    piercing_pattern,
)
from app.strategy_engine.indicators.calculations.shooting_star import (
    shooting_star,
)
from app.strategy_engine.indicators.calculations.three_black_crows import (
    three_black_crows,
)
from app.strategy_engine.indicators.calculations.three_white_soldiers import (
    three_white_soldiers,
)
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Single-bar patterns ─────────────────────────────────────────────


def test_doji_detects_near_equal_open_close() -> None:
    """Body 0.5 % of range — comfortably under the 10 % default."""
    o = [100.0, 100.0]
    h = [101.0, 101.0]
    lo = [99.0, 99.0]
    c = [100.005, 100.5]  # bar 0 doji, bar 1 not
    out = doji(o, h, lo, c)
    assert out[0] == 1.0
    assert out[1] == 0.0


def test_doji_skips_strong_directional_bar() -> None:
    """Body == range → nowhere near doji territory."""
    out = doji([100.0], [101.0], [100.0], [101.0])
    assert out == [0.0]


def test_doji_empty_returns_empty() -> None:
    assert doji([], [], [], []) == []


def test_hammer_detects_classic_hammer_shape() -> None:
    """Body in upper third, long lower wick, short upper wick."""
    o = [101.5]
    h = [102.0]
    lo = [98.0]
    c = [101.7]
    out = hammer(o, h, lo, c)
    assert out == [1.0]


def test_hammer_skips_balanced_doji() -> None:
    """Symmetric wicks — long upper wick fails ``upper <= 0.5 * lower``."""
    out = hammer([100.0], [102.0], [98.0], [100.0])
    assert out == [0.0]


def test_shooting_star_detects_inverted_hammer_shape() -> None:
    """Body in lower third, long upper wick, short lower wick."""
    o = [98.5]
    h = [102.0]
    lo = [98.0]
    c = [98.3]
    out = shooting_star(o, h, lo, c)
    assert out == [1.0]


def test_shooting_star_skips_strong_directional_body() -> None:
    out = shooting_star([100.0], [105.0], [99.0], [104.0])
    assert out == [0.0]


def test_marubozu_detects_full_body_no_wicks() -> None:
    """open == low, close == high, no wicks."""
    out = marubozu([100.0], [105.0], [100.0], [105.0])
    assert out == [1.0]


def test_marubozu_skips_candle_with_visible_wicks() -> None:
    out = marubozu([100.0], [110.0], [95.0], [105.0])
    assert out == [0.0]


def test_marubozu_empty_returns_empty() -> None:
    assert marubozu([], [], [], []) == []


# ─── Two-bar patterns ────────────────────────────────────────────────


def test_bullish_engulfing_first_bar_is_none() -> None:
    """The 2-bar lookback means index 0 has no prior bar to test
    against — output is ``None``, not 0.0."""
    out = bullish_engulfing([100.0], [101.0], [99.0], [100.5])
    assert out == [None]


def test_bullish_engulfing_detects_engulfing_reversal() -> None:
    """Bar 0 bearish (98 -> 97); bar 1 bullish (96 -> 99) engulfs."""
    o = [98.0, 96.0]
    h = [98.5, 99.5]
    lo = [96.5, 95.5]
    c = [97.0, 99.0]
    out = bullish_engulfing(o, h, lo, c)
    assert out[0] is None
    assert out[1] == 1.0


def test_bullish_engulfing_skips_when_current_doesnt_engulf() -> None:
    o = [98.0, 97.5]
    h = [98.5, 98.0]
    lo = [96.5, 97.0]
    c = [97.0, 97.8]  # current body inside prior body
    out = bullish_engulfing(o, h, lo, c)
    assert out[1] == 0.0


def test_bearish_engulfing_detects_mirror_pattern() -> None:
    """Bar 0 bullish (97 -> 98); bar 1 bearish (99 -> 96) engulfs."""
    o = [97.0, 99.0]
    h = [98.5, 99.5]
    lo = [96.5, 95.5]
    c = [98.0, 96.0]
    out = bearish_engulfing(o, h, lo, c)
    assert out[1] == 1.0


def test_bearish_engulfing_skips_when_prior_was_bearish() -> None:
    o = [99.0, 99.0]
    h = [99.5, 99.5]
    lo = [96.5, 95.5]
    c = [97.0, 96.0]  # prior also bearish — fails the "i-1 bullish" gate
    out = bearish_engulfing(o, h, lo, c)
    assert out[1] == 0.0


def test_piercing_pattern_detects_gap_down_recovery() -> None:
    """Bar 0 bearish 100 -> 96 (mid = 98). Bar 1 opens at 95 (gaps
    below low 96), closes at 99 (above mid 98 but below open 100)."""
    o = [100.0, 95.0]
    h = [100.5, 99.5]
    lo = [95.5, 94.5]
    c = [96.0, 99.0]
    out = piercing_pattern(o, h, lo, c)
    assert out[1] == 1.0


def test_piercing_pattern_skips_when_no_gap_down() -> None:
    """Same bar 0 bearish but bar 1 opens at 96 — no gap below low."""
    o = [100.0, 96.0]
    h = [100.5, 99.5]
    lo = [95.5, 94.5]
    c = [96.0, 99.0]
    out = piercing_pattern(o, h, lo, c)
    assert out[1] == 0.0


def test_dark_cloud_cover_detects_gap_up_failure() -> None:
    """Bar 0 bullish 96 -> 100 (mid = 98). Bar 1 opens at 101 (gap
    above high 100.5), closes at 97 (below mid 98 but above open 96)."""
    o = [96.0, 101.0]
    h = [100.5, 101.5]
    lo = [95.5, 96.5]
    c = [100.0, 97.0]
    out = dark_cloud_cover(o, h, lo, c)
    assert out[1] == 1.0


def test_dark_cloud_cover_skips_when_no_gap_up() -> None:
    o = [96.0, 99.5]  # bar 1 opens below high
    h = [100.5, 101.5]
    lo = [95.5, 96.5]
    c = [100.0, 97.0]
    out = dark_cloud_cover(o, h, lo, c)
    assert out[1] == 0.0


# ─── Three-bar patterns ─────────────────────────────────────────────


def test_morning_star_first_two_bars_are_none() -> None:
    out = morning_star([100.0, 100.0], [101.0, 101.0], [99.0, 99.0], [100.0, 100.0])
    assert out == [None, None]


def test_morning_star_detects_classic_three_bar_reversal() -> None:
    """
    Bar 0: bearish big body 100 -> 96 (range 5, body 4 -> 80% which is
           >= 50% big_body_ratio).
    Bar 1: small star 95.5 -> 95.55 (body 0.05 = 12.5% of range 0.4,
           comfortably under the 30% small_body_ratio).
           max(o,c) = 95.55 < close[0] = 96 (gap below i-2 body).
    Bar 2: bullish 96 -> 99 (closes 99 > mid_body[0] = 98).
    """
    o = [100.0, 95.5, 96.0]
    h = [100.5, 95.7, 99.5]
    lo = [95.5, 95.3, 95.5]
    c = [96.0, 95.55, 99.0]
    out = morning_star(o, h, lo, c)
    assert out[2] == 1.0


def test_morning_star_skips_when_third_bar_doesnt_close_above_mid() -> None:
    o = [100.0, 95.5, 96.0]
    h = [100.5, 95.7, 97.5]
    lo = [95.5, 95.3, 95.5]
    c = [96.0, 95.55, 97.0]  # 97 < mid[0] = 98 — no recovery
    out = morning_star(o, h, lo, c)
    assert out[2] == 0.0


def test_evening_star_detects_mirror_pattern() -> None:
    """
    Bar 0: bullish big body 96 -> 100 (range 5, body 4 = 80%).
    Bar 1: small star 100.3 -> 100.35 (body 0.05 = 10% of range 0.5,
           min(o,c) = 100.3 > close[0] = 100).
    Bar 2: bearish 100 -> 97 (closes 97 < mid_body[0] = 98).
    """
    o = [96.0, 100.3, 100.0]
    h = [100.5, 100.7, 100.5]
    lo = [95.5, 100.2, 96.5]
    c = [100.0, 100.35, 97.0]
    out = evening_star(o, h, lo, c)
    assert out[2] == 1.0


def test_evening_star_skips_when_third_bar_isnt_bearish_enough() -> None:
    o = [96.0, 100.3, 100.0]
    h = [100.5, 100.7, 100.5]
    lo = [95.5, 100.2, 98.5]
    c = [100.0, 100.35, 99.0]  # 99 > mid[0] = 98
    out = evening_star(o, h, lo, c)
    assert out[2] == 0.0


def test_three_white_soldiers_detects_three_rising_bullish_bars() -> None:
    """Each bar opens within the prior body, closes higher with a
    big body (>= 50 % of range)."""
    o = [100.0, 102.0, 104.0]
    h = [103.5, 105.5, 107.5]
    lo = [99.5, 101.5, 103.5]
    c = [103.0, 105.0, 107.0]
    out = three_white_soldiers(o, h, lo, c)
    assert out[2] == 1.0


def test_three_white_soldiers_skips_when_one_bar_is_bearish() -> None:
    o = [100.0, 102.0, 104.0]
    h = [103.5, 105.5, 105.5]
    lo = [99.5, 101.5, 103.5]
    c = [103.0, 105.0, 103.5]  # third bar is bearish (close < open)
    out = three_white_soldiers(o, h, lo, c)
    assert out[2] == 0.0


def test_three_black_crows_detects_three_falling_bearish_bars() -> None:
    """Mirror of three_white_soldiers."""
    o = [107.0, 105.0, 103.0]
    h = [107.5, 105.5, 103.5]
    lo = [103.5, 101.5, 99.5]
    c = [104.0, 102.0, 100.0]
    out = three_black_crows(o, h, lo, c)
    assert out[2] == 1.0


def test_three_black_crows_skips_when_one_close_doesnt_drop() -> None:
    o = [107.0, 105.0, 103.0]
    h = [107.5, 105.5, 105.5]
    lo = [103.5, 101.5, 102.0]
    c = [104.0, 102.0, 102.5]  # third close 102.5 > prior close 102 — fails
    out = three_black_crows(o, h, lo, c)
    assert out[2] == 0.0


# ─── Length validation ─────────────────────────────────────────────


def test_pattern_calcs_reject_mismatched_input_lengths() -> None:
    with pytest.raises(ValueError):
        doji([1.0, 2.0], [1.0], [1.0, 2.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        bullish_engulfing([1.0], [1.0, 2.0], [1.0], [1.0])
    with pytest.raises(ValueError):
        morning_star([1.0, 2.0], [1.0, 2.0], [1.0], [1.0, 2.0])


# ─── Registry promotion ────────────────────────────────────────────


_PACK3_IDS = {
    "doji",
    "hammer",
    "shooting_star",
    "marubozu",
    "bullish_engulfing",
    "bearish_engulfing",
    "piercing_pattern",
    "dark_cloud_cover",
    "morning_star",
    "evening_star",
    "three_white_soldiers",
    "three_black_crows",
}


def test_pack3_module_exposes_twelve_indicators() -> None:
    assert len(PACK3_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK3_ACTIVE_INDICATORS} == _PACK3_IDS


def test_pack3_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK3_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id
        assert meta.category == "Pattern"


def test_active_count_after_pack3_is_forty_seven() -> None:
    """20 historical + 15 Pack 2 + 12 Pack 3 = 47.

    Loose lower bound so future packs don't have to edit this file."""
    assert len(get_active_indicators()) >= 47


def test_pack3_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK3_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


# ─── Backtest dispatch ─────────────────────────────────────────────


def _bullish_engulfing_candles() -> list:
    """Two bars where bar 1 engulfs bar 0; padded out with neutral
    candles before/after so the strategy schema's price > 99.5
    entry trigger has somewhere to fire."""
    out = []
    # Two long flat bars to give the indicator some warmup data.
    for i in range(3):
        out.append(make_candle(minutes=i, open_=100.0, high=100.5, low=99.5, close=100.0))
    # Bar 3 bearish, bar 4 bullish-engulfing.
    out.append(make_candle(minutes=3, open_=98.0, high=98.5, low=96.5, close=97.0))
    out.append(make_candle(minutes=4, open_=96.0, high=99.5, low=95.5, close=99.0))
    # Trailing flat candles.
    for i in range(5, 10):
        out.append(make_candle(minutes=i, open_=99.0, high=99.5, low=98.5, close=99.0))
    return out


def test_dispatch_emits_pack3_pattern_series_with_one_signal() -> None:
    """End-to-end: registry → dispatcher → series. The hand-crafted
    candle sequence triggers exactly one bullish-engulfing signal."""
    candles = _bullish_engulfing_candles()
    strategy = make_strategy(
        indicators=[
            {"id": "be_main", "type": "bullish_engulfing", "params": {}},
        ],
    )
    series, _warnings = precompute_indicators(candles, strategy)
    primary = series["be_main"]
    assert len(primary) == len(candles)
    # Bar 0 is None (warm-up); bar 4 is the engulfing match.
    assert primary[0] is None
    assert primary[4] == pytest.approx(1.0)
    # Every other bar (1-3, 5-9) should be 0.0.
    for i, v in enumerate(primary):
        if i == 0 or i == 4:
            continue
        assert v == pytest.approx(0.0), f"bar {i}: expected 0.0, got {v!r}"


def test_dispatch_three_pattern_indicators_coexist_with_phase1() -> None:
    """Mixing patterns with a Phase 1 EMA in one strategy precomputes
    everything in a single pass."""
    candles = [
        make_candle(minutes=i, open_=100.0 + i, high=101.0 + i, low=99.0 + i, close=100.5 + i)
        for i in range(20)
    ]
    strategy = make_strategy(
        indicators=[
            {"id": "ema_main", "type": "ema", "params": {"period": 5, "source": "close"}},
            {"id": "doji_main", "type": "doji", "params": {"body_ratio": 0.1}},
            {"id": "marubozu_main", "type": "marubozu", "params": {"max_wick_ratio": 0.05}},
            {
                "id": "tws_main",
                "type": "three_white_soldiers",
                "params": {"min_body_ratio": 0.5},
            },
        ],
    )
    series, _warnings = precompute_indicators(candles, strategy)
    assert {"ema_main", "doji_main", "marubozu_main", "tws_main"} <= series.keys()
    # Each pattern series is the same length as candles.
    for sid in ("doji_main", "marubozu_main", "tws_main"):
        assert len(series[sid]) == len(candles)
