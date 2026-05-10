"""Optional inputs — market regime + live deviation.

When the caller does not supply these, the corresponding rules stay
silent (no spurious warnings).
"""

from __future__ import annotations

from app.strategy_engine.advisor import AdviceCategory, generate_advice
from tests.strategy_engine.advisor.conftest import make_strategy


def test_sideways_regime_with_trend_only_strategy_warns() -> None:
    strategy = make_strategy(
        indicators=[{"id": "ema_20", "type": "ema", "params": {"period": 20}}],
    )
    report = generate_advice(strategy=strategy, market_regime="sideways")

    regime_advice = [
        a for a in report.advice if a.category == AdviceCategory.REGIME_MISMATCH
    ]
    assert len(regime_advice) == 1
    assert "sideways" in regime_advice[0].message


def test_no_regime_supplied_does_not_emit_regime_advice() -> None:
    strategy = make_strategy()
    report = generate_advice(strategy=strategy)
    assert not any(
        a.category == AdviceCategory.REGIME_MISMATCH for a in report.advice
    )


def test_deviation_report_with_deviation_emits_warning() -> None:
    report = generate_advice(
        strategy=make_strategy(),
        deviation_report={"has_deviation": True, "magnitude_pct": 4.2},
    )

    live_dev = [
        a for a in report.advice if a.category == AdviceCategory.LIVE_DEVIATION
    ]
    assert len(live_dev) == 1


def test_deviation_report_without_deviation_stays_silent() -> None:
    report = generate_advice(
        strategy=make_strategy(),
        deviation_report={"has_deviation": False},
    )
    assert not any(
        a.category == AdviceCategory.LIVE_DEVIATION for a in report.advice
    )
