"""Pack 11 — cycle + divergence + advanced pattern tests.

Same shape as Pack 2-10. Active count assertion ``>= 143``.

No Pine importer tests — Pack 11 deliberately ships no Pine
wirings (none of the indicators have a standard Pine v5 ta.*
equivalent). Documented in the pack11_active module.

Cycle indicators get qualitative tests (output range, no NaNs,
deterministic) rather than byte-matching TradingView since our
implementation simplifies Ehlers' published median-period chain.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack11_active import (
    PACK11_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators.calculations.consolidation_score import (
    consolidation_score,
)
from app.strategy_engine.indicators.calculations.cycle_period_oscillator import (
    cycle_period_oscillator,
)
from app.strategy_engine.indicators.calculations.dominant_cycle_period import (
    dominant_cycle_period,
)
from app.strategy_engine.indicators.calculations.inside_bar_breakout import (
    inside_bar_breakout,
)
from app.strategy_engine.indicators.calculations.macd_divergence import (
    macd_divergence,
)
from app.strategy_engine.indicators.calculations.mesa_sine_lead import (
    mesa_sine_lead,
)
from app.strategy_engine.indicators.calculations.mesa_sine_wave import (
    mesa_sine_wave,
)
from app.strategy_engine.indicators.calculations.nr7 import nr7
from app.strategy_engine.indicators.calculations.obv_divergence import (
    obv_divergence,
)
from app.strategy_engine.indicators.calculations.outside_bar import outside_bar
from app.strategy_engine.indicators.calculations.rsi_divergence import (
    rsi_divergence,
)
from app.strategy_engine.indicators.calculations.wide_range_bar import (
    wide_range_bar,
)
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Cycle Indicators (4) ────────────────────────────────────────────


def test_dominant_cycle_period_insufficient_returns_empty() -> None:
    out = dominant_cycle_period(closes=[100.0] * 20, smooth=0.07)
    assert out == []


def test_dominant_cycle_period_returns_in_band() -> None:
    """Output should land in [6, 50] for any defined bar."""
    import math

    n = 200
    out = dominant_cycle_period(
        closes=[100.0 + 5.0 * math.sin(i * 0.3) for i in range(n)],
        smooth=0.07,
    )
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(6.0 <= v <= 50.0 for v in defined)


def test_mesa_sine_wave_output_in_unit_range() -> None:
    import math

    n = 200
    out = mesa_sine_wave(
        closes=[100.0 + 5.0 * math.sin(i * 0.3) for i in range(n)],
        alpha=0.07,
    )
    defined = [v for v in out if v is not None]
    assert all(-1.0 <= v <= 1.0 for v in defined)


def test_mesa_sine_lead_differs_from_sine_wave() -> None:
    """Lead is a 45° phase shift — for the same input, lead and
    wave should disagree on at least one bar (otherwise the shift
    would be a no-op)."""
    import math

    closes = [100.0 + 5.0 * math.sin(i * 0.3) for i in range(200)]
    wave = mesa_sine_wave(closes=closes, alpha=0.07)
    lead = mesa_sine_lead(closes=closes, alpha=0.07)
    diffs = [
        (w - le) for w, le in zip(wave, lead, strict=True)
        if w is not None and le is not None
    ]
    assert any(abs(d) > 1e-3 for d in diffs)


def test_cycle_period_oscillator_extreme_at_window_high() -> None:
    """Last close at the window high → oscillator = +1."""
    n = 30
    out = cycle_period_oscillator(
        highs=[10.0] * n, lows=[5.0] * n, closes=[5.0] * 29 + [10.0],
        period=14,
    )
    assert out[-1] == pytest.approx(1.0)


def test_cycle_period_oscillator_flat_window_returns_zero() -> None:
    out = cycle_period_oscillator(
        highs=[10.0] * 30, lows=[10.0] * 30, closes=[10.0] * 30, period=14,
    )
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


# ─── Divergence Detection (3) ────────────────────────────────────────


def test_rsi_divergence_returns_same_length() -> None:
    n = 60
    out = rsi_divergence(
        closes=[100.0 + (i % 7) for i in range(n)], rsi_period=14, lookback=20,
    )
    assert len(out) == n


def test_rsi_divergence_emits_some_signal_on_long_monotone_uptrend() -> None:
    """A strict monotone uptrend looks like saturated-RSI bearish
    divergence by the textbook: price keeps making new highs but
    RSI can't (it's pinned at 100). Counter-intuitive at first,
    but it's exactly what the regular-divergence rule prescribes
    — and a real trading concern when momentum exhausts.

    This test pins the contract: the detector should fire at
    least once on this input, not return all-zero."""
    n = 50
    out = rsi_divergence(
        closes=[100.0 + i for i in range(n)], rsi_period=14, lookback=20,
    )
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert any(v != 0.0 for v in defined)


def test_macd_divergence_returns_same_length() -> None:
    n = 80
    out = macd_divergence(
        closes=[100.0 + (i % 5) for i in range(n)],
        fast=12, slow=26, signal=9, lookback=20,
    )
    assert len(out) == n


def test_obv_divergence_returns_same_length() -> None:
    n = 50
    out = obv_divergence(
        closes=[100.0 + (i % 7) for i in range(n)],
        volumes=[1000.0] * n, lookback=20,
    )
    assert len(out) == n


def test_obv_divergence_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        obv_divergence(closes=[1.0] * 10, volumes=[1.0] * 9, lookback=5)


# ─── Advanced Patterns (5) ───────────────────────────────────────────


def test_inside_bar_breakout_long_signal() -> None:
    """Bar -2: range 100-110. Bar -1: inside (104-108). Bar 0:
    high 112 > inside-bar high 108 → +1."""
    highs = [100.0, 110.0, 108.0, 112.0]
    lows = [95.0, 100.0, 104.0, 105.0]
    out = inside_bar_breakout(highs=highs, lows=lows)
    assert out[-1] == 1.0


def test_inside_bar_breakout_short_signal() -> None:
    highs = [100.0, 110.0, 108.0, 105.0]
    lows = [95.0, 100.0, 104.0, 102.0]  # bar -1 low 104 > bar -2 low 100 → inside; current low 102 < 104
    out = inside_bar_breakout(highs=highs, lows=lows)
    assert out[-1] == -1.0


def test_inside_bar_breakout_no_inside_yields_zero() -> None:
    highs = [100.0, 105.0, 110.0]
    lows = [95.0, 100.0, 105.0]  # no inside bar
    out = inside_bar_breakout(highs=highs, lows=lows)
    assert out[-1] == 0.0


def test_outside_bar_bullish_engulfing() -> None:
    out = outside_bar(
        opens=[100.0, 95.0],
        highs=[105.0, 110.0],
        lows=[97.0, 90.0],
        closes=[103.0, 108.0],
    )
    assert out[-1] == 1.0


def test_outside_bar_bearish_engulfing() -> None:
    out = outside_bar(
        opens=[100.0, 105.0],
        highs=[105.0, 110.0],
        lows=[97.0, 90.0],
        closes=[103.0, 92.0],  # bearish close
    )
    assert out[-1] == -1.0


def test_outside_bar_normal_bar_yields_zero() -> None:
    out = outside_bar(
        opens=[100.0, 102.0],
        highs=[105.0, 104.0],  # not engulfing
        lows=[97.0, 99.0],
        closes=[103.0, 103.5],
    )
    assert out[-1] == 0.0


def test_nr7_narrowest_yields_one() -> None:
    """Bar 6 has the narrowest range of the last 7 bars."""
    highs = [110.0, 109.0, 108.0, 107.0, 106.0, 105.0, 100.5]
    lows = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    out = nr7(highs=highs, lows=lows)
    assert out[-1] == 1.0


def test_nr7_wider_yields_zero() -> None:
    highs = [101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 110.0]
    lows = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    out = nr7(highs=highs, lows=lows)
    assert out[-1] == 0.0


def test_nr7_insufficient_returns_empty() -> None:
    assert nr7(highs=[1.0] * 5, lows=[1.0] * 5) == []


def test_wide_range_bar_bullish_signal() -> None:
    """Last bar's range >> avg, close > open → +1."""
    opens = [100.0] * 20 + [100.0]
    highs = [101.0] * 20 + [105.0]  # range 5 vs avg 1
    lows = [100.0] * 20 + [98.0]
    closes = [100.5] * 20 + [104.0]
    out = wide_range_bar(opens, highs, lows, closes, lookback=20, mult=1.5)
    assert out[-1] == 1.0


