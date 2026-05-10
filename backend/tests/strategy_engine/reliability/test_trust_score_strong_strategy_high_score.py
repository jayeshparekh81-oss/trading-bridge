"""Trust-score: strong strategy gets a high score."""

from __future__ import annotations

from app.strategy_engine.reliability.trust_score import calculate_trust_score
from tests.strategy_engine.reliability.conftest import (
    make_strong_strategy_result,
    make_unprofitable_result,
)


def test_strong_strategy_grades_a() -> None:
    """A strategy that passes every check should score 100 and grade A."""
    bt = make_strong_strategy_result()
    score = calculate_trust_score(bt)
    assert score.score == 100
    assert score.grade == "A"
    assert score.failed_checks == ()
    assert score.warnings == ()


def test_strong_strategy_with_clean_optionals_still_grades_a() -> None:
    bt = make_strong_strategy_result()
    score = calculate_trust_score(
        bt,
        oos_degradation=0.05,  # well under 0.25
        walk_forward_consistency=0.80,  # above 0.60
        sensitivity_fragile=False,
    )
    assert score.score == 100
    assert score.grade == "A"


def test_unprofitable_strategy_grades_far_below_strong() -> None:
    weak = calculate_trust_score(make_unprofitable_result())
    strong = calculate_trust_score(make_strong_strategy_result())
    assert weak.score < strong.score
    assert weak.grade in ("D", "F")


def test_strong_strategy_lists_passed_checks() -> None:
    """A strong baseline should populate ``passed_checks`` with at least
    the four core checks (trade count, profit factor, drawdown, RR).
    """
    score = calculate_trust_score(make_strong_strategy_result())
    joined = " | ".join(score.passed_checks)
    assert "Trade count" in joined
    assert "Profit factor" in joined
    assert "Max drawdown" in joined
    assert "Risk-reward" in joined
