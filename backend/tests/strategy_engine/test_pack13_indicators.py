"""Pack 13 - sentiment + breadth + cross-asset tests.

Same shape as Pack 2-12. Active count assertion ``>= 167``.

The relative_strength_vs_benchmark indicator is a Phase-1 stub
(same shape as Pack 8's nifty_correlation). Test asserts the
all-None contract + the HAS_BENCHMARK_CONTEXT flag so a future
Phase-2 wiring can't quietly regress.

No new Pine importer wiring; pinned by the Pack 13 lock test.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack13_active import (
    PACK13_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators.calculations.advance_decline_proxy import (
    advance_decline_proxy,
)
from app.strategy_engine.indicators.calculations.breadth_thrust import (
    breadth_thrust,
)
from app.strategy_engine.indicators.calculations.capitulation_signal import (
    capitulation_signal,
)
from app.strategy_engine.indicators.calculations.correlation_with_volume import (
    correlation_with_volume,
)
from app.strategy_engine.indicators.calculations.divergence_strength_score import (
    divergence_strength_score,
)
from app.strategy_engine.indicators.calculations.fear_greed_index import (
    fear_greed_index,
)
from app.strategy_engine.indicators.calculations.mcclellan_oscillator_proxy import (
    mcclellan_oscillator_proxy,
)
from app.strategy_engine.indicators.calculations.relative_strength_vs_benchmark import (
    HAS_BENCHMARK_CONTEXT,
    relative_strength_vs_benchmark,
)
from app.strategy_engine.indicators.calculations.sentiment_oscillator import (
    sentiment_oscillator,
)
from app.strategy_engine.indicators.calculations.tick_index import tick_index
from app.strategy_engine.indicators.calculations.trend_consistency_score import (
    trend_consistency_score,
)
from app.strategy_engine.indicators.calculations.trin_proxy import trin_proxy
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# --- Sentiment Proxies (4) ------------------------------------------


def test_fear_greed_index_returns_in_range() -> None:
    """Output should always land in [0, 100] when defined."""
    n = 100
    out = fear_greed_index(
        highs=[10.0 + (i % 5) for i in range(n)],
        lows=[8.0 + (i % 5) for i in range(n)],
        closes=[9.0 + (i % 5) for i in range(n)],
        volumes=[1000.0 + i for i in range(n)],
        lookback=30,
    )
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(0.0 <= v <= 100.0 for v in defined)


def test_fear_greed_index_rejects_short_lookback() -> None:
    with pytest.raises(ValueError, match=">= 5"):
        fear_greed_index(
            highs=[1.0] * 30, lows=[1.0] * 30, closes=[1.0] * 30,
            volumes=[1.0] * 30, lookback=4,
        )


def test_breadth_thrust_all_bull_settles_at_one() -> None:
    """All bullish bars -> share = 1 once the rolling window is full
    -> EMA settles toward 1 over enough bars. Need n >> period +
    ema_period so the EMA has time to converge from its
    zero-seed warm-up."""
    n = 100
    out = breadth_thrust(
        opens=[100.0] * n, closes=[101.0] * n, period=10, ema_period=10,
    )
    last = out[-1]
    assert last is not None
    assert last == pytest.approx(1.0, abs=0.01)


def test_breadth_thrust_all_bear_settles_at_zero() -> None:
    n = 100
    out = breadth_thrust(
        opens=[100.0] * n, closes=[99.0] * n, period=10, ema_period=10,
    )
    last = out[-1]
    assert last is not None
    assert last == pytest.approx(0.0, abs=0.01)


def test_sentiment_oscillator_all_bull_yields_hundred() -> None:
    out = sentiment_oscillator(
        opens=[100.0] * 30, closes=[101.0] * 30, period=20,
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(100.0) for v in defined)


def test_sentiment_oscillator_all_bear_yields_zero() -> None:
    out = sentiment_oscillator(
        opens=[100.0] * 30, closes=[99.0] * 30, period=20,
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0) for v in defined)


def test_capitulation_signal_volume_spike_yields_signal() -> None:
    """Last bar: 5x volume + 3x range + close at low -> -1.0."""
    highs = [101.0] * 20 + [105.0]  # range 5 vs avg 1
    lows = [100.0] * 20 + [95.0]
    closes = [100.5] * 20 + [95.0]  # close at low
    volumes = [10.0] * 20 + [50.0]  # 5x avg
    out = capitulation_signal(
        highs, lows, closes, volumes, vol_mult=3.0, range_mult=2.0, lookback=20,
    )
    assert out[-1] == -1.0


def test_capitulation_signal_no_spike_yields_zero() -> None:
    out = capitulation_signal(
        highs=[101.0] * 30, lows=[100.0] * 30, closes=[100.5] * 30,
        volumes=[10.0] * 30, vol_mult=3.0, range_mult=2.0, lookback=20,
    )
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


# --- Market Breadth Proxies (4) -------------------------------------


def test_tick_index_monotone_uptrend_yields_period() -> None:
    """Strict uptrend -> every bar +1 -> sum = period."""
    out = tick_index(closes=[100.0 + i for i in range(20)], period=5)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(5.0) for v in defined)


def test_tick_index_monotone_downtrend_yields_neg_period() -> None:
    out = tick_index(closes=[100.0 - i for i in range(20)], period=5)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(-5.0) for v in defined)


def test_advance_decline_proxy_all_bull_yields_period() -> None:
    out = advance_decline_proxy(
        opens=[100.0] * 30, closes=[101.0] * 30, period=10,
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(10.0) for v in defined)


def test_advance_decline_proxy_all_bear_yields_neg_period() -> None:
    out = advance_decline_proxy(
        opens=[100.0] * 30, closes=[99.0] * 30, period=10,
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(-10.0) for v in defined)


def test_mcclellan_oscillator_proxy_constant_input_yields_zero() -> None:
    """All bullish -> bar_sign constant +1 -> EMA(fast) == EMA(slow) -> diff = 0."""
    out = mcclellan_oscillator_proxy(
        opens=[100.0] * 100, closes=[101.0] * 100, fast=19, slow=39,
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0) for v in defined)


def test_mcclellan_rejects_fast_geq_slow() -> None:
    with pytest.raises(ValueError, match="strictly less"):
        mcclellan_oscillator_proxy(
            opens=[1.0] * 100, closes=[1.0] * 100, fast=39, slow=39,
        )


def test_trin_proxy_all_bull_returns_none() -> None:
    """All bullish bars -> bear_count = 0 -> degenerate -> None."""
    out = trin_proxy(
        opens=[100.0] * 30, closes=[101.0] * 30, volumes=[10.0] * 30, period=10,
    )
    assert all(v is None for v in out)


def test_trin_proxy_balanced_window_yields_one() -> None:
    """Equal bull/bear bars + equal volume -> ratio_count == 1, ratio_vol == 1
    -> TRIN = 1."""
    n = 21
    opens = []
    closes = []
    for i in range(n):
        opens.append(100.0)
        closes.append(101.0 if i % 2 == 0 else 99.0)
    volumes = [10.0] * n
    out = trin_proxy(opens=opens, closes=closes, volumes=volumes, period=10)
    last = out[-1]
    assert last is not None
    assert last == pytest.approx(1.0)


# --- Cross-Asset Signals (4) ----------------------------------------


def test_relative_strength_vs_benchmark_is_phase1_stub() -> None:
    """The stub contract: returns all-None for any input length.
    A future Phase-2 wiring will replace the body but the empty-
    output guarantee documents current behaviour so callers can
    branch on None."""
    out = relative_strength_vs_benchmark(closes=[100.0] * 50, period=30)
    assert len(out) == 50
    assert all(v is None for v in out)


def test_relative_strength_vs_benchmark_flag() -> None:
    """The HAS_BENCHMARK_CONTEXT flag is the operator-visible
    signal for the dashboard."""
    assert HAS_BENCHMARK_CONTEXT is False


def test_relative_strength_vs_benchmark_rejects_low_period() -> None:
    with pytest.raises(ValueError, match="> 1"):
        relative_strength_vs_benchmark(closes=[1.0] * 50, period=1)


def test_correlation_with_volume_returns_in_range() -> None:
    n = 50
    out = correlation_with_volume(
        closes=[100.0 + (i % 7) for i in range(n)],
        volumes=[1000.0 + (i % 5) for i in range(n)],
        period=20,
    )
    defined = [v for v in out if v is not None]
    assert all(-1.0 - 1e-9 <= v <= 1.0 + 1e-9 for v in defined)


def test_correlation_with_volume_constant_yields_none() -> None:
    """Constant inputs -> stddev = 0 -> Pearson undefined -> None."""
    out = correlation_with_volume(
        closes=[100.0] * 30, volumes=[1000.0] * 30, period=20,
    )
    assert all(v is None for v in out)


def test_divergence_strength_score_in_bounds() -> None:
    """Sum of three -1/0/+1 codes -> output in [-3, +3]."""
    n = 60
    out = divergence_strength_score(
        closes=[100.0 + (i % 7) for i in range(n)],
        volumes=[1000.0] * n, period=14,
    )
    defined = [v for v in out if v is not None]
    assert all(-3.0 <= v <= 3.0 for v in defined)


def test_trend_consistency_score_uptrend_yields_one() -> None:
    """Strict uptrend -> all SMA slopes positive -> score = 1.0."""
    n = 100
    out = trend_consistency_score(
        closes=[100.0 + i * 0.5 for i in range(n)], timeframes=(10, 20, 50),
    )
    defined = [v for v in out if v is not None]
    # All defined values should be 1.0 (every SMA slope agrees).
    assert all(v == pytest.approx(1.0) for v in defined)


def test_trend_consistency_score_rejects_short_timeframes() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        trend_consistency_score(closes=[1.0] * 100, timeframes=(10,))


def test_trend_consistency_score_rejects_period_below_two() -> None:
    with pytest.raises(ValueError, match=">= 2"):
        trend_consistency_score(closes=[1.0] * 100, timeframes=(10, 1))


# --- Registry promotion ---------------------------------------------


_PACK13_IDS = {
    "fear_greed_index",
    "breadth_thrust",
    "sentiment_oscillator",
    "capitulation_signal",
    "tick_index",
    "advance_decline_proxy",
    "mcclellan_oscillator_proxy",
    "trin_proxy",
    "relative_strength_vs_benchmark",
    "correlation_with_volume",
    "divergence_strength_score",
    "trend_consistency_score",
}


def test_pack13_module_exposes_twelve_indicators() -> None:
    assert len(PACK13_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK13_ACTIVE_INDICATORS} == _PACK13_IDS


def test_pack13_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK13_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack13_is_one_hundred_sixty_seven() -> None:
    """Pack-12 baseline 155 + 12 Pack 13 = 167."""
    assert len(get_active_indicators()) >= 167


def test_pack13_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK13_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack13_no_beginner_difficulty() -> None:
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK13_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has difficulty {meta.difficulty}; expected INTERMEDIATE/EXPERT"


def test_pack13_has_no_pine_aliases() -> None:
    """Pack 13 ships no Pine wiring - none of the indicators have
    a standard Pine v5 ta.* equivalent. Lock so a future edit
    doesn't quietly add one."""
    for meta in PACK13_ACTIVE_INDICATORS:
        assert meta.pine_aliases == [], (
            f"{meta.id} unexpectedly has Pine aliases: {meta.pine_aliases}"
        )


