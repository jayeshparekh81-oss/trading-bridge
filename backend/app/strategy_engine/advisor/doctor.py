"""AI Strategy Doctor — structured strategy diagnosis (deterministic).

Inspects the strategy + its backtest / reliability / truth artefacts
and returns a typed :class:`Diagnosis` partitioned into:

    * ``problems``           — typed, severity-tagged findings.
    * ``recommendedFixes``   — short imperative actions.
    * ``canAutoImprove``     — true iff the doctor has produced a
                                concrete ``improvedStrategyDraft``
                                that the caller can apply with one
                                click after review.
    * ``improvedStrategyDraft`` — a *new* strategy dict (the original
                                  is never mutated). The draft is
                                  emitted as ``model_dump(by_alias=True,
                                  mode="json")`` so it can be stored
                                  through the Phase 5 CRUD endpoint
                                  without re-shaping.

The doctor never promises profit, never fabricates backtest results,
and never auto-applies a change. The Apply Fix & Compare workflow
described in the master prompt is the **caller's** responsibility:
this module produces the draft, the caller re-runs the backtest and
shows the comparison.
"""

from __future__ import annotations

import copy
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.advisor.advisor import AdviceSeverity
from app.strategy_engine.advisor.constants import (
    HIGH_DRAWDOWN_ADVISORY_THRESHOLD,
    INDICATOR_OVERLOAD_THRESHOLD,
    POOR_TRUTH_SCORE_THRESHOLD,
)

if TYPE_CHECKING:
    from app.strategy_engine.backtest.runner import BacktestResult
    from app.strategy_engine.reliability.reliability_report import (
        ReliabilityReport,
    )
    from app.strategy_engine.schema.strategy import StrategyJSON
    from app.strategy_engine.truth.truth_score import TruthReport


class ProblemType(StrEnum):
    """Doctor problem taxonomy — matches the master-prompt schema."""

    ENTRY = "entry"
    EXIT = "exit"
    RISK = "risk"
    OVERFIT = "overfit"
    COST = "cost"
    REGIME = "regime"
    COMPLEXITY = "complexity"


class Problem(BaseModel):
    """One typed problem the doctor detected."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    type: ProblemType
    severity: AdviceSeverity
    message: str = Field(..., min_length=1, max_length=512)
    suggested_fix: str = Field(..., min_length=1, max_length=512, alias="suggestedFix")
    auto_fix_available: bool = Field(default=False, alias="autoFixAvailable")


class Diagnosis(BaseModel):
    """Top-level doctor output — JSON-serialised with master-prompt aliases."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    diagnosis_summary: str = Field(
        default="", max_length=1024, alias="diagnosisSummary"
    )
    problems: tuple[Problem, ...] = Field(default_factory=tuple)
    recommended_fixes: tuple[str, ...] = Field(
        default_factory=tuple, alias="recommendedFixes"
    )
    can_auto_improve: bool = Field(default=False, alias="canAutoImprove")
    improved_strategy_draft: dict[str, Any] | None = Field(
        default=None, alias="improvedStrategyDraft"
    )


def diagnose_strategy(
    *,
    strategy: StrategyJSON,
    backtest: BacktestResult | None = None,
    reliability: ReliabilityReport | None = None,
    truth: TruthReport | None = None,
) -> Diagnosis:
    """Return a structured :class:`Diagnosis`. The input is never mutated."""
    problems: list[Problem] = []

    problems.extend(_exit_problems(strategy))
    problems.extend(_complexity_problems(strategy))

    if backtest is not None:
        problems.extend(_backtest_problems(backtest))
    if truth is not None:
        problems.extend(_truth_problems(truth))
    if reliability is not None:
        problems.extend(_reliability_problems(reliability))

    draft, fixed_problem = _build_improved_draft(strategy, problems)

    can_auto_improve = draft is not None
    recommended_fixes = tuple(p.suggested_fix for p in problems)
    summary = _summarise(problems, fixed_problem=fixed_problem)

    return Diagnosis(
        diagnosis_summary=summary,
        problems=tuple(problems),
        recommended_fixes=recommended_fixes,
        can_auto_improve=can_auto_improve,
        improved_strategy_draft=draft,
    )


# ─── Problem detectors ─────────────────────────────────────────────────


def _exit_problems(strategy: StrategyJSON) -> list[Problem]:
    out: list[Problem] = []
    has_stop_loss = (
        strategy.exit.stop_loss_percent is not None
        or strategy.exit.trailing_stop_percent is not None
    )
    if not has_stop_loss:
        out.append(
            Problem(
                type=ProblemType.RISK,
                severity=AdviceSeverity.CRITICAL,
                message="Stop loss is missing — drawdowns are unbounded.",
                suggested_fix=(
                    "Add stopLossPercent (or trailingStopPercent) to the "
                    "exit block."
                ),
                auto_fix_available=strategy.exit.target_percent is not None,
            )
        )
    if strategy.exit.target_percent is not None and (
        strategy.exit.stop_loss_percent is not None
        and strategy.exit.target_percent < strategy.exit.stop_loss_percent
    ):
        out.append(
            Problem(
                type=ProblemType.EXIT,
                severity=AdviceSeverity.WARNING,
                message=(
                    "Target is smaller than stop loss — the strategy needs "
                    "a high win rate just to break even."
                ),
                suggested_fix=(
                    "Widen targetPercent so the reward exceeds the risk."
                ),
                auto_fix_available=False,
            )
        )
    return out


