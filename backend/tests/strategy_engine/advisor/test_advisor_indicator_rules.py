"""Indicator-coverage rules from the Phase 7 spec.

    only EMA   -> suggest RSI/MACD
    only RSI   -> suggest EMA
    overload   -> warn
"""

from __future__ import annotations

from app.strategy_engine.advisor import (
    AdviceCategory,
    AdviceSeverity,
    generate_advice,
)
from tests.strategy_engine.advisor.conftest import make_strategy


def test_only_trend_indicator_suggests_momentum_confirmation() -> None:
    strategy = make_strategy(
        indicators=[{"id": "ema_20", "type": "ema", "params": {"period": 20}}],
    )
    report = generate_advice(strategy=strategy)

    suggestions = [
        a for a in report.advice if a.category == AdviceCategory.INDICATOR_SUGGESTION
    ]
    assert suggestions, "expected an indicator suggestion"
    assert any("RSI or MACD" in a.message for a in suggestions)


def test_only_momentum_indicator_suggests_trend_anchor() -> None:
    """Conftest auto-repoints the default entry to the new indicator id."""
    strategy = make_strategy(
        indicators=[{"id": "rsi_14", "type": "rsi", "params": {"period": 14}}],
    )

    report = generate_advice(strategy=strategy)

    suggestions = [
        a for a in report.advice if a.category == AdviceCategory.INDICATOR_SUGGESTION
    ]
    assert suggestions
    assert any("EMA or VWAP" in a.message for a in suggestions)


def test_too_many_indicators_triggers_overload_warning() -> None:
    indicators = [
        {"id": f"ema_{p}", "type": "ema", "params": {"period": p}}
        for p in (5, 10, 20, 50, 100, 200)  # 6 indicators > threshold of 5
    ]
    strategy = make_strategy(indicators=indicators)

    report = generate_advice(strategy=strategy)

    overload = [
        a for a in report.advice if a.category == AdviceCategory.INDICATOR_OVERLOAD
    ]
    assert len(overload) == 1
    assert overload[0].severity is AdviceSeverity.WARNING
    assert "6 indicators" in overload[0].message


def test_balanced_trend_plus_momentum_does_not_suggest_indicators() -> None:
    strategy = make_strategy(
        indicators=[
            {"id": "ema_20", "type": "ema", "params": {"period": 20}},
            {"id": "rsi_14", "type": "rsi", "params": {"period": 14}},
        ],
    )
    report = generate_advice(strategy=strategy)
    assert not any(
        a.category == AdviceCategory.INDICATOR_SUGGESTION for a in report.advice
    )
