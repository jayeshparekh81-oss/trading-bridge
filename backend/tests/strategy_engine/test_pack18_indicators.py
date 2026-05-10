"""Pack 18 - final 15 indicators. MILESTONE: 230 active.

Mirrors Pack 2-17 test shape. Includes the campaign-defining
``test_active_count_after_pack18_is_230`` milestone assertion.

Stub contracts pinned for nse_bse_arbitrage_proxy and
nifty_50_relative_position. ttm_squeeze coming-soon-promotion
verified (status now ACTIVE, calculation_function set).

Pine wiring: ta.mom -> momentum_oscillator (the only documented
Pine alias in Pack 18).
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack18_active import (
    PACK18_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators.calculations.consecutive_higher_lows import (
    consecutive_higher_lows,
)
from app.strategy_engine.indicators.calculations.fno_lot_size_atr import (
    fno_lot_size_atr,
)
from app.strategy_engine.indicators.calculations.momentum_oscillator import (
    momentum_oscillator,
)
from app.strategy_engine.indicators.calculations.negative_volume_index_signal import (
    negative_volume_index_signal,
)
from app.strategy_engine.indicators.calculations.nifty_50_relative_position import (
    HAS_SYMBOL_CONTEXT,
    nifty_50_relative_position,
)
from app.strategy_engine.indicators.calculations.nse_bse_arbitrage_proxy import (
    HAS_DUAL_EXCHANGE,
    nse_bse_arbitrage_proxy,
)
from app.strategy_engine.indicators.calculations.positive_volume_index_signal import (
    positive_volume_index_signal,
)
from app.strategy_engine.indicators.calculations.price_momentum_index import (
    price_momentum_index,
)
from app.strategy_engine.indicators.calculations.roc_smoothed import (
    roc_smoothed,
)
from app.strategy_engine.indicators.calculations.trend_age_bars import (
    trend_age_bars,
)
from app.strategy_engine.indicators.calculations.trend_momentum_combo import (
    trend_momentum_combo,
)
from app.strategy_engine.indicators.calculations.ttm_squeeze import ttm_squeeze
from app.strategy_engine.indicators.calculations.ttm_squeeze_pro import (
    ttm_squeeze_pro,
)
from app.strategy_engine.indicators.calculations.volume_zone_oscillator import (
    volume_zone_oscillator,
)
from app.strategy_engine.indicators.calculations.weekly_trend_strength import (
    weekly_trend_strength,
)
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# --- Trend completers (5) -------------------------------------------


def _wavy_closes(n: int = 300, base: float = 24500.0) -> list[float]:
    return [base + math.sin(i * 0.1) * 50.0 for i in range(n)]


def _wavy_hl(closes: list[float]) -> tuple[list[float], list[float]]:
    return [c + 30 for c in closes], [c - 30 for c in closes]


def test_ttm_squeeze_emits_zero_one_only() -> None:
    closes = _wavy_closes()
    highs, lows = _wavy_hl(closes)
    out = ttm_squeeze(highs=highs, lows=lows, closes=closes)
    defined = [v for v in out if v is not None]
    assert defined and all(v in (0.0, 1.0) for v in defined)


def test_ttm_squeeze_rejects_zero_kc_mult() -> None:
    with pytest.raises(ValueError, match="kc_mult"):
        ttm_squeeze(highs=[1.0] * 30, lows=[0.0] * 30, closes=[0.5] * 30, kc_mult=0)


def test_ttm_squeeze_pro_emits_zero_to_three() -> None:
    closes = _wavy_closes()
    highs, lows = _wavy_hl(closes)
    out = ttm_squeeze_pro(highs=highs, lows=lows, closes=closes)
    defined = [v for v in out if v is not None]
    assert defined and all(v in (0.0, 1.0, 2.0, 3.0) for v in defined)


def test_ttm_squeeze_pro_rejects_low_ge_high_mult() -> None:
    with pytest.raises(ValueError, match="low_volatility_mult"):
        ttm_squeeze_pro(
            highs=[1.0] * 30, lows=[0.0] * 30, closes=[0.5] * 30,
            low_volatility_mult=2.0, high_volatility_mult=2.0,
        )


def test_weekly_trend_strength_perfect_uptrend_yields_hundred() -> None:
    """Closes strictly increasing -> all 4 weeks bullish -> 100."""
    closes = [100.0 + i for i in range(30)]
    out = weekly_trend_strength(closes=closes, weeks=4)
    last = out[-1]
    assert last is not None and last == pytest.approx(100.0)


def test_weekly_trend_strength_alternating_weeks() -> None:
    """Build closes where 5-bar blocks alternate up/down direction.
    With weeks=4, expect ~50%."""
    closes: list[float] = [100.0]
    direction = 1
    for _w in range(8):
        for _ in range(5):
            closes.append(closes[-1] + direction)
        direction *= -1
    out = weekly_trend_strength(closes=closes, weeks=4)
    last = out[-1]
    assert last is not None and last == pytest.approx(50.0, abs=25.0)


def test_weekly_trend_strength_rejects_low_weeks() -> None:
    with pytest.raises(ValueError, match=">= 2"):
        weekly_trend_strength(closes=[1.0] * 50, weeks=1)


def test_trend_age_bars_increments_after_cross() -> None:
    """Build a down-then-up series so an EMA cross occurs at the
    flip; trend_age should reset to 0 at the cross and increment
    monotonically after."""
    closes = [100.0 - i * 0.5 for i in range(50)] + [75.0 + i * 1.0 for i in range(60)]
    out = trend_age_bars(closes=closes, ema_fast=12, ema_slow=26)
    defined = [v for v in out if v is not None]
    assert defined
    assert min(defined) == 0.0
    assert defined[-1] > 0.0


def test_trend_age_bars_rejects_fast_ge_slow() -> None:
    with pytest.raises(ValueError, match="ema_slow"):
        trend_age_bars(closes=[1.0] * 30, ema_fast=20, ema_slow=20)


def test_consecutive_higher_lows_perfect_uptrend_caps_at_lookback() -> None:
    lows = [100.0 + i for i in range(20)]
    out = consecutive_higher_lows(lows=lows, lookback=10)
    assert out[-1] == 10.0
    assert out[0] == 0.0


def test_consecutive_higher_lows_resets_on_break() -> None:
    """Three HLs, then a break, then the count should reset to 0."""
    lows = [100.0, 101.0, 102.0, 103.0, 99.0, 100.0, 101.0]
    out = consecutive_higher_lows(lows=lows, lookback=10)
    assert out == [0.0, 1.0, 2.0, 3.0, 0.0, 1.0, 2.0]


def test_consecutive_higher_lows_rejects_zero_lookback() -> None:
    with pytest.raises(ValueError, match="positive int"):
        consecutive_higher_lows(lows=[1.0] * 10, lookback=0)


# --- Momentum completers (4) ----------------------------------------


def test_roc_smoothed_constant_input_yields_zero() -> None:
    out = roc_smoothed(closes=[100.0] * 50, roc_period=10, smooth_period=5)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0, abs=1e-9) for v in defined)


def test_roc_smoothed_linear_input_positive() -> None:
    closes = [100.0 + i for i in range(50)]
    out = roc_smoothed(closes=closes, roc_period=10, smooth_period=5)
    defined = [v for v in out if v is not None]
    assert defined and all(v > 0 for v in defined)


def test_momentum_oscillator_classic_diff() -> None:
    """ta.mom equivalent: close[i] - close[i-period]."""
    closes = [100.0 + i for i in range(20)]
    out = momentum_oscillator(closes=closes, period=10)
    # At i=10: 110 - 100 = 10
    assert out[10] == pytest.approx(10.0)
    assert out[19] == pytest.approx(10.0)


def test_momentum_oscillator_warmup() -> None:
    out = momentum_oscillator(closes=[1.0] * 20, period=10)
    assert all(v is None for v in out[:10])
    assert all(v == 0.0 for v in out[10:])


def test_price_momentum_index_constant_yields_zero() -> None:
    out = price_momentum_index(closes=[100.0] * 30, period=14)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0) for v in defined)


def test_price_momentum_index_uptrend_positive() -> None:
    closes = [100.0 + i for i in range(40)]
    out = price_momentum_index(closes=closes, period=14)
    defined = [v for v in out if v is not None]
    assert defined and all(v > 0 for v in defined)


def test_trend_momentum_combo_uptrend_aligned_positive() -> None:
    closes = [100.0 + i for i in range(80)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    out = trend_momentum_combo(
        highs=highs, lows=lows, closes=closes, trend_period=20, momentum_period=10,
    )
    defined = [v for v in out if v is not None]
    assert defined and all(v > 0 for v in defined)


def test_trend_momentum_combo_rejects_low_trend_period() -> None:
    with pytest.raises(ValueError, match="trend_period"):
        trend_momentum_combo(
            highs=[1.0] * 50, lows=[0.0] * 50, closes=[0.5] * 50, trend_period=1,
        )


# --- Volume completers (3) ------------------------------------------


def test_volume_zone_oscillator_in_minus_to_plus_hundred() -> None:
    closes = _wavy_closes()
    volumes = [1000.0 + i for i in range(len(closes))]
    out = volume_zone_oscillator(closes=closes, volumes=volumes, period=14)
    defined = [v for v in out if v is not None]
    assert defined and all(-100.0 <= v <= 100.0 for v in defined)


def test_volume_zone_oscillator_uptrend_positive() -> None:
    closes = [100.0 + i for i in range(50)]
    volumes = [1000.0] * 50
    out = volume_zone_oscillator(closes=closes, volumes=volumes, period=14)
    defined = [v for v in out if v is not None]
    assert defined and all(v > 0 for v in defined)


def test_pvi_signal_emits_smoothed_pvi() -> None:
    closes = [100.0 + i * 0.5 for i in range(60)]
    volumes = [1000.0 + i * 10 for i in range(60)]
    out = positive_volume_index_signal(closes=closes, volumes=volumes, signal_period=10)
    defined = [v for v in out if v is not None]
    assert defined
    assert all(v > 0 for v in defined)


def test_nvi_signal_emits_smoothed_nvi() -> None:
    closes = [100.0 + i * 0.5 for i in range(60)]
    volumes = [1000.0 - i * 5 for i in range(60)]
    out = negative_volume_index_signal(closes=closes, volumes=volumes, signal_period=10)
    defined = [v for v in out if v is not None]
    assert defined
    assert all(v > 0 for v in defined)


def test_pvi_signal_rejects_low_period() -> None:
    with pytest.raises(ValueError, match=">= 2"):
        positive_volume_index_signal(closes=[1.0] * 10, volumes=[1.0] * 10, signal_period=1)


# --- India-specific (3, 2 stubs) -----------------------------------


def test_fno_lot_size_atr_multiplies_atr_by_lot() -> None:
    """ATR * lot. With a constant 1.0 range, ATR -> 1.0. Lot=50
    -> output 50.0."""
    n = 50
    out = fno_lot_size_atr(
        highs=[101.0] * n, lows=[100.0] * n, closes=[100.5] * n,
        atr_period=14, assumed_lot_size=50,
    )
    defined = [v for v in out if v is not None]
    assert defined and all(v == pytest.approx(50.0, abs=1.0) for v in defined)


def test_fno_lot_size_atr_rejects_zero_lot() -> None:
    with pytest.raises(ValueError, match="assumed_lot_size"):
        fno_lot_size_atr(
            highs=[1.0] * 30, lows=[0.0] * 30, closes=[0.5] * 30, assumed_lot_size=0,
        )


def test_nse_bse_arbitrage_proxy_is_phase1_stub() -> None:
    out = nse_bse_arbitrage_proxy(closes=[100.0] * 50)
    assert len(out) == 50
    assert all(v is None for v in out)


def test_nse_bse_arbitrage_proxy_flag() -> None:
    assert HAS_DUAL_EXCHANGE is False


def test_nse_bse_arbitrage_proxy_rejects_zero_threshold() -> None:
    with pytest.raises(ValueError, match="spread_threshold_pct"):
        nse_bse_arbitrage_proxy(closes=[1.0] * 10, spread_threshold_pct=0)


def test_nifty_50_relative_position_is_phase1_stub() -> None:
    out = nifty_50_relative_position(closes=[100.0] * 50)
    assert len(out) == 50
    assert all(v is None for v in out)


def test_nifty_50_relative_position_flag() -> None:
    assert HAS_SYMBOL_CONTEXT is False


def test_nifty_50_relative_position_rejects_low_lookback() -> None:
    with pytest.raises(ValueError, match=">= 2"):
        nifty_50_relative_position(closes=[1.0] * 10, lookback=1)


# --- Locks ---------------------------------------------------------


def test_pack18_only_documented_pine_aliases() -> None:
    """Only momentum_oscillator carries a Pine alias (ta.mom).
    Lock test pins this."""
    expected_aliases: dict[str, list[str]] = {
        "momentum_oscillator": ["ta.mom"],
    }
    for meta in PACK18_ACTIVE_INDICATORS:
        expected = expected_aliases.get(meta.id, [])
        assert meta.pine_aliases == expected, (
            f"{meta.id} pine_aliases mismatch: got {meta.pine_aliases}, "
            f"expected {expected}"
        )


def test_pack18_no_beginner_difficulty() -> None:
    from app.strategy_engine.schema.indicator import IndicatorDifficulty
    for meta in PACK18_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has unexpected difficulty {meta.difficulty}"


def test_pack18_stubs_documented_in_descriptions() -> None:
    """Lock test: stub indicators must say STUB in description."""
    for stub_id in ("nse_bse_arbitrage_proxy", "nifty_50_relative_position"):
        meta = INDICATOR_REGISTRY[stub_id]
        assert "STUB" in meta.description.upper(), (
            f"{stub_id} description must say STUB (got: {meta.description!r})"
        )


def test_pack18_ttm_squeeze_promoted_to_active() -> None:
    """ttm_squeeze was COMING_SOON in Phase 9; Pack 18 promotes it
    to ACTIVE via the splat-after-coming-soon pattern."""
    meta = INDICATOR_REGISTRY["ttm_squeeze"]
    assert meta.status == IndicatorStatus.ACTIVE
    assert meta.calculation_function == "ttm_squeeze"


def test_pack18_ids_present_in_registry() -> None:
    expected = {meta.id for meta in PACK18_ACTIVE_INDICATORS}
    assert len(expected) == 15
    for ind_id in expected:
        assert ind_id in INDICATOR_REGISTRY, f"{ind_id} missing from registry"


def test_active_count_after_pack18_is_230() -> None:
    """MILESTONE: 230 ACTIVE INDICATORS reached."""
    active = [
        m for m in INDICATOR_REGISTRY.values()
        if m.status == IndicatorStatus.ACTIVE
    ]
    assert len(active) >= 230, (
        f"230 ACTIVE TARGET MISSED: got {len(active)}"
    )


def test_pine_ta_mom_promoted_out_of_coming_soon() -> None:
    """ta.mom was in _COMING_SOON_PINE_TO_REGISTRY; Pack 18 promoted it."""
    from app.strategy_engine.pine_import.mapper import (
        _COMING_SOON_PINE_TO_REGISTRY,
    )
    assert "mom" not in _COMING_SOON_PINE_TO_REGISTRY


# --- Backtest dispatch ---------------------------------------------


def _wavy_intraday_candles(n: int = 300) -> list:
    """Synthetic candles for dispatch coverage."""
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
        ("ttm_squeeze", {"bb_period": 20, "kc_period": 20, "bb_std": 2.0, "kc_mult": 1.5}),
        (
            "ttm_squeeze_pro",
            {"bb_period": 20, "kc_period": 20, "low_volatility_mult": 1.0, "high_volatility_mult": 2.0},
        ),
        ("weekly_trend_strength", {"weeks": 4}),
        ("trend_age_bars", {"ema_fast": 12, "ema_slow": 26}),
        ("consecutive_higher_lows", {"lookback": 10}),
        ("roc_smoothed", {"roc_period": 10, "smooth_period": 5}),
        ("momentum_oscillator", {"period": 10}),
        ("price_momentum_index", {"period": 14}),
        ("trend_momentum_combo", {"trend_period": 50, "momentum_period": 14}),
        ("volume_zone_oscillator", {"period": 14}),
        ("positive_volume_index_signal", {"signal_period": 30}),
        ("negative_volume_index_signal", {"signal_period": 30}),
        ("fno_lot_size_atr", {"atr_period": 14, "assumed_lot_size": 50}),
        ("nse_bse_arbitrage_proxy", {"spread_threshold_pct": 0.1}),
        ("nifty_50_relative_position", {"lookback": 30}),
    ],
)
def test_pack18_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object],
) -> None:
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


# --- Pine importer wiring for ta.mom -------------------------------


def test_pine_ta_mom_maps_to_momentum_oscillator() -> None:
    """ta.mom(close, 14) -> momentum_oscillator with period=14."""
    from app.strategy_engine.pine_import.converter import (
        convert_pine_to_strategy,
    )
    src = """\
//@version=5
strategy("test")
m = ta.mom(close, 14)
if m > 0
    strategy.entry("long", strategy.long)
"""
    result = convert_pine_to_strategy(src)
    assert result.get("success"), f"Pine import failed: {result!r}"
    indicators = result["strategy"]["indicators"]
    mom_inds = [i for i in indicators if i["type"] == "momentum_oscillator"]
    assert mom_inds, f"Expected momentum_oscillator in {indicators!r}"
    assert mom_inds[0]["params"]["period"] == 14