# --- Backtest dispatch ----------------------------------------------


def _wavy_candles(n: int = 120) -> list:
    """Synthetic OHLC large enough for the cross-asset indicators
    (need 50+ for trend_consistency_score's SMA50 default)."""
    out = []
    for i in range(n):
        base = 100.0 + (i % 9) - 4.0
        out.append(
            make_candle(
                minutes=i,
                open_=base,
                high=base + 1.5,
                low=base - 1.5,
                close=base + 0.5,
                volume=1_000.0 + i * 4,
            )
        )
    return out


@pytest.mark.parametrize(
    ("indicator_type", "params"),
    [
        ("fear_greed_index", {"lookback": 30}),
        ("breadth_thrust", {"period": 10, "ema_period": 10}),
        ("sentiment_oscillator", {"period": 20}),
        (
            "capitulation_signal",
            {
                "vol_mult": 3.0, "range_mult": 2.0,
                "lookback": 20, "close_position_threshold": 0.85,
            },
        ),
        ("tick_index", {"period": 5}),
        ("advance_decline_proxy", {"period": 10}),
        ("mcclellan_oscillator_proxy", {"fast": 19, "slow": 39}),
        ("trin_proxy", {"period": 10}),
        ("relative_strength_vs_benchmark", {"period": 30}),
        ("correlation_with_volume", {"period": 20}),
        ("divergence_strength_score", {"period": 14}),
        ("trend_consistency_score", {"timeframes": "10,20,50"}),
    ],
)
def test_pack13_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 13 indicator dispatches successfully and produces
    a same-length series."""
    candles = _wavy_candles()
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    assert not any(f"{indicator_type}_inst" in w for w in warnings)
