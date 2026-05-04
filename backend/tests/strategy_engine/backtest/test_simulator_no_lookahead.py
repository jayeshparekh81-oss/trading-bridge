"""No-lookahead invariant — the #1 correctness gate of Phase 3.

The trick: run the backtest twice with the SAME prefix of candles but
DIFFERENT future bars. If the engine peeks ahead, the equity-curve
prefix will differ between runs. If it respects the locked
"signal-on-close, entry-on-next-open" contract, the prefix matches.

We do this two ways:
    1. Truncate test — backtest on candles[0..N] and on candles[0..M]
       (M < N). Equity curve and trades up to bar M-1 must match.
    2. Garbage-future test — replace bars after index k with arbitrary
       (but valid) values; equity curve up to bar k must match.

Both paths fail loudly if the simulator reads any candles[i] when
deciding bar j < i.
"""

from __future__ import annotations

from app.strategy_engine.backtest import BacktestInput, run_backtest
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def _strat() -> StrategyJSON:
    return make_strategy(
        indicators=[{"id": "ema_5", "type": "ema", "params": {"period": 3}}],
        entry_conditions=[
            {"type": "indicator", "left": "ema_5", "op": ">", "value": 99},
        ],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},
    )


def _full_candles() -> list[Candle]:
    """A 12-bar synthetic series with mixed direction so multiple trades fire."""
    return [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100.4, low=99.6, close=100),
        make_candle(minutes=2, open_=100, high=102.5, low=99.6, close=102),
        make_candle(minutes=3, open_=102, high=102, low=99, close=99),
        make_candle(minutes=4, open_=99, high=100, low=99, close=100),
        make_candle(minutes=5, open_=100, high=102.5, low=99.6, close=102),
        make_candle(minutes=6, open_=102, high=102, low=98, close=98.5),
        make_candle(minutes=7, open_=98.5, high=100, low=98.5, close=99.8),
        make_candle(minutes=8, open_=100, high=102.5, low=99.6, close=102),
        make_candle(minutes=9, open_=102, high=102, low=102, close=102),
        make_candle(minutes=10, open_=102, high=102, low=102, close=102),
        make_candle(minutes=11, open_=102, high=102, low=102, close=102),
    ]


def test_truncate_future_does_not_change_past_decisions() -> None:
    """Equity curve up to bar M must match between the full run and the truncated run."""
    full = _full_candles()
    truncate_at = 6  # candles[0..6] inclusive

    full_result = run_backtest(BacktestInput(candles=full, strategy=_strat()))
    truncated_result = run_backtest(
        BacktestInput(candles=full[: truncate_at + 1], strategy=_strat())
    )

    full_prefix = full_result.equity_curve[:truncate_at]
    trunc_prefix = truncated_result.equity_curve[:truncate_at]
    # Don't compare the *last* point of the truncated run because that
    # bar is the truncated run's "end of history" and may force-close
    # an open position; the full run wouldn't.
    assert [pt.equity for pt in full_prefix] == [pt.equity for pt in trunc_prefix]


def test_garbage_future_does_not_change_past_decisions() -> None:
    """Replacing future bars with garbage must leave past equity unchanged."""
    base = _full_candles()
    cutoff = 5

    # Build a "garbage" tail — wildly different prices, valid OHLC.
    garbage_tail = [
        make_candle(minutes=i, open_=999, high=1000, low=998, close=999)
        for i in range(cutoff + 1, len(base))
    ]
    garbage_full = base[: cutoff + 1] + garbage_tail

    base_result = run_backtest(BacktestInput(candles=base, strategy=_strat()))
    garbage_result = run_backtest(BacktestInput(candles=garbage_full, strategy=_strat()))

    # Equity points up to (but not including) the cutoff bar must match —
    # the cutoff bar itself is influenced by the prior bar's close and the
    # current bar's open/range, both of which are the same; bar cutoff+1
    # is where divergence is allowed.
    base_prefix = [pt.equity for pt in base_result.equity_curve[: cutoff + 1]]
    garb_prefix = [pt.equity for pt in garbage_result.equity_curve[: cutoff + 1]]
    assert base_prefix == garb_prefix


def test_indicator_value_never_uses_future_bars() -> None:
    """Indicator pre-compute uses values[0..i] for output[i] — extending the
    series with future values must not change any output[i] for i <= original_end.
    """
    from app.strategy_engine.backtest.indicator_runner import precompute_indicators

    full = _full_candles()
    short = full[:6]

    full_series, _ = precompute_indicators(full, _strat())
    short_series, _ = precompute_indicators(short, _strat())

    # Compare the prefix of each indicator series.
    for name in full_series:
        full_prefix = full_series[name][:6]
        short_full = short_series[name]
        assert full_prefix == short_full, (
            f"Indicator {name!r} prefix differs between full and short runs — "
            "calculation peeked at future data."
        )