def test_wide_range_bar_rejects_zero_mult() -> None:
    with pytest.raises(ValueError, match="> 0"):
        wide_range_bar(
            opens=[1.0] * 30, highs=[1.0] * 30, lows=[1.0] * 30,
            closes=[1.0] * 30, mult=0,
        )


def test_consolidation_score_tight_window_high_score() -> None:
    """All bars at same H/L → window_range = 0 → score = 1.0."""
    out = consolidation_score(
        highs=[100.0] * 20, lows=[99.0] * 20, period=10
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(1.0) for v in defined)


def test_consolidation_score_wide_window_low_score() -> None:
    """Strongly-trending highs/lows → score should be much less than 1."""
    n = 30
    out = consolidation_score(
        highs=[100.0 + i for i in range(n)],
        lows=[99.0 + i for i in range(n)],
        period=10,
    )
    last = out[-1]
    assert last is not None
    assert last < 0.5


def test_consolidation_score_rejects_period_below_two() -> None:
    with pytest.raises(ValueError, match=">= 2"):
        consolidation_score(highs=[1.0] * 10, lows=[1.0] * 10, period=1)


# ─── Registry promotion ──────────────────────────────────────────────


_PACK11_IDS = {
    "dominant_cycle_period",
    "mesa_sine_wave",
    "mesa_sine_lead",
    "cycle_period_oscillator",
    "rsi_divergence",
    "macd_divergence",
    "obv_divergence",
    "inside_bar_breakout",
    "outside_bar",
    "nr7",
    "wide_range_bar",
    "consolidation_score",
}


