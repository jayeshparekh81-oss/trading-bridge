"""Reliability report — end-to-end integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.strategy_engine.reliability import (
    ReliabilityReport,
    build_reliability_report,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def _candles(n: int) -> list[Candle]:
    return [
        Candle(
            timestamp=T0 + timedelta(minutes=i),
            open=100,
            high=100,
            low=100,
            close=100,
            volume=1000,
        )
        for i in range(n)
    ]


def _strategy() -> StrategyJSON:
    """A small-period EMA so the strategy fits inside walk-forward / OOS
    sub-segments. Phase 3's indicator runner returns an empty series when
    ``period > len(candles)`` and the simulator then raises IndexError —
    using ema_5 keeps every Phase 4 sub-analysis above the minimum.
    """
    return StrategyJSON.model_validate(
        {
            "id": "s",
            "name": "test",
            "mode": "expert",
            "indicators": [
                {"id": "ema_5", "type": "ema", "params": {"period": 5}},
            ],
            "entry": {
                "side": "BUY",
                "operator": "AND",
                "conditions": [{"type": "price", "op": ">", "value": 99.5}],
            },
            "exit": {"targetPercent": 2, "stopLossPercent": 1},
            "execution": {
                "mode": "backtest",
                "orderType": "MARKET",
                "productType": "INTRADAY",
            },
        }
    )


def test_full_report_runs_end_to_end_with_all_analyses() -> None:
    report = build_reliability_report(
        strategy=_strategy(),
        candles=_candles(100),
    )
    assert isinstance(report, ReliabilityReport)
    assert report.out_of_sample is not None
    assert report.walk_forward is not None
    assert report.sensitivity is not None
    # Trust-score range invariants.
    assert 0 <= report.trust_score.score <= 100
    assert report.trust_score.grade in {"A", "B", "C", "D", "F"}


def test_report_skips_walk_forward_when_data_too_short() -> None:
    """20 candles is the WF minimum; 15 candles should skip WF gracefully."""
    report = build_reliability_report(
        strategy=_strategy(),
        candles=_candles(15),
    )
    assert report.walk_forward is None
    # OOS still runs (4-candle minimum).
    assert report.out_of_sample is not None


def test_report_respects_explicit_skip_flags() -> None:
    report = build_reliability_report(
        strategy=_strategy(),
        candles=_candles(100),
        include_oos=False,
        include_walk_forward=False,
        include_sensitivity=False,
    )
    assert report.out_of_sample is None
    assert report.walk_forward is None
    assert report.sensitivity is None


def test_report_round_trips_through_json() -> None:
    report = build_reliability_report(
        strategy=_strategy(),
        candles=_candles(100),
    )
    blob = report.model_dump_json()
    rehydrated = ReliabilityReport.model_validate_json(blob)
    assert rehydrated == report


def test_report_is_deterministic_across_runs() -> None:
    """Two runs over identical inputs must produce identical reports."""
    a = build_reliability_report(strategy=_strategy(), candles=_candles(100))
    b = build_reliability_report(strategy=_strategy(), candles=_candles(100))
    assert a == b


def test_trust_score_consumes_optional_inputs_when_provided() -> None:
    """When OOS / WF / sensitivity run, the trust score should reflect
    those checks in its passed_checks / failed_checks lists.
    """
    report = build_reliability_report(
        strategy=_strategy(),
        candles=_candles(100),
    )
    joined = " | ".join(report.trust_score.passed_checks + report.trust_score.failed_checks)
    # OOS, WF, and sensitivity checks must be present.
    assert "Out-of-sample" in joined
    assert "Walk-forward" in joined
    assert "robust" in joined or "Strategy is" in joined
