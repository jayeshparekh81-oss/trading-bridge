"""Stop-loss / exit rules from the Phase 7 spec.

    no stop loss -> warn (critical)
    no exit      -> warn (defensive — Phase 1 schema enforces this,
                    so this can only trigger if a future schema
                    relaxation lands)
"""

from __future__ import annotations

from app.strategy_engine.advisor import (
    AdviceCategory,
    AdviceSeverity,
    generate_advice,
)
from tests.strategy_engine.advisor.conftest import make_strategy


def test_missing_stop_loss_emits_critical_advice() -> None:
    """A strategy with only a target and no stop loss is critically flagged."""
    strategy = make_strategy(exit_block={"targetPercent": 2.0})

    report = generate_advice(strategy=strategy)

    missing_sl = [
        a for a in report.advice if a.category == AdviceCategory.MISSING_STOP_LOSS
    ]
    assert len(missing_sl) == 1
    assert missing_sl[0].severity is AdviceSeverity.CRITICAL
    assert "Stop loss is missing" in missing_sl[0].message
    # Critical advice forces paper recommendation off and live off.
    assert report.paper_trading_recommended is False
    assert report.live_trading_recommended is False


def test_trailing_stop_satisfies_stop_loss_rule() -> None:
    """A trailing stop counts as a stop loss for advisor purposes."""
    strategy = make_strategy(
        exit_block={"targetPercent": 2.0, "trailingStopPercent": 0.8},
    )

    report = generate_advice(strategy=strategy)

    assert not any(
        a.category == AdviceCategory.MISSING_STOP_LOSS for a in report.advice
    )