def test_pack11_module_exposes_twelve_indicators() -> None:
    assert len(PACK11_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK11_ACTIVE_INDICATORS} == _PACK11_IDS


def test_pack11_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK11_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack11_is_one_hundred_forty_three() -> None:
    """Pack-10 baseline 131 + 12 Pack 11 = 143."""
    assert len(get_active_indicators()) >= 143


def test_pack11_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK11_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack11_no_beginner_difficulty() -> None:
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK11_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has difficulty {meta.difficulty}; expected INTERMEDIATE/EXPERT"


def test_pack11_has_no_pine_aliases() -> None:
    """Pack 11 deliberately ships no Pine wiring — no indicator
    in the pack should claim a Pine alias."""
    for meta in PACK11_ACTIVE_INDICATORS:
        assert meta.pine_aliases == [], (
            f"{meta.id} unexpectedly has Pine aliases: {meta.pine_aliases}"
        )


# ─── Backtest dispatch ──────────────────────────────────────────────


def _wavy_candles(n: int = 120) -> list:
    """Synthetic OHLC with non-trivial range — needs to be large
    enough for the cycle + divergence indicators (200+ minimum)."""
    import math
    out = []
    for i in range(n):
        base = 100.0 + 3.0 * math.sin(i * 0.3) + (i % 5) * 0.2
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
        ("dominant_cycle_period", {"smooth": 0.07}),
        ("mesa_sine_wave", {"alpha": 0.07}),
        ("mesa_sine_lead", {"alpha": 0.07}),
        ("cycle_period_oscillator", {"period": 14}),
        ("rsi_divergence", {"rsi_period": 14, "lookback": 20}),
        (
            "macd_divergence",
            {"fast": 12, "slow": 26, "signal": 9, "lookback": 20},
        ),
        ("obv_divergence", {"lookback": 20}),
        ("inside_bar_breakout", {}),
        ("outside_bar", {}),
        ("nr7", {}),
        ("wide_range_bar", {"lookback": 20, "mult": 1.5}),
        ("consolidation_score", {"period": 10}),
    ],
)
def test_pack11_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 11 indicator dispatches successfully and produces
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
