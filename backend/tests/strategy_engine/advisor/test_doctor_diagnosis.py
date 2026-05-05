"""Strategy Doctor — structured diagnosis output.

Coverage:

    * shape          — Diagnosis matches the master-prompt schema
    * problem types  — exit / risk / overfit / cost / complexity get
                       routed correctly
    * auto-fix       — missing-stop-loss + target produces an
                       improvedStrategyDraft AND original strategy
                       is unchanged (no auto-apply)
    * canAutoImprove — false when no fixable problem exists
    * camelCase JSON — model_dump(by_alias=True) round-trip yields the
                       prompt's wire format
"""

from __future__ import annotations

from app.strategy_engine.advisor import (
    AdviceSeverity,
    Diagnosis,
    ProblemType,
    diagnose_strategy,
)
from tests.strategy_engine.advisor.conftest import (
    make_backtest_result,
    make_oos,
    make_reliability,
    make_sensitivity,
    make_strategy,
    make_truth_report,
)


def test_diagnosis_for_clean_strategy_has_no_problems() -> None:
    backtest = make_backtest_result(max_drawdown=0.10)
    reliability = make_reliability(
        backtest, sensitivity=make_sensitivity(fragile=False)
    )
    truth = make_truth_report(truth_score=92)

    diagnosis = diagnose_strategy(
        strategy=make_strategy(),
        backtest=backtest,
        reliability=reliability,
        truth=truth,
    )

    assert diagnosis.problems == ()
    assert diagnosis.recommended_fixes == ()
    assert diagnosis.can_auto_improve is False
    assert diagnosis.improved_strategy_draft is None
    assert "No problems detected" in diagnosis.diagnosis_summary


def test_missing_stop_loss_with_target_produces_auto_fix_draft() -> None:
    """Doctor must build an improvedStrategyDraft AND not mutate input."""
    strategy = make_strategy(exit_block={"targetPercent": 4.0})
    snapshot = strategy.model_dump_json()

    diagnosis = diagnose_strategy(strategy=strategy)

    # The original strategy is untouched — no auto-apply.
    assert strategy.model_dump_json() == snapshot

    # The diagnosis surfaces a critical RISK problem with auto_fix=True.
    risk_problems = [p for p in diagnosis.problems if p.type is ProblemType.RISK]
    assert risk_problems, "expected a RISK problem"
    fixable = [p for p in risk_problems if p.auto_fix_available]
    assert len(fixable) == 1
    assert fixable[0].severity is AdviceSeverity.CRITICAL

    # The draft is a fresh dict ready to round-trip through the Phase 5
    # CRUD endpoint: stopLossPercent has been inserted at half the target.
    assert diagnosis.can_auto_improve is True
    draft = diagnosis.improved_strategy_draft
    assert draft is not None
    assert draft["exit"]["stopLossPercent"] == 2.0
    assert draft["exit"]["targetPercent"] == 4.0


def test_missing_stop_loss_without_target_emits_problem_but_no_draft() -> None:
    """Without a target to anchor the default stop, there is no draft."""
    strategy = make_strategy(exit_block={"squareOffTime": "15:15"})

    diagnosis = diagnose_strategy(strategy=strategy)

    # Problem still surfaces.
    assert any(
        p.type is ProblemType.RISK and "Stop loss is missing" in p.message
        for p in diagnosis.problems
    )
    # But auto-fix is not available.
    assert diagnosis.can_auto_improve is False
    assert diagnosis.improved_strategy_draft is None


def test_truth_overfit_and_cost_buckets_route_to_typed_problems() -> None:
    truth = make_truth_report(
        truth_score=60, overfitting=True, cost_warning=True
    )

    diagnosis = diagnose_strategy(strategy=make_strategy(), truth=truth)

    types = {p.type for p in diagnosis.problems}
    assert ProblemType.OVERFIT in types
    assert ProblemType.COST in types


def test_indicator_overload_routes_to_complexity_problem() -> None:
    strategy = make_strategy(
        indicators=[
            {"id": f"ema_{p}", "type": "ema", "params": {"period": p}}
            for p in (5, 10, 20, 50, 100, 200)
        ],
    )

    diagnosis = diagnose_strategy(strategy=strategy)

    complexity = [p for p in diagnosis.problems if p.type is ProblemType.COMPLEXITY]
    assert len(complexity) == 1
    assert "6 indicators" in complexity[0].message


def test_diagnosis_serialises_to_master_prompt_camelcase_keys() -> None:
    """model_dump(by_alias=True) matches the wire schema verbatim."""
    truth = make_truth_report(truth_score=40, overfitting=True)
    diagnosis = diagnose_strategy(
        strategy=make_strategy(exit_block={"targetPercent": 4.0}),
        truth=truth,
    )

    dumped = diagnosis.model_dump(by_alias=True, mode="json")
    assert "diagnosisSummary" in dumped
    assert "recommendedFixes" in dumped
    assert "canAutoImprove" in dumped
    assert "improvedStrategyDraft" in dumped
    # Per-problem keys also use the prompt's casing.
    for problem in dumped["problems"]:
        assert "suggestedFix" in problem
        assert "autoFixAvailable" in problem


def test_diagnosis_round_trips_through_pydantic_validation() -> None:
    """Sanity: the Diagnosis schema accepts its own dump."""
    diagnosis = diagnose_strategy(strategy=make_strategy())
    Diagnosis.model_validate(diagnosis.model_dump(by_alias=True, mode="json"))


def test_backtest_high_drawdown_routes_to_risk_problem() -> None:
    backtest = make_backtest_result(max_drawdown=0.45)

    diagnosis = diagnose_strategy(strategy=make_strategy(), backtest=backtest)

    risk_dd = [
        p
        for p in diagnosis.problems
        if p.type is ProblemType.RISK and "Max drawdown" in p.message
    ]
    assert len(risk_dd) == 1


def test_fragile_sensitivity_routes_to_overfit_problem() -> None:
    backtest = make_backtest_result()
    reliability = make_reliability(
        backtest,
        out_of_sample=make_oos(degradation_percent=0.05),
        sensitivity=make_sensitivity(fragile=True),
    )

    diagnosis = diagnose_strategy(
        strategy=make_strategy(), reliability=reliability
    )

    overfit = [p for p in diagnosis.problems if p.type is ProblemType.OVERFIT]
    assert any("fragile" in p.message.lower() for p in overfit)
