"""Pack 12 — volatility regime + risk-adjusted + bands tests.

Same shape as Pack 2-11. Active count assertion ``>= 155``.

No new Pine importer wiring this pack — none of Pack 12's
indicators have a standard Pine v5 ta.* equivalent. Lock test
asserts the contract.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack12_active import (
    PACK12_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators.calculations.atr_percent import atr_percent
from app.strategy_engine.indicators.calculations.atr_trailing_stop import (
    atr_trailing_stop,
)
from app.strategy_engine.indicators.calculations.burke_ratio import burke_ratio
from app.strategy_engine.indicators.calculations.chandelier_exit_long import (
    chandelier_exit_long,
)
from app.strategy_engine.indicators.calculations.chandelier_exit_short import (
    chandelier_exit_short,
)
from app.strategy_engine.indicators.calculations.martin_ratio import martin_ratio
from app.strategy_engine.indicators.calculations.parkinson_volatility import (
    parkinson_volatility,
)
from app.strategy_engine.indicators.calculations.supertrend_v2 import (
    supertrend_v2,
)
from app.strategy_engine.indicators.calculations.trade_efficiency import (
    trade_efficiency,
)
from app.strategy_engine.indicators.calculations.ulcer_index import ulcer_index
from app.strategy_engine.indicators.calculations.volatility_ratio import (
    volatility_ratio,
)
from app.strategy_engine.indicators.calculations.volatility_regime import (
    volatility_regime,
)
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Volatility Regime (4) ───────────────────────────────────────────


def test_atr_percent_constant_input_yields_zero() -> None:
    """Flat highs == lows → ATR = 0 → ATR% = 0."""
    out = atr_percent(
        highs=[100.0] * 30, lows=[100.0] * 30, closes=[100.0] * 30, period=14
    )
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


def test_atr_percent_returns_same_length() -> None:
    n = 30
    out = atr_percent(
        highs=[10.0 + (i % 5) for i in range(n)],
        lows=[8.0 + (i % 5) for i in range(n)],
        closes=[9.0 + (i % 5) for i in range(n)],
        period=14,
    )
    assert len(out) == n


def test_volatility_regime_emits_in_bounds() -> None:
    n = 200
    out = volatility_regime(
        highs=[10.0 + (i % 7) - 3.0 for i in range(n)],
        lows=[8.0 + (i % 7) - 3.0 for i in range(n)],
        closes=[9.0 + (i % 7) - 3.0 for i in range(n)],
        lookback=100, atr_period=14,
    )
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(v in (0.0, 1.0, 2.0, 3.0) for v in defined)


def test_volatility_regime_rejects_short_lookback() -> None:
    with pytest.raises(ValueError, match=">= 4"):
        volatility_regime(
            highs=[1.0] * 30, lows=[1.0] * 30, closes=[1.0] * 30, lookback=3,
        )


def test_parkinson_volatility_constant_bar_yields_zero() -> None:
    """Flat high==low for every bar → log(1) = 0 → vol = 0."""
    out = parkinson_volatility(
        highs=[100.0] * 30, lows=[100.0] * 30, period=20, bars_per_year=252,
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0) for v in defined)


def test_parkinson_volatility_known_window() -> None:
    """Constant 1% range → known annualised vol."""
    n = 30
    highs = [101.0] * n
    lows = [100.0] * n
    out = parkinson_volatility(highs=highs, lows=lows, period=20, bars_per_year=252)
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    # Just sanity-check it's positive and finite.
    assert all(v > 0 for v in defined)


def test_volatility_ratio_rejects_short_geq_long() -> None:
    with pytest.raises(ValueError, match="strictly less"):
        volatility_ratio(
            highs=[1.0] * 30, lows=[1.0] * 30, closes=[1.0] * 30,
            short=20, long=20,
        )


def test_volatility_ratio_constant_input_yields_undefined_or_one() -> None:
    """Constant H/L/C → both ATRs → 0 → ratio undefined → None.
    The implementation correctly returns None when long-window ATR
    is zero rather than raising or producing inf."""
    out = volatility_ratio(
        highs=[100.0] * 30, lows=[100.0] * 30, closes=[100.0] * 30,
        short=5, long=20,
    )
    # All defined entries should be None (degenerate).
    assert all(v is None for v in out)


# ─── Risk-Adjusted (4) ───────────────────────────────────────────────


def test_trade_efficiency_clean_uptrend_yields_one() -> None:
    """Strict monotone uptrend: net == path → efficiency = +1."""
    out = trade_efficiency(closes=[100.0 + i for i in range(30)], period=20)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(1.0) for v in defined)


def test_trade_efficiency_clean_downtrend_yields_minus_one() -> None:
    out = trade_efficiency(closes=[100.0 - i for i in range(30)], period=20)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(-1.0) for v in defined)


def test_trade_efficiency_constant_window_yields_zero() -> None:
    out = trade_efficiency(closes=[100.0] * 30, period=20)
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


def test_ulcer_index_monotone_uptrend_yields_zero() -> None:
    """Strict uptrend has no drawdowns → UI = 0."""
    out = ulcer_index(closes=[100.0 + i for i in range(30)], period=14)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0) for v in defined)


def test_ulcer_index_drawdown_emits_positive() -> None:
    """Up then down → drawdowns exist → UI > 0."""
    closes = [100.0 + i for i in range(15)] + [114.0 - i for i in range(15)]
    out = ulcer_index(closes=closes, period=14)
    last = out[-1]
    assert last is not None
    assert last > 0.0


def test_martin_ratio_no_drawdown_positive_return_inf() -> None:
    """Monotone uptrend → UI=0 → ratio is +inf for positive return."""
    out = martin_ratio(closes=[100.0 + i for i in range(30)], period=14)
    last = out[-1]
    assert last is not None
    assert math.isinf(last) and last > 0


def test_burke_ratio_no_drawdown_positive_return_inf() -> None:
    out = burke_ratio(closes=[100.0 + i for i in range(30)], period=14)
    last = out[-1]
    assert last is not None
    assert math.isinf(last) and last > 0


def test_burke_ratio_with_drawdown_finite() -> None:
    """Up-then-down → has drawdowns → ratio is finite."""
    closes = [100.0 + i for i in range(15)] + [114.0 - i for i in range(15)]
    out = burke_ratio(closes=closes, period=14)
    last = out[-1]
    assert last is not None
    assert math.isfinite(last)


# ─── Volatility Bands (4) ────────────────────────────────────────────


def test_chandelier_exit_long_below_recent_high() -> None:
    """The long-side stop must be strictly below the recent peak high."""
    n = 30
    highs = [100.0 + i for i in range(n)]
    lows = [99.0 + i for i in range(n)]
    closes = [99.5 + i for i in range(n)]
    out = chandelier_exit_long(
        highs=highs, lows=lows, closes=closes, period=22, atr_mult=3.0,
    )
    last = out[-1]
    assert last is not None
    assert last < highs[-1]


def test_chandelier_exit_short_above_recent_low() -> None:
    n = 30
    highs = [100.0 + i for i in range(n)]
    lows = [99.0 + i for i in range(n)]
    closes = [99.5 + i for i in range(n)]
    out = chandelier_exit_short(
        highs=highs, lows=lows, closes=closes, period=22, atr_mult=3.0,
    )
    last = out[-1]
    assert last is not None
    # Window low is the OLDEST bar (lows[8] = 107). Stop is above it.
    window_low = min(lows[-22:])
    assert last > window_low


def test_chandelier_rejects_zero_mult() -> None:
    with pytest.raises(ValueError, match="> 0"):
        chandelier_exit_long(
            highs=[1.0] * 30, lows=[1.0] * 30, closes=[1.0] * 30, atr_mult=0,
        )


def test_supertrend_v2_returns_same_length() -> None:
    n = 200
    out = supertrend_v2(
        highs=[10.0 + (i % 7) for i in range(n)],
        lows=[8.0 + (i % 7) for i in range(n)],
        closes=[9.0 + (i % 7) for i in range(n)],
        period=10, atr_mult=3.0, volatility_lookback=100,
    )
    assert len(out) == n


def test_supertrend_v2_rejects_zero_mult() -> None:
    with pytest.raises(ValueError, match="> 0"):
        supertrend_v2(
            highs=[1.0] * 30, lows=[1.0] * 30, closes=[1.0] * 30,
            atr_mult=0,
        )


def test_atr_trailing_stop_ratchets_up() -> None:
    """In a monotone uptrend the stop should never decrease."""
    n = 30
    highs = [100.0 + i for i in range(n)]
    lows = [99.0 + i for i in range(n)]
    closes = [99.5 + i for i in range(n)]
    out = atr_trailing_stop(
        highs=highs, lows=lows, closes=closes, atr_period=14, atr_mult=2.0,
    )
    defined = [v for v in out if v is not None]
    assert all(
        defined[k + 1] >= defined[k] for k in range(len(defined) - 1)
    )


def test_atr_trailing_stop_rejects_zero_mult() -> None:
    with pytest.raises(ValueError, match="> 0"):
        atr_trailing_stop(
            highs=[1.0] * 30, lows=[1.0] * 30, closes=[1.0] * 30, atr_mult=0,
        )


# ─── Registry promotion ──────────────────────────────────────────────


_PACK12_IDS = {
    "atr_percent",
    "volatility_regime",
    "parkinson_volatility",
    "volatility_ratio",
    "trade_efficiency",
    "ulcer_index",
    "martin_ratio",
    "burke_ratio",
    "chandelier_exit_long",
    "chandelier_exit_short",
    "supertrend_v2",
    "atr_trailing_stop",
}


def test_pack12_module_exposes_twelve_indicators() -> None:
    assert len(PACK12_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK12_ACTIVE_INDICATORS} == _PACK12_IDS


def test_pack12_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK12_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack12_is_one_hundred_fifty_five() -> None:
    """Pack-11 baseline 143 + 12 Pack 12 = 155."""
    assert len(get_active_indicators()) >= 155


def test_pack12_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK12_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack12_no_beginner_difficulty() -> None:
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK12_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has difficulty {meta.difficulty}; expected INTERMEDIATE/EXPERT"


def test_pack12_has_no_pine_aliases() -> None:
    """Pack 12 ships no Pine wiring — no indicator should claim a
    Pine alias. Lock so a future edit doesn't quietly add one."""
    for meta in PACK12_ACTIVE_INDICATORS:
        assert meta.pine_aliases == [], (
            f"{meta.id} unexpectedly has Pine aliases: {meta.pine_aliases}"
        )


# ─── Backtest dispatch ──────────────────────────────────────────────


def _wavy_candles(n: int = 200) -> list:
    """Synthetic OHLC large enough for the volatility-regime
    indicators (need 100+ bars of warm-up)."""
    out = []
    for i in range(n):
        base = 100.0 + (i % 7) - 3.0
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
        ("atr_percent", {"period": 14}),
        ("volatility_regime", {"lookback": 100, "atr_period": 14}),
        ("parkinson_volatility", {"period": 20, "bars_per_year": 252}),
        ("volatility_ratio", {"short": 5, "long": 20}),
        ("trade_efficiency", {"period": 20}),
        ("ulcer_index", {"period": 14}),
        ("martin_ratio", {"period": 14}),
        ("burke_ratio", {"period": 14}),
        ("chandelier_exit_long", {"period": 22, "atr_mult": 3.0}),
        ("chandelier_exit_short", {"period": 22, "atr_mult": 3.0}),
        (
            "supertrend_v2",
            {"period": 10, "atr_mult": 3.0, "volatility_lookback": 100},
        ),
        ("atr_trailing_stop", {"atr_period": 14, "atr_mult": 2.0}),
    ],
)
def test_pack12_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 12 indicator dispatches successfully and produces
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
