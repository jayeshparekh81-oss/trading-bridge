"""Pack 2 dispatch wiring — every promoted indicator must compute.

Pack 2 (commit 511f591) registered 15 new active indicators but
left ``precompute_indicators`` unaware of them, so a strategy
referencing one used to silently produce no series. The follow-up
commit added 15 dispatch branches; these tests pin the contract.

For each indicator we run ``precompute_indicators`` over a long
enough candle sequence to seed it past warm-up, then assert:

    * the primary series is present, list-of-length-n;
    * at least one bar is non-None (i.e. the calc actually ran);
    * for multi-output indicators (supertrend / stochastic /
      donchian / keltner) the dotted sub-output ids are also
      populated and the multi-output warning fires.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.schema.ohlcv import Candle
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Test fixtures ─────────────────────────────────────────────────────


def _trending_candles(n: int = 60) -> list[Candle]:
    """Smooth uptrend so every Pack 2 indicator has something
    non-trivial to compute on. Volume varies bar-to-bar so VWMA / MFI
    / Keltner don't divide by a constant."""
    return [
        make_candle(
            minutes=i,
            open_=100.0 + i,
            high=100.5 + i,
            low=99.5 + i,
            close=100.0 + i,
            volume=1_000.0 + i * 10,
        )
        for i in range(n)
    ]


def _wavy_candles(n: int = 80) -> list[Candle]:
    """Sinusoidal close so oscillators (CCI, Williams %R, Stochastic,
    Chande Momentum, ROC, MFI) move through their full range."""
    out: list[Candle] = []
    for i in range(n):
        wave = math.sin(i * 0.25) * 5
        close = 100.0 + wave
        out.append(
            make_candle(
                minutes=i,
                open_=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000.0 + i * 7,
            )
        )
    return out


def _assert_series_seeded(
    series: list[float | None], indicator_id: str
) -> None:
    """The dispatcher must return a same-length list with at least
    one non-None value once the warm-up period clears."""
    assert series, f"{indicator_id}: empty series"
    assert any(v is not None for v in series), (
        f"{indicator_id}: every bar is None — dispatch likely returned []"
    )


# ─── Single-output Pack 2 indicators ──────────────────────────────────