def _complexity_problems(strategy: StrategyJSON) -> list[Problem]:
    out: list[Problem] = []
    if len(strategy.indicators) > INDICATOR_OVERLOAD_THRESHOLD:
        out.append(
            Problem(
                type=ProblemType.COMPLEXITY,
                severity=AdviceSeverity.WARNING,
                message=(
                    f"{len(strategy.indicators)} indicators is above the "
                    f"{INDICATOR_OVERLOAD_THRESHOLD}-indicator overload "
                    "threshold; multiple same-category indicators rarely add "
                    "independent signal."
                ),
                suggested_fix=(
                    "Use one trend indicator, one momentum confirmation, "
                    "and one risk rule."
                ),
                auto_fix_available=False,
            )
        )
    return out


def _backtest_problems(backtest: BacktestResult) -> list[Problem]:
    out: list[Problem] = []
    if backtest.max_drawdown > HIGH_DRAWDOWN_ADVISORY_THRESHOLD:
        out.append(
            Problem(
                type=ProblemType.RISK,
                severity=AdviceSeverity.WARNING,
                message=(
                    f"Max drawdown {backtest.max_drawdown * 100:.1f} % is "
                    "high; few traders can sit through this."
                ),
                suggested_fix=(
                    "Reduce position size or tighten the stop loss to cap "
                    "drawdown."
                ),
                auto_fix_available=False,
            )
        )
    return out


def _truth_problems(truth: TruthReport) -> list[Problem]:
    out: list[Problem] = []
    if truth.overfitting_warnings:
        out.append(
            Problem(
                type=ProblemType.OVERFIT,
                severity=AdviceSeverity.WARNING,
                message=(
                    "Truth report flagged overfitting risk based on out-of-"
                    "sample degradation or parameter fragility."
                ),
                suggested_fix=(
                    "Simplify the strategy (fewer indicators) or extend the "
                    "training window before deploying."
                ),
                auto_fix_available=False,
            )
        )
    if truth.cost_warnings:
        out.append(
            Problem(
                type=ProblemType.COST,
                severity=AdviceSeverity.WARNING,
                message=(
                    "Truth report flagged cost impact — fees and slippage "
                    "may erase the edge in live conditions."
                ),
                suggested_fix=(
                    "Trade less frequently, use a lower-cost broker, or "
                    "widen targets to absorb round-trip costs."
                ),
                auto_fix_available=False,
            )
        )
    if truth.truth_score < POOR_TRUTH_SCORE_THRESHOLD:
        out.append(
            Problem(
                type=ProblemType.RISK,
                severity=AdviceSeverity.CRITICAL,
                message=(
                    f"Truth score {truth.truth_score} is below "
                    f"{POOR_TRUTH_SCORE_THRESHOLD}; the strategy is not ready."
                ),
                suggested_fix=(
                    "Resolve the warnings in the truth report, then re-run "
                    "the reliability and truth checks."
                ),
                auto_fix_available=False,
            )
        )
    return out


def _reliability_problems(reliability: ReliabilityReport) -> list[Problem]:
    out: list[Problem] = []
    sens = reliability.sensitivity
    if sens is not None and sens.fragile:
        out.append(
            Problem(
                type=ProblemType.OVERFIT,
                severity=AdviceSeverity.WARNING,
                message=(
                    "Strategy is fragile to small parameter perturbations."
                ),
                suggested_fix=(
                    "Pick parameter values that perform well across a range, "
                    "not the single best in-sample tuning."
                ),
                auto_fix_available=False,
            )
        )
    return out


# ─── Auto-improvement draft ────────────────────────────────────────────


def _build_improved_draft(
    strategy: StrategyJSON,
    problems: list[Problem],
) -> tuple[dict[str, Any] | None, Problem | None]:
    """Build a fresh strategy dict if exactly one trivially-fixable
    problem is present. Returns ``(draft_or_none, fixed_problem_or_none)``.

    Phase 7 ships the most common auto-fix only — inserting a default
    stop loss when the strategy has a target but no stop. Multi-step
    fixes (regime filters, indicator pruning) are deliberately deferred
    to a later phase to keep "auto-apply without user approval"
    impossible-by-construction.
    """
    fixable = [p for p in problems if p.auto_fix_available]
    if len(fixable) != 1:
        return None, None

    problem = fixable[0]
    if not (
        problem.type is ProblemType.RISK
        and "Stop loss is missing" in problem.message
    ):
        return None, None

    if strategy.exit.target_percent is None:
        return None, None  # nothing to anchor a default stop loss to

    # ``model_dump(by_alias=True, mode="json")`` produces the same wire
    # shape the Phase 5 CRUD endpoint accepts, and ``copy.deepcopy``
    # guards against the (paranoid) case of a future helper that hands
    # back a shared sub-dict.
    draft: dict[str, Any] = copy.deepcopy(
        strategy.model_dump(by_alias=True, mode="json")
    )
    # Default stop loss: half the target — gives ≥2:1 reward:risk so
    # the auto-fix does not introduce a worse-than-break-even setup.
    draft["exit"]["stopLossPercent"] = strategy.exit.target_percent / 2

    return draft, problem


# ─── Summary line ──────────────────────────────────────────────────────


def _summarise(problems: list[Problem], *, fixed_problem: Problem | None) -> str:
    if not problems:
        return "No problems detected. Strategy looks well-formed."
    critical = [p for p in problems if p.severity is AdviceSeverity.CRITICAL]
    summary = (
        f"{len(problems)} problem(s) detected"
        f"{f'; {len(critical)} critical' if critical else ''}."
    )
    if fixed_problem is not None:
        summary += " A one-click auto-fix is available for review."
    return summary


__all__ = [
    "Diagnosis",
    "Problem",
    "ProblemType",
    "diagnose_strategy",
]
