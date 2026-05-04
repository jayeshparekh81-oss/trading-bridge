"""Trust-score: low-trade-count warning."""

from __future__ import annotations

from app.strategy_engine.reliability.constants import (
    DEDUCT_LOW_TRADE_COUNT,
    LOW_TRADE_COUNT_THRESHOLD,
)
from app.strategy_engine.reliability.trust_score import calculate_trust_score
from tests.strategy_engine.reliability.conftest import (
    make_low_trade_count_result,
    make_strong_strategy_result,
)


def test_low_trade_count_triggers_warning_and_deduction() -> None:
    bt = make_low_trade_count_result()  # 12 trades
    score = calculate_trust_score(bt)
    assert any("Low trade count" in w for w in score.warnings)
    assert any(f"{LOW_TRADE_COUNT_THRESHOLD}" in c for c in score.failed_checks)


def test_thirty_trades_at_threshold_does_not_warn() -> None:
    bt = make_strong_strategy_result().model_copy(update={"total_trades": 30})
    score = calculate_trust_score(bt)
    assert all("Low trade count" not in w for w in score.warnings)


def test_twenty_nine_trades_under_threshold_warns() -> None:
    bt = make_strong_strategy_result().model_copy(update={"total_trades": 29})
    score = calculate_trust_score(bt)
    assert any("Low trade count" in w for w in score.warnings)


def test_low_trade_count_deduction_amount() -> None:
    """Score on otherwise-strong strategy with 10 trades: 100 - DEDUCT_LOW_TRADE_COUNT."""
    bt = make_strong_strategy_result().model_copy(update={"total_trades": 10})
    score = calculate_trust_score(bt)
    assert score.score == 100 - DEDUCT_LOW_TRADE_COUNT
