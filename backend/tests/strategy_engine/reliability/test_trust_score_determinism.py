"""Trust-score: deterministic — same input always returns same TrustScore."""

from __future__ import annotations

from app.strategy_engine.reliability.trust_score import calculate_trust_score
from tests.strategy_engine.reliability.conftest import (
    make_high_win_rate_trap_result,
    make_low_trade_count_result,
    make_strong_strategy_result,
    make_unprofitable_result,
)


def test_run_twice_same_input_returns_same_trust_score() -> None:
    bt = make_strong_strategy_result()
    a = calculate_trust_score(bt)
    b = calculate_trust_score(bt)
    assert a == b


def test_optional_inputs_do_not_introduce_nondeterminism() -> None:
    bt = make_strong_strategy_result()
    a = calculate_trust_score(
        bt,
        oos_degradation=0.10,
        walk_forward_consistency=0.80,
        sensitivity_fragile=False,
    )
    b = calculate_trust_score(
        bt,
        oos_degradation=0.10,
        walk_forward_consistency=0.80,
        sensitivity_fragile=False,
    )
    assert a == b


def test_each_baseline_is_self_consistent() -> None:
    """Every helper baseline must produce identical scores on repeat call."""
    for builder in (
        make_strong_strategy_result,
        make_unprofitable_result,
        make_low_trade_count_result,
        make_high_win_rate_trap_result,
    ):
        bt = builder()
        first = calculate_trust_score(bt)
        second = calculate_trust_score(bt)
        assert first == second, f"{builder.__name__} is non-deterministic"