@pytest.mark.parametrize(
    ("indicator_type", "params"),
    [
        ("vwma", {"period": 14, "source": "close"}),
        ("smma", {"period": 14, "source": "close"}),
        ("dema", {"period": 10, "source": "close"}),
        ("tema", {"period": 8, "source": "close"}),
        ("hull_ma", {"period": 9, "source": "close"}),
        ("parabolic_sar", {"step": 0.02, "max_step": 0.2}),
        ("cci", {"period": 14}),
        ("williams_r", {"period": 14}),
        ("chande_momentum", {"period": 9, "source": "close"}),
        ("roc", {"period": 5, "source": "close"}),
        ("mfi", {"period": 14}),
    ],
)
def test_pack2_single_output_indicators_dispatch(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each of the 11 single-output Pack 2 indicators dispatches to
    its calculation function and produces a populated series."""
    candles = _wavy_candles()
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    _assert_series_seeded(primary, indicator_type)
    # No multi-output warning for single-line indicators.
    assert not any(f"{indicator_type}_inst" in w for w in warnings)


# ─── Multi-output Pack 2 indicators ───────────────────────────────────


def test_supertrend_dispatches_with_line_and_direction_extras() -> None:
    candles = _trending_candles()
    strategy = make_strategy(
        indicators=[
            {
                "id": "st_main",
                "type": "supertrend",
                "params": {"period": 10, "multiplier": 3.0},
            }
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    _assert_series_seeded(series["st_main"], "supertrend")
    _assert_series_seeded(series["st_main.line"], "supertrend.line")
    _assert_series_seeded(series["st_main.direction"], "supertrend.direction")
    # Direction values must all be ±1 once seeded.
    seeded_dir = [d for d in series["st_main.direction"] if d is not None]
    assert seeded_dir
    assert set(seeded_dir) <= {1.0, -1.0}
    assert any("st_main" in w and "multi-output" in w for w in warnings)


def test_stochastic_dispatches_with_k_and_d_extras() -> None:
    candles = _wavy_candles()
    strategy = make_strategy(
        indicators=[
            {
                "id": "stoch_main",
                "type": "stochastic",
                "params": {"k_period": 14, "d_period": 3},
            }
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    _assert_series_seeded(series["stoch_main"], "stochastic")
    _assert_series_seeded(series["stoch_main.k"], "stochastic.k")
    _assert_series_seeded(series["stoch_main.d"], "stochastic.d")
    # %K and %D must lie in [0, 100].
    for v in series["stoch_main.k"]:
        if v is not None:
            assert 0.0 <= v <= 100.0
    for v in series["stoch_main.d"]:
        if v is not None:
            assert 0.0 <= v <= 100.0
    assert any("stoch_main" in w and "multi-output" in w for w in warnings)


def test_donchian_channel_dispatches_with_upper_middle_lower_extras() -> None:
    candles = _wavy_candles()
    strategy = make_strategy(
        indicators=[
            {
                "id": "dc_main",
                "type": "donchian_channel",
                "params": {"period": 20},
            }
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    _assert_series_seeded(series["dc_main"], "donchian_channel")
    _assert_series_seeded(series["dc_main.upper"], "donchian.upper")
    _assert_series_seeded(series["dc_main.middle"], "donchian.middle")
    _assert_series_seeded(series["dc_main.lower"], "donchian.lower")
    # Upper >= middle >= lower at every seeded bar.
    for u, m, lo in zip(
        series["dc_main.upper"],
        series["dc_main.middle"],
        series["dc_main.lower"],
        strict=True,
    ):
        if u is None or m is None or lo is None:
            continue
        assert u >= m >= lo
    assert any("dc_main" in w and "multi-output" in w for w in warnings)


def test_keltner_channel_dispatches_with_upper_middle_lower_extras() -> None:
    candles = _trending_candles()
    strategy = make_strategy(
        indicators=[
            {
                "id": "kc_main",
                "type": "keltner_channel",
                "params": {"period": 20, "multiplier": 2.0},
            }
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    _assert_series_seeded(series["kc_main"], "keltner_channel")
    _assert_series_seeded(series["kc_main.upper"], "keltner.upper")
    _assert_series_seeded(series["kc_main.middle"], "keltner.middle")
    _assert_series_seeded(series["kc_main.lower"], "keltner.lower")
    # Bands are symmetric around middle.
    for u, m, lo in zip(
        series["kc_main.upper"],
        series["kc_main.middle"],
        series["kc_main.lower"],
        strict=True,
    ):
        if u is None or m is None or lo is None:
            continue
        upper_gap = u - m
        lower_gap = m - lo
        assert upper_gap == pytest.approx(lower_gap)
    assert any("kc_main" in w and "multi-output" in w for w in warnings)


# ─── Regression — coexistence with existing indicators ────────────────


def test_pack2_indicator_coexists_with_phase1_indicators() -> None:
    """A strategy mixing one Phase 1 indicator (EMA) with two Pack 2
    indicators (Supertrend + CCI) precomputes everything in a single
    pass, with no cross-contamination of the series dict."""
    candles = _trending_candles()
    strategy = make_strategy(
        indicators=[
            {"id": "ema_main", "type": "ema", "params": {"period": 9, "source": "close"}},
            {
                "id": "st_main",
                "type": "supertrend",
                "params": {"period": 10, "multiplier": 3.0},
            },
            {"id": "cci_main", "type": "cci", "params": {"period": 14}},
        ],
    )
    series, _warnings = precompute_indicators(candles, strategy)
    assert {"ema_main", "st_main", "st_main.line", "st_main.direction", "cci_main"} <= series.keys()
    _assert_series_seeded(series["ema_main"], "ema")
    _assert_series_seeded(series["st_main"], "supertrend")
    _assert_series_seeded(series["cci_main"], "cci")
