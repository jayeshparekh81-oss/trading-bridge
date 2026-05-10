"""Locked benchmark thresholds + classifiers for the 7 coach metrics.

Each metric exposes:

    * ``classify(value) -> MetricGradeLevel`` — pure function
    * ``RUBRIC[name]`` — :class:`MetricRubric` with the four ideal-range
      strings shown to the user.

The thresholds match the master prompt verbatim. Changing a value here
changes the coach's grade boundaries — call out the rationale in the
commit message.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.strategy_engine.coach.models import MetricGradeLevel


@dataclass(frozen=True)
class MetricRubric:
    """The four ideal-range strings shown to the user for a metric."""

    name: str
    unit: str
    ideal_excellent: str
    ideal_good: str
    ideal_acceptable: str
    ideal_concerning: str


# ─── Win Rate ──────────────────────────────────────────────────────────


def classify_win_rate(win_rate_pct: float) -> MetricGradeLevel:
    """50-65% excellent; 45-50 / 65-75 good; 40-45 / 75-85 acceptable;
    everything else concerning (too low or suspiciously high)."""
    pct = win_rate_pct
    if 50.0 <= pct <= 65.0:
        return "EXCELLENT"
    if (45.0 <= pct < 50.0) or (65.0 < pct <= 75.0):
        return "GOOD"
    if (40.0 <= pct < 45.0) or (75.0 < pct <= 85.0):
        return "ACCEPTABLE"
    return "CONCERNING"


WIN_RATE_RUBRIC = MetricRubric(
    name="Win Rate",
    unit="%",
    ideal_excellent="50-65%",
    ideal_good="45-50% or 65-75%",
    ideal_acceptable="40-45% or 75-85%",
    ideal_concerning="<40% or >85%",
)


# ─── Profit Factor ─────────────────────────────────────────────────────


def classify_profit_factor(pf: float) -> MetricGradeLevel:
    """``inf`` (no losses) trivially excellent. >2.0 excellent; 1.5-2.0
    good; 1.2-1.5 acceptable; <1.2 concerning."""
    if math.isinf(pf):
        return "EXCELLENT"
    if pf > 2.0:
        return "EXCELLENT"
    if pf >= 1.5:
        return "GOOD"
    if pf >= 1.2:
        return "ACCEPTABLE"
    return "CONCERNING"


PROFIT_FACTOR_RUBRIC = MetricRubric(
    name="Profit Factor",
    unit="x",
    ideal_excellent=">2.0x",
    ideal_good="1.5-2.0x",
    ideal_acceptable="1.2-1.5x",
    ideal_concerning="<1.2x",
)


# ─── Max Drawdown ──────────────────────────────────────────────────────


def classify_max_drawdown(dd_pct: float) -> MetricGradeLevel:
    """<10% excellent; 10-15 good; 15-25 acceptable; >25 concerning."""
    if dd_pct < 10.0:
        return "EXCELLENT"
    if dd_pct <= 15.0:
        return "GOOD"
    if dd_pct <= 25.0:
        return "ACCEPTABLE"
    return "CONCERNING"


MAX_DRAWDOWN_RUBRIC = MetricRubric(
    name="Max Drawdown",
    unit="%",
    ideal_excellent="<10%",
    ideal_good="10-15%",
    ideal_acceptable="15-25%",
    ideal_concerning=">25%",
)


# ─── Risk-Reward (avg_win / avg_loss) ──────────────────────────────────


def classify_risk_reward(rr: float) -> MetricGradeLevel:
    """>2.0 excellent; 1.5-2.0 good; 1.0-1.5 acceptable; <1.0 concerning."""
    if math.isinf(rr) or rr > 2.0:
        return "EXCELLENT"
    if rr >= 1.5:
        return "GOOD"
    if rr >= 1.0:
        return "ACCEPTABLE"
    return "CONCERNING"


RISK_REWARD_RUBRIC = MetricRubric(
    name="Risk-Reward",
    unit="x",
    ideal_excellent=">2.0x",
    ideal_good="1.5-2.0x",
    ideal_acceptable="1.0-1.5x",
    ideal_concerning="<1.0x",
)


# ─── Total Trades ──────────────────────────────────────────────────────


def classify_total_trades(count: int) -> MetricGradeLevel:
    """>100 excellent; 50-100 good; 30-50 acceptable; <30 concerning."""
    if count > 100:
        return "EXCELLENT"
    if count >= 50:
        return "GOOD"
    if count >= 30:
        return "ACCEPTABLE"
    return "CONCERNING"


TOTAL_TRADES_RUBRIC = MetricRubric(
    name="Total Trades",
    unit="trades",
    ideal_excellent=">100 trades",
    ideal_good="50-100 trades",
    ideal_acceptable="30-50 trades",
    ideal_concerning="<30 trades",
)


# ─── Expectancy (% of capital per trade) ──────────────────────────────


def classify_expectancy(expectancy_pct_per_trade: float) -> MetricGradeLevel:
    """>0.5% positive excellent; 0-0.5 good; near zero acceptable;
    negative concerning. ``Near zero`` = (-0.05, 0)."""
    val = expectancy_pct_per_trade
    if val > 0.5:
        return "EXCELLENT"
    if val > 0.0:
        return "GOOD"
    if val >= -0.05:
        return "ACCEPTABLE"
    return "CONCERNING"


EXPECTANCY_RUBRIC = MetricRubric(
    name="Expectancy",
    unit="%",
    ideal_excellent=">0.5% per trade",
    ideal_good="0-0.5% per trade",
    ideal_acceptable="near zero",
    ideal_concerning="negative",
)


# ─── Recovery Factor (return / drawdown) ──────────────────────────────


def classify_recovery_factor(rf: float) -> MetricGradeLevel:
    """>5 excellent; 3-5 good; 1-3 acceptable; <1 (or non-positive)
    concerning. ``inf`` (positive return + zero drawdown) is excellent."""
    if math.isinf(rf):
        return "EXCELLENT"
    if rf > 5.0:
        return "EXCELLENT"
    if rf >= 3.0:
        return "GOOD"
    if rf >= 1.0:
        return "ACCEPTABLE"
    return "CONCERNING"


RECOVERY_FACTOR_RUBRIC = MetricRubric(
    name="Recovery Factor",
    unit="x",
    ideal_excellent=">5x",
    ideal_good="3-5x",
    ideal_acceptable="1-3x",
    ideal_concerning="<1x",
)


# ─── Per-grade score weights for the overall A-F roll-up ─────────────


GRADE_WEIGHTS: dict[MetricGradeLevel, int] = {
    "EXCELLENT": 4,
    "GOOD": 3,
    "ACCEPTABLE": 2,
    "CONCERNING": 0,
}


__all__ = [
    "EXPECTANCY_RUBRIC",
    "GRADE_WEIGHTS",
    "MAX_DRAWDOWN_RUBRIC",
    "PROFIT_FACTOR_RUBRIC",
    "RECOVERY_FACTOR_RUBRIC",
    "RISK_REWARD_RUBRIC",
    "TOTAL_TRADES_RUBRIC",
    "WIN_RATE_RUBRIC",
    "MetricRubric",
    "classify_expectancy",
    "classify_max_drawdown",
    "classify_profit_factor",
    "classify_recovery_factor",
    "classify_risk_reward",
    "classify_total_trades",
    "classify_win_rate",
]
