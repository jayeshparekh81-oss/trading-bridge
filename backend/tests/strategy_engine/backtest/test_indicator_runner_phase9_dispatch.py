"""Phase 9b — backtest dispatch wiring for the new active indicators.

Three integration tests covering the three shapes of dispatch the
runner now handles:

    1. Single-output (ADX) — primary stored under ``cfg.id`` only;
       no extras, no multi-output warning.
    2. Multi-output (Pivot Points) — primary stored under ``cfg.id`` AND
       five dotted sub-ids (``pp``, ``r1``, ``r2``, ``s1``, ``s2``);
       the multi-output warning fires.
    3. End-to-end ``run_backtest`` driving an Aroon-oscillator entry —
       proves the new dispatch threads through the simulator without
       crashing and emits a coherent :class:`BacktestResult`.

These tests pin the runner contract; the per-calculation correctness
is owned by the focused calculation tests in ``test_adx.py`` /
``test_aroon.py`` / ``test_pivot_points.py``.
"""

from __future__ import annotations

import math

from app.strategy_engine.backtest import BacktestInput, run_backtest
from app.strategy_engine.backtest.indicator_runner import (
    precompute_indicators,
    values_at,
)
from app.strategy_engine.schema.ohlcv import Candle
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def _trending_candles(n: int = 60) -> list[Candle]:
    """Steady uptrend so all the new indicators have something non-trivial
    to compute on."""
    return [
        make_candle(
            minutes=i,
            open_=100.0 + i,
            high=100.5 + i,
            low=99.5 + i,
            close=100.0 + i,
        )
        for i in range(n)
    ]


# ─── 1. Single-output dispatch: ADX ────────────────────────────────────


def test_runner_dispatches_adx_as_single_output() -> None:
    """ADX returns one series under cfg.id with no extras and no warning."""
    candles = _trending_candles()
    strategy = make_strategy(
        indicators=[
            {"id": "adx_default", "type": "adx", "params": {"period": 14}},
        ],
    )

    series, warnings = precompute_indicators(candles, strategy)

    assert "adx_default" in series
    assert len(series["adx_default"]) == len(candles)
    # Single-output ⇒ no dotted sub-ids registered.
    dotted = [k for k in series if k.startswith("adx_default.")]
    assert dotted == []
    # ADX seeds at index 2*period - 1 = 27 — assert the line is non-None
    # past the seed and zero or positive (ADX is unsigned).
    assert series["adx_default"][27] is not None
    last = series["adx_default"][-1]
    assert last is not None
    assert last >= 0
    # No multi-output warning for a single-output indicator.
    assert not any("adx_default" in w for w in warnings)


# ─── 2. Multi-output dispatch: Pivot Points ───────────────────────────


def test_runner_dispatches_pivot_points_with_all_dotted_sub_ids() -> None:
    """Pivot Points stores the primary (PP) and five dotted lines."""
    candles = _trending_candles(n=20)
    strategy = make_strategy(
        indicators=[
            {"id": "pp_default", "type": "pivot_points", "params": {}},
        ],
    )

    series, warnings = precompute_indicators(candles, strategy)

    # Primary maps to the pivot value PP.
    assert "pp_default" in series
    assert len(series["pp_default"]) == len(candles)
    # All five sub-outputs accessible via dotted ids.
    for suffix in ("pp", "r1", "r2", "s1", "s2"):
        key = f"pp_default.{suffix}"
        assert key in series, f"missing dotted sub-id {key!r}"
        assert len(series[key]) == len(candles)
    # Hot-loop access at the last bar succeeds for every series.
    snapshot = values_at(series, len(candles) - 1)
    pp_val = snapshot["pp_default"]
    r1_val = snapshot["pp_default.r1"]
    s1_val = snapshot["pp_default.s1"]
    s2_val = snapshot["pp_default.s2"]
    assert pp_val is not None
    assert r1_val is not None
    assert s1_val is not None
    assert s2_val is not None
    # In an uptrend resistance lies above the pivot; support below.
    assert r1_val > pp_val
    assert s1_val < pp_val
    # Multi-output warning fires.
    assert any("pp_default" in w and "multi-output" in w for w in warnings)


# ─── 3. End-to-end backtest with an Aroon entry ───────────────────────


def test_run_backtest_completes_with_aroon_oscillator_entry() -> None:
    """A strategy referencing aroon's primary (oscillator) runs end-to-end.

    The oscillator goes positive in a trending-up regime; the entry rule
    ``aroon_default > 0`` therefore fires on the post-warmup bars.
    """
    strategy = make_strategy(
        indicators=[
            {"id": "aroon_default", "type": "aroon", "params": {"period": 5}},
        ],
        entry_conditions=[
            {"type": "indicator", "left": "aroon_default", "op": ">", "value": 0.0},
        ],
        exit_block={"targetPercent": 1.0, "stopLossPercent": 1.0},
    )
    payload = BacktestInput(
        candles=_trending_candles(n=40),
        strategy=strategy,
        initial_capital=100_000.0,
        quantity=1,
    )

    result = run_backtest(payload)

    # Coherence: result fields validate against the BacktestResult schema
    # and the equity curve has one point per bar.
    assert len(result.equity_curve) == 40
    assert math.isfinite(result.total_pnl)
    assert math.isfinite(result.total_return_percent)
    assert 0.0 <= result.win_rate <= 1.0
    # The runner emits a multi-output warning for aroon — surfaces in the
    # BacktestResult.warnings list.
    assert any("aroon_default" in w and "multi-output" in w for w in result.warnings)
