"""Top-level Strategy Coach entrypoint.

Assembles a :class:`StrategyHealthCard` from a Phase 3
:class:`BacktestResult` (and optionally a Phase 4
:class:`ReliabilityReport`).

Pipeline::

    backtest → 7 metric values → 7 metric grades → 7 metric tips
                                 ↓
                      overall score (avg x 25)
                                 ↓
                      A-F grade → summary + next steps
                                 ↓
                      learning tips (driven by grade + reliability)

The function is pure: same inputs always produce the same output.
``test_two_runs_produce_identical_card`` pins this.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from app.strategy_engine.coach.models import (
    MetricGrade,
    MetricGradeLevel,
    OverallGrade,
    StrategyHealthCard,
)
from app.strategy_engine.coach.rubric import (
    EXPECTANCY_RUBRIC,
    GRADE_WEIGHTS,
    MAX_DRAWDOWN_RUBRIC,
    PROFIT_FACTOR_RUBRIC,
    RECOVERY_FACTOR_RUBRIC,
    RISK_REWARD_RUBRIC,
    TOTAL_TRADES_RUBRIC,
    WIN_RATE_RUBRIC,
    MetricRubric,
    classify_expectancy,
    classify_max_drawdown,
    classify_profit_factor,
    classify_recovery_factor,
    classify_risk_reward,
    classify_total_trades,
    classify_win_rate,
)
from app.strategy_engine.coach.tips import (
    expectancy_tip,
    max_drawdown_tip,
    profit_factor_tip,
    recovery_factor_tip,
    risk_reward_tip,
    total_trades_tip,
    win_rate_tip,
)

if TYPE_CHECKING:
    from app.strategy_engine.backtest.runner import BacktestResult
    from app.strategy_engine.reliability.reliability_report import (
        ReliabilityReport,
    )


# ─── Overall summary + next steps per grade ──────────────────────────


_OVERALL_SUMMARY: dict[OverallGrade, str] = {
    "A": (
        "Strategy strong hai - paper trading shuru karo. Real money lagane se "
        "pehle 7 sessions complete karo."
    ),
    "B": (
        "Strategy theek hai - 1-2 metrics mein improvements kar sakte ho. "
        "Doctor module check karo."
    ),
    "C": (
        "Strategy workable but kuch weak metrics hain. Pehle inhe fix karo "
        "phir paper trading."
    ),
    "D": (
        "Strategy mein significant issues hain. Risk parameters aur entry "
        "rules re-check karo."
    ),
    "F": (
        "Strategy abhi reliable nahi hai. Risk parameters aur entry rules "
        "re-check karo - re-design ki zaroorat ho sakti hai."
    ),
}


_NEXT_STEPS: dict[OverallGrade, tuple[str, ...]] = {
    "A": (
        "Strategy strong hai. Paper trading shuru karo - 7 sessions complete karo.",
    ),
    "B": (
        "Strategy theek hai. Doctor module se improvements dekho.",
    ),
    "C": (
        "Pehle weak metrics fix karo. Phir paper trading.",
    ),
    "D": (
        "Pehle weak metrics fix karo. Phir paper trading.",
    ),
    "F": (
        "Strategy abhi reliable nahi. Risk parameters re-check karo.",
    ),
}


# ─── Public API ────────────────────────────────────────────────────────


def generate_health_card(
    backtest: BacktestResult,
    reliability: ReliabilityReport | None = None,
) -> StrategyHealthCard:
    """Build a :class:`StrategyHealthCard` from a backtest result.

    The optional ``reliability`` argument enriches the learning tips
    when present (low trust score → coach surfaces a reliability note);
    every gate computation works without it.
    """
    metrics = [
        _build_win_rate(backtest),
        _build_profit_factor(backtest),
        _build_max_drawdown(backtest),
        _build_risk_reward(backtest),
        _build_total_trades(backtest),
        _build_expectancy(backtest),
        _build_recovery_factor(backtest),
    ]

    overall_score = _overall_score(metrics)
    overall_grade = _grade_for(overall_score)

    learning_tips = _learning_tips(metrics, reliability=reliability)

    return StrategyHealthCard(
        overall_grade=overall_grade,
        overall_summary_hinglish=_OVERALL_SUMMARY[overall_grade],
        metric_grades=tuple(metrics),
        learning_tips=tuple(learning_tips),
        next_steps_hinglish=_NEXT_STEPS[overall_grade],
    )


# ─── Per-metric builders ───────────────────────────────────────────────


def _build_win_rate(backtest: BacktestResult) -> MetricGrade:
    pct = backtest.win_rate * 100.0
    grade = classify_win_rate(pct)
    return _row(
        rubric=WIN_RATE_RUBRIC,
        value=pct,
        grade=grade,
        tip=win_rate_tip(grade, pct),
    )


def _build_profit_factor(backtest: BacktestResult) -> MetricGrade:
    pf = backtest.profit_factor
    grade = classify_profit_factor(pf)
    # For the model's ``your_value`` we clamp ``inf`` to a large display
    # number so the field stays a finite float in JSON; the tip text
    # still honours the inf case.
    display_value = pf if math.isfinite(pf) else 1e9
    return _row(
        rubric=PROFIT_FACTOR_RUBRIC,
        value=display_value,
        grade=grade,
        tip=profit_factor_tip(grade, pf),
    )


def _build_max_drawdown(backtest: BacktestResult) -> MetricGrade:
    pct = backtest.max_drawdown * 100.0
    grade = classify_max_drawdown(pct)
    return _row(
        rubric=MAX_DRAWDOWN_RUBRIC,
        value=pct,
        grade=grade,
        tip=max_drawdown_tip(grade, pct),
    )


def _build_risk_reward(backtest: BacktestResult) -> MetricGrade:
    rr = _risk_reward_value(backtest)
    grade = classify_risk_reward(rr)
    display_value = rr if math.isfinite(rr) else 1e9
    return _row(
        rubric=RISK_REWARD_RUBRIC,
        value=display_value,
        grade=grade,
        tip=risk_reward_tip(grade, rr),
    )


def _build_total_trades(backtest: BacktestResult) -> MetricGrade:
    count = backtest.total_trades
    grade = classify_total_trades(count)
    return _row(
        rubric=TOTAL_TRADES_RUBRIC,
        value=float(count),
        grade=grade,
        tip=total_trades_tip(grade, count),
    )


def _build_expectancy(backtest: BacktestResult) -> MetricGrade:
    expectancy_pct = _expectancy_percent(backtest)
    grade = classify_expectancy(expectancy_pct)
    return _row(
        rubric=EXPECTANCY_RUBRIC,
        value=expectancy_pct,
        grade=grade,
        tip=expectancy_tip(grade, expectancy_pct),
    )


def _build_recovery_factor(backtest: BacktestResult) -> MetricGrade:
    rf = _recovery_factor_value(backtest)
    grade = classify_recovery_factor(rf)
    display_value = rf if math.isfinite(rf) else 1e9
    return _row(
        rubric=RECOVERY_FACTOR_RUBRIC,
        value=display_value,
        grade=grade,
        tip=recovery_factor_tip(grade, rf),
    )


# ─── Derived metrics ───────────────────────────────────────────────────


def _risk_reward_value(backtest: BacktestResult) -> float:
    """``avg_win / avg_loss`` (Phase 3 stores avg_loss as magnitude).

    Returns ``0.0`` when both averages are zero (no trades) so the
    metric still classifies (CONCERNING) without raising.
    """
    if backtest.average_loss == 0:
        return float("inf") if backtest.average_win > 0 else 0.0
    return backtest.average_win / backtest.average_loss


def _expectancy_percent(backtest: BacktestResult) -> float:
    """Average percent return per trade — uses Phase 3's
    ``total_return_percent`` to stay independent of initial capital."""
    if backtest.total_trades == 0:
        return 0.0
    return backtest.total_return_percent / backtest.total_trades


def _recovery_factor_value(backtest: BacktestResult) -> float:
    """``total_return_percent / max_drawdown_percent``. ``inf`` when the
    drawdown is exactly zero AND the strategy is profitable; ``0.0``
    when both are zero (flat strategy)."""
    dd_pct = backtest.max_drawdown * 100.0
    if dd_pct == 0.0:
        if backtest.total_return_percent > 0:
            return float("inf")
        return 0.0
    return backtest.total_return_percent / dd_pct


# ─── Overall score + grade ────────────────────────────────────────────


def _overall_score(metrics: list[MetricGrade]) -> float:
    if not metrics:
        return 0.0
    weights = [GRADE_WEIGHTS[m.your_grade] for m in metrics]
    average = sum(weights) / len(weights)
    return average * 25.0


def _grade_for(score: float) -> OverallGrade:
    if score >= 85.0:
        return "A"
    if score >= 70.0:
        return "B"
    if score >= 55.0:
        return "C"
    if score >= 40.0:
        return "D"
    return "F"


# ─── Learning tips ─────────────────────────────────────────────────────


def _learning_tips(
    metrics: list[MetricGrade],
    *,
    reliability: ReliabilityReport | None,
) -> list[str]:
    tips: list[str] = []

    concerning = [m for m in metrics if m.your_grade == "CONCERNING"]
    if concerning:
        names = ", ".join(m.metric_name for m in concerning)
        tips.append(
            f"Focus areas: {names}. In metrics ko fix karne se overall grade "
            "improve hoga."
        )

    if reliability is not None:
        trust = reliability.trust_score.score
        if trust < 70:
            tips.append(
                f"Reliability trust score {trust}/100 hai - paper trading se "
                "pehle Strategy Doctor se diagnose karwao."
            )
        else:
            tips.append(
                f"Reliability trust score {trust}/100 strong hai. Backtest "
                "ke result par bharosa kar sakte ho."
            )

    if not tips:
        tips.append(
            "Strategy ke har metric ko time-time pe re-check karo. Markets "
            "change hote hain - rules update karte raho."
        )

    return tips


# ─── Helpers ───────────────────────────────────────────────────────────


def _row(
    *,
    rubric: MetricRubric,
    value: float,
    grade: MetricGradeLevel,
    tip: str,
) -> MetricGrade:
    return MetricGrade(
        metric_name=rubric.name,
        your_value=value,
        unit=rubric.unit,
        ideal_excellent=rubric.ideal_excellent,
        ideal_good=rubric.ideal_good,
        ideal_acceptable=rubric.ideal_acceptable,
        ideal_concerning=rubric.ideal_concerning,
        your_grade=grade,
        hinglish_tip=tip,
    )


__all__ = ["generate_health_card"]
