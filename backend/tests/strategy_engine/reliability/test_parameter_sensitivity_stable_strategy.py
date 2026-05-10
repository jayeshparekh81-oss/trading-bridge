"""Parameter sensitivity: a stable strategy should not be flagged fragile."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.strategy_engine.reliability.parameter_sensitivity import (
    VariantOutcome,
    _summarise,
    run_sensitivity,
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
    return StrategyJSON.model_validate(
        {
            "id": "s",
            "name": "test",
            "mode": "expert",
            "indicators": [
                {"id": "ema_20", "type": "ema", "params": {"period": 20}},
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


def test_strategy_with_no_trading_signals_has_no_degradation() -> None:
    """Flat candles -> zero trades -> identical (terrible) score across
    variants. The variants are all equivalently bad, so degradation
    should be zero and ``fragile`` False.
    """
    result = run_sensitivity(strategy=_strategy(), candles=_candles(40))
    assert result.fragile is False
    # Stability score is 1.0 when no variant degraded.
    assert result.stability_score == 1.0


def test_summarise_with_no_variants_is_stable() -> None:
    fragile, stability, warning = _summarise([])
    assert fragile is False
    assert stability == 1.0
    assert warning == ""


def test_summarise_below_fragile_threshold_is_stable() -> None:
    """30 % degraded is at the threshold (strict >), so still stable."""
    variants = [
        VariantOutcome(
            param_path=f"p_{i}",
            base_value=10.0,
            variant_value=11.0,
            variation_pct=0.10,
            score=80,
            score_delta=-21 if i < 3 else 0,  # 3 / 10 = 30 % degraded
            degraded=i < 3,
        )
        for i in range(10)
    ]
    fragile, stability, _ = _summarise(variants)
    assert fragile is False
    assert stability == 0.7


def test_run_sensitivity_returns_stable_score_close_to_one() -> None:
    """A run on a healthy strategy + flat data should yield stability 1.0."""
    result = run_sensitivity(strategy=_strategy(), candles=_candles(30))
    assert 0 <= result.stability_score <= 1
    assert result.fragile is False
