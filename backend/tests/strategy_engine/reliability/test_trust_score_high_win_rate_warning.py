"""Trust-score: high-win-rate trap warning."""

from __future__ import annotations

from app.strategy_engine.reliability.constants import DEDUCT_SUSPICIOUS_WIN_RATE
from app.strategy_engine.reliability.trust_score import calculate_trust_score
from tests.strategy_engine.reliability.conftest import (
    make_high_win_rate_trap_result,
    make_strong_strategy_result,
)


def test_high_win_rate_with_low_profit_factor_triggers_warning() -> None:
    """90 % win rate + profit factor 1.2 -> suspicious deduction fires."""
    bt = make_high_win_rate_trap_result()
    score = calculate_trust_score(bt)
    assert any("Win rate" in w for w in score.warnings)
    # Score should reflect the suspicious-win-rate deduction (among others).
    assert score.score < 100 - DEDUCT_SUSPICIOUS_WIN_RATE + 1


def test_high_win_rate_with_high_profit_factor_passes() -> None:
    """If profit factor is comfortably above 1.5, the suspicious check
    does NOT fire even with a 90 % win rate (the trap is wins masking
    rare big losses, which a high PF rules out).
    """
    bt = make_strong_strategy_result().model_copy(
        update={"win_rate": 0.92, "loss_rate": 0.08, "profit_factor": 2.5}
    )
    score = calculate_trust_score(bt)
    assert all("suspicious" not in w.lower() for w in score.warnings)


def test_normal_win_rate_does_not_trigger_warning() -> None:
    """Win rate 0.62 is below the 0.85 threshold -> check passes regardless."""
    bt = make_strong_strategy_result()
    score = calculate_trust_score(bt)
    assert all("Win rate" not in w for w in score.warnings)


def test_high_win_rate_with_infinite_profit_factor_passes() -> None:
    """A wins-only deck (no losses ever) sets PF=inf — the trap check
    must treat ``inf`` as comfortably above the cushion threshold.
    """
    import math

    bt = make_strong_strategy_result().model_copy(
        update={
            "win_rate": 0.95,
            "loss_rate": 0.05,
            "profit_factor": math.inf,
        }
    )
    score = calculate_trust_score(bt)
    assert all("Win rate" not in w for w in score.warnings)
