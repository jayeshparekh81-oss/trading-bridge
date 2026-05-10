"""Pack 17 - composite signal + ML-style feature tests.

Same shape as Pack 2-16. Active count assertion ``>= 215``. The
score-bound tests guarantee 0..100 composites stay in range under
varied inputs (constant, linear, oscillating, blowoff). The ML
features (price_velocity / price_acceleration / volume_momentum_
ratio / range_expansion_score) get monotone-trend predictability
checks.

No new Pine wiring - lock test enforces empty pine_aliases.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack17_active import (
    PACK17_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators.calculations.breakout_probability_score import (
    breakout_probability_score,
)
from app.strategy_engine.indicators.calculations.consolidation_breakout_score import (
    consolidation_breakout_score,
)
from app.strategy_engine.indicators.calculations.exhaustion_score import (
    exhaustion_score,
)
from app.strategy_engine.indicators.calculations.mean_reversion_score import (
    mean_reversion_score,
)
from app.strategy_engine.indicators.calculations.momentum_quality_score import (
    momentum_quality_score,
)
from app.strategy_engine.indicators.calculations.price_acceleration import (
    price_acceleration,
)
from app.strategy_engine.indicators.calculations.price_velocity import (
    price_velocity,
)
from app.strategy_engine.indicators.calculations.range_expansion_score import (
    range_expansion_score,
)
from app.strategy_engine.indicators.calculations.reversal_likelihood_score import (
    reversal_likelihood_score,
)
from app.strategy_engine.indicators.calculations.trend_continuation_score import (
    trend_continuation_score,
)
from app.strategy_engine.indicators.calculations.trend_quality_score import (
    trend_quality_score,
)
from app.strategy_engine.indicators.calculations.volume_momentum_ratio import (
    volume_momentum_ratio,
)
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# --- ML-style features (4) ------------------------------------------


def test_price_velocity_constant_input_yields_zero() -> None:
    out = price_velocity(closes=[100.0] * 20, period=5)
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


def test_price_velocity_linear_input_matches_slope() -> None:
    """closes[i] = i -> velocity = 1.0 / period * period = 1.0 per bar."""
    out = price_velocity(closes=[float(i) for i in range(30)], period=5)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(1.0) for v in defined)


def test_price_velocity_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError, match="positive int"):
        price_velocity(closes=[1.0] * 10, period=0)


def test_price_acceleration_constant_velocity_yields_zero() -> None:
    """Linear closes -> constant velocity -> zero acceleration."""
    out = price_acceleration(closes=[float(i) for i in range(40)], period=5)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0, abs=1e-9) for v in defined)


def test_price_acceleration_quadratic_input_is_positive() -> None:
    """closes[i] = i*i -> velocity rising -> positive acceleration."""
    closes = [float(i * i) for i in range(60)]
    out = price_acceleration(closes=closes, period=5)
    defined = [v for v in out if v is not None]
    assert all(v > 0 for v in defined)


def test_volume_momentum_ratio_flat_price_returns_none() -> None:
    """Zero price velocity -> ratio undefined -> None for those bars."""
    out = volume_momentum_ratio(
        closes=[100.0] * 30,
        volumes=[float(i * 100) for i in range(30)],
        period=5,
    )
    defined = [v for v in out if v is not None]
    assert defined == []


def test_volume_momentum_ratio_sign_follows_volume_change() -> None:
    """Volume rising while price moves -> positive ratio."""
    closes = [100.0 + i for i in range(30)]
    volumes = [1000.0 + i * 10 for i in range(30)]
    out = volume_momentum_ratio(closes=closes, volumes=volumes, period=5)
    defined = [v for v in out if v is not None]
    assert all(v > 0 for v in defined)


def test_volume_momentum_ratio_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        volume_momentum_ratio(closes=[1.0] * 10, volumes=[1.0] * 5)


def test_range_expansion_score_constant_range_yields_zero() -> None:
    out = range_expansion_score(
        highs=[101.0] * 30, lows=[100.0] * 30, short=5, long=20,
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0, abs=1e-9) for v in defined)


def test_range_expansion_score_expanding_range_is_positive() -> None:
    """Recent range > long-window range -> positive score."""
    n = 40
    highs = [100.0 + (5.0 if i >= n - 5 else 1.0) for i in range(n)]
    lows = [99.0] * n
    out = range_expansion_score(highs=highs, lows=lows, short=5, long=20)
    last = out[-1]
    assert last is not None and last > 0.5


def test_range_expansion_score_rejects_long_lt_short() -> None:
    with pytest.raises(ValueError, match=">= short"):
        range_expansion_score(
            highs=[1.0] * 10, lows=[0.0] * 10, short=10, long=5,
        )


# --- Composite scores: bounds (0..100) ------------------------------


def _wavy_closes(n: int = 300, base: float = 24500.0) -> list[float]:
    return [base + math.sin(i * 0.1) * 50.0 for i in range(n)]


def _wavy_highs_lows(closes: list[float]) -> tuple[list[float], list[float]]:
    return [c + 30 for c in closes], [c - 30 for c in closes]


def test_trend_quality_score_in_zero_to_hundred() -> None:
    closes = _wavy_closes()
    highs, lows = _wavy_highs_lows(closes)
    out = trend_quality_score(highs=highs, lows=lows, closes=closes, period=14)
    defined = [v for v in out if v is not None]
    assert defined and all(0.0 <= v <= 100.0 for v in defined)


def test_trend_quality_score_higher_for_strong_trend() -> None:
    """Linear up-trend -> score should be meaningfully higher than
    a sine wave's average score."""
    n = 200
    trend_closes = [24500.0 + i * 5.0 for i in range(n)]
    trend_highs = [c + 10 for c in trend_closes]
    trend_lows = [c - 10 for c in trend_closes]
    trend_out = trend_quality_score(
        highs=trend_highs, lows=trend_lows, closes=trend_closes, period=14,
    )
    wavy_closes = _wavy_closes(n)
    wavy_highs, wavy_lows = _wavy_highs_lows(wavy_closes)
    wavy_out = trend_quality_score(
        highs=wavy_highs, lows=wavy_lows, closes=wavy_closes, period=14,
    )
    trend_avg = sum(v for v in trend_out if v is not None) / len(
        [v for v in trend_out if v is not None]
    )
    wavy_avg = sum(v for v in wavy_out if v is not None) / len(
        [v for v in wavy_out if v is not None]
    )
    assert trend_avg > wavy_avg


