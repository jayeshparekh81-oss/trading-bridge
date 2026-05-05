"""Boundary tests — grade ranges, verdict bands, and risk-level thresholds.

The grade ranges are inherited from Phase 4 (``TRUST_SCORE_GRADES``),
the verdict bands are Phase 6's
:data:`~app.strategy_engine.truth.constants.TRUTH_VERDICTS`, and the
risk level is a four-band map keyed off total warning count.

These tests pin the *boundaries* — the value at the edge of each band
— so accidental drift in the constants module is caught loudly.
"""

from __future__ import annotations

from app.strategy_engine.backtest.costs import CostSettings
from app.strategy_engine.backtest.runner import AmbiguityMode
from app.strategy_engine.truth import evaluate_strategy_truth
from app.strategy_engine.truth.constants import (
    RISK_LEVEL_THRESHOLDS,
    TRUST_SCORE_GRADES,
    TRUTH_VERDICTS,
)
from tests.strategy_engine.truth.conftest import (
    make_backtest_result,
    make_oos,
    make_reliability,
    make_sensitivity,
    make_strategy,
)

# ─── Static boundary properties ────────────────────────────────────────


def test_grade_ranges_cover_0_to_100_contiguously() -> None:
    """Every score 0-100 maps to exactly one grade."""
    covered: list[tuple[int, int]] = []
    for grade in ("A", "B", "C", "D", "F"):
        low, high = TRUST_SCORE_GRADES[grade]
        covered.append((low, high))
    covered.sort()
    # First range starts at 0, last ends at 100, no gap or overlap.
    assert covered[0][0] == 0
    assert covered[-1][1] == 100
    from itertools import pairwise

    for (_, prev_high), (next_low, _) in pairwise(covered):
        assert next_low == prev_high + 1


def test_truth_verdicts_keyed_by_every_grade() -> None:
    assert set(TRUTH_VERDICTS.keys()) == set(TRUST_SCORE_GRADES.keys())
    # Three distinct verdicts → three bands.
    assert set(TRUTH_VERDICTS.values()) == {
        "Ready for paper trading",
        "Needs improvement",
        "Not ready",
    }


def test_risk_thresholds_are_monotonic_and_non_overlapping() -> None:
    low_max, medium_max, high_max = RISK_LEVEL_THRESHOLDS
    assert 0 <= low_max < medium_max < high_max


# ─── Risk-level mapping at the bucket boundaries ────────────────────────


def test_risk_level_low_when_no_warnings_fire() -> None:
    """Clean strategy → 0 warnings → 'low'."""
    report = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=make_reliability(
            make_backtest_result(
                total_trades=120,
                win_rate=0.58,
                average_win=250.0,
                average_loss=180.0,
                profit_factor=1.8,
                max_drawdown=0.12,
            ),
            sensitivity=make_sensitivity(fragile=False),
        ),
        cost_settings=CostSettings(
            fixed_cost=20.0, percent_cost=0.03, slippage_percent=0.05
        ),
    )
    assert report.risk_level == "low"


def test_risk_level_extreme_when_many_buckets_fire() -> None:
    """A strategy that trips every category lands in 'extreme'."""
    backtest = make_backtest_result(
        total_trades=10,
        win_rate=0.95,
        average_win=80.0,
        average_loss=350.0,
        profit_factor=0.8,
        max_drawdown=0.50,
    )
    report = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=make_reliability(
            backtest,
            out_of_sample=make_oos(degradation_percent=0.40),
            sensitivity=make_sensitivity(fragile=True),
        ),
        # Frictionless costs + optimistic ambiguity = both execution warnings.
        cost_settings=CostSettings(),
        ambiguity_mode=AmbiguityMode.OPTIMISTIC,
    )
    assert report.risk_level == "extreme"