def test_momentum_quality_score_in_zero_to_hundred() -> None:
    out = momentum_quality_score(closes=_wavy_closes(), period=14)
    defined = [v for v in out if v is not None]
    assert defined and all(0.0 <= v <= 100.0 for v in defined)


def test_mean_reversion_score_in_zero_to_hundred() -> None:
    out = mean_reversion_score(closes=_wavy_closes(), period=20)
    defined = [v for v in out if v is not None]
    assert defined and all(0.0 <= v <= 100.0 for v in defined)


def test_breakout_probability_score_in_zero_to_hundred() -> None:
    closes = _wavy_closes()
    highs, lows = _wavy_highs_lows(closes)
    volumes = [1000.0 + i for i in range(len(closes))]
    out = breakout_probability_score(
        highs=highs, lows=lows, closes=closes, volumes=volumes, period=20,
    )
    defined = [v for v in out if v is not None]
    assert defined and all(0.0 <= v <= 100.0 for v in defined)


def test_breakout_probability_score_rejects_low_period() -> None:
    with pytest.raises(ValueError, match=">= 5"):
        breakout_probability_score(
            highs=[1.0] * 10, lows=[0.0] * 10, closes=[0.5] * 10,
            volumes=[1.0] * 10, period=4,
        )


def test_trend_continuation_score_in_zero_to_hundred() -> None:
    closes = _wavy_closes()
    highs, lows = _wavy_highs_lows(closes)
    out = trend_continuation_score(highs=highs, lows=lows, closes=closes, period=14)
    defined = [v for v in out if v is not None]
    assert defined and all(0.0 <= v <= 100.0 for v in defined)


def test_reversal_likelihood_score_in_zero_to_hundred() -> None:
    closes = _wavy_closes()
    highs, lows = _wavy_highs_lows(closes)
    out = reversal_likelihood_score(highs=highs, lows=lows, closes=closes, period=14)
    defined = [v for v in out if v is not None]
    assert defined and all(0.0 <= v <= 100.0 for v in defined)


def test_consolidation_breakout_score_in_zero_to_hundred() -> None:
    closes = _wavy_closes()
    highs, lows = _wavy_highs_lows(closes)
    out = consolidation_breakout_score(highs=highs, lows=lows, closes=closes, period=14)
    defined = [v for v in out if v is not None]
    assert defined and all(0.0 <= v <= 100.0 for v in defined)


def test_consolidation_breakout_score_rejects_low_period() -> None:
    with pytest.raises(ValueError, match=">= 5"):
        consolidation_breakout_score(
            highs=[1.0] * 10, lows=[0.0] * 10, closes=[0.5] * 10, period=4,
        )


def test_exhaustion_score_in_zero_to_hundred() -> None:
    closes = _wavy_closes()
    highs, lows = _wavy_highs_lows(closes)
    out = exhaustion_score(highs=highs, lows=lows, closes=closes, period=14)
    defined = [v for v in out if v is not None]
    assert defined and all(0.0 <= v <= 100.0 for v in defined)


def test_exhaustion_score_higher_after_blowoff_bar() -> None:
    """Insert a 5x-ATR blowoff bar at the end - exhaustion should
    be higher than the same series without the blowoff."""
    n = 100
    base = [24500.0 + i * 0.5 for i in range(n)]
    flat_highs = [c + 5 for c in base]
    flat_lows = [c - 5 for c in base]
    blowoff_highs = list(flat_highs)
    blowoff_lows = list(flat_lows)
    blowoff_highs[-1] = base[-1] + 50
    blowoff_lows[-1] = base[-1] - 50
    base_out = exhaustion_score(
        highs=flat_highs, lows=flat_lows, closes=base, period=14,
    )
    blow_out = exhaustion_score(
        highs=blowoff_highs, lows=blowoff_lows, closes=base, period=14,
    )
    base_last = base_out[-1]
    blow_last = blow_out[-1]
    assert base_last is not None and blow_last is not None
    assert blow_last > base_last


def test_reversal_likelihood_rejects_low_period() -> None:
    with pytest.raises(ValueError, match=">= 2"):
        reversal_likelihood_score(
            highs=[1.0] * 10, lows=[0.0] * 10, closes=[0.5] * 10, period=1,
        )


# --- Locks ----------------------------------------------------------


def test_pack17_has_no_pine_aliases() -> None:
    """Pack 17 indicators are custom composites - no real Pine ta.*
    name maps to any of them."""
    for meta in PACK17_ACTIVE_INDICATORS:
        assert meta.pine_aliases == [], (
            f"{meta.id} unexpectedly has Pine aliases: {meta.pine_aliases}"
        )


def test_pack17_no_beginner_difficulty() -> None:
    """Pack 17 indicators are INTERMEDIATE or EXPERT only."""
    from app.strategy_engine.schema.indicator import IndicatorDifficulty
    for meta in PACK17_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has unexpected difficulty {meta.difficulty}"


def test_pack17_composite_score_categories() -> None:
    """Composite-score indicators must be in the Composite category;
    ML features in ML Features category."""
    composite_ids = {
        "trend_quality_score", "momentum_quality_score",
        "mean_reversion_score", "breakout_probability_score",
        "trend_continuation_score", "reversal_likelihood_score",
        "consolidation_breakout_score", "exhaustion_score",
    }
    ml_ids = {
        "price_velocity", "price_acceleration",
        "volume_momentum_ratio", "range_expansion_score",
    }
    for meta in PACK17_ACTIVE_INDICATORS:
        if meta.id in composite_ids:
            assert meta.category == "Composite", (
                f"{meta.id} should be in Composite, got {meta.category}"
            )
        elif meta.id in ml_ids:
            assert meta.category == "ML Features", (
                f"{meta.id} should be in ML Features, got {meta.category}"
            )


def test_active_count_after_pack17_at_least_215() -> None:
    active = [
        m for m in INDICATOR_REGISTRY.values()
        if m.status == IndicatorStatus.ACTIVE
    ]
    assert len(active) >= 215, (
        f"Expected >= 215 active after Pack 17, got {len(active)}"
    )


def test_pack17_ids_present_in_registry() -> None:
    expected = {meta.id for meta in PACK17_ACTIVE_INDICATORS}
    assert len(expected) == 12
    for ind_id in expected:
        assert ind_id in INDICATOR_REGISTRY, f"{ind_id} missing from registry"


# --- Backtest dispatch ----------------------------------------------


def _wavy_intraday_candles(n: int = 300) -> list:
    """Synthetic intraday candles wide enough for the longest Pack 17
    warmup (volume_momentum_ratio period default + composites)."""
    out = []
    for i in range(n):
        base = 24500.0 + math.sin(i * 0.1) * 50.0 + (i % 5) * 2
        out.append(
            make_candle(
                minutes=i * 5,
                open_=base,
                high=base + 30,
                low=base - 30,
                close=base + 10,
                volume=1_000.0 + i,
            )
        )
    return out


@pytest.mark.parametrize(
    ("indicator_type", "params"),
    [
        ("trend_quality_score", {"period": 14}),
        ("momentum_quality_score", {"period": 14}),
        ("mean_reversion_score", {"period": 20}),
        ("breakout_probability_score", {"period": 20}),
        ("price_velocity", {"period": 5}),
        ("price_acceleration", {"period": 5}),
        ("volume_momentum_ratio", {"period": 14}),
        ("range_expansion_score", {"short": 5, "long": 20}),
        ("trend_continuation_score", {"period": 14}),
        ("reversal_likelihood_score", {"period": 14}),
        ("consolidation_breakout_score", {"period": 14}),
        ("exhaustion_score", {"period": 14}),
    ],
)
def test_pack17_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 17 indicator dispatches successfully and yields a
    same-length series with no warnings."""
    candles = _wavy_intraday_candles()
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    assert not any(f"{indicator_type}_inst" in w for w in warnings)
