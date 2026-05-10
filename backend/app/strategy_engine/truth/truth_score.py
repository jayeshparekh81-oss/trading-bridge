"""Truth-score evaluator — fake-backtest detection on top of reliability.

The engine consumes a pre-computed
:class:`~app.strategy_engine.reliability.ReliabilityReport` and the
operator's cost / ambiguity choices, then walks twelve inspections
(grouped into four warning buckets) to decide whether the headline
backtest deserves the operator's confidence.

Inspections (deductions accumulate; final score floors at 0, caps at 100):

    Bucket: fake-backtest
        1. High win-rate trap        (win_rate > 0.85 AND pf weak / R:R bad)
        2. Low trade count           (< 30)
        3. Poor risk-reward          (avg_win / avg_loss < 1.0)
        4. Avg-loss dominates win    (avg_loss > 1.5 x avg_win)
        5. High max drawdown         (> 30 %)
        6. Weak profit factor        (< 1.3)

    Bucket: overfitting
        7. Out-of-sample degradation (degradation_percent > 25 %)
        8. Fragile parameters        (sensitivity.fragile = True)
        11. Overfitting stack        (7 AND 8 both fire — extra penalty)

    Bucket: execution
        10. Same-bar ambiguity bias  (ambiguity_mode = OPTIMISTIC)
        12. Unrealistic frictionless (zero costs AND zero slippage)

    Bucket: cost
        9. Cost impact               (caller pre_cost_pnl shows >20 %
                                      shortfall, OR cost configured AND
                                      profit factor in marginal band)

Output:

    :class:`TruthReport` — frozen, JSON-friendly. Field aliases match
    the master prompt's exact camelCase wire format
    (``truthScore``, ``fakeBacktestWarnings``, …).

The engine **does not mutate** any input. Frozen Pydantic models make
this enforceable, and ``test_evaluate_does_not_mutate_inputs`` pins
the round-trip equality.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.backtest.runner import AmbiguityMode
from app.strategy_engine.truth.constants import (
    AVG_LOSS_RATIO_THRESHOLD,
    BAD_RISK_REWARD_RATIO,
    COST_IMPACT_FRACTION_THRESHOLD,
    DEDUCT_AMBIGUITY_OPTIMISTIC,
    DEDUCT_AVG_LOSS_DOMINATES,
    DEDUCT_COST_IMPACT,
    DEDUCT_FRAGILE_PARAMETERS,
    DEDUCT_HIGH_DRAWDOWN,
    DEDUCT_HIGH_WIN_RATE_RISK,
    DEDUCT_LOW_TRADE_COUNT,
    DEDUCT_OOS_DEGRADATION,
    DEDUCT_OVERFITTING_STACK,
    DEDUCT_POOR_RISK_REWARD,
    DEDUCT_UNREALISTIC_FRICTIONLESS,
    DEDUCT_WEAK_PROFIT_FACTOR,
    HIGH_DRAWDOWN_THRESHOLD,
    HIGH_WIN_RATE_WARNING_THRESHOLD,
    LOW_TRADE_COUNT_THRESHOLD,
    MARGINAL_PROFIT_FACTOR,
    OOS_DEGRADATION_WARNING_THRESHOLD,
    RISK_LEVEL_THRESHOLDS,
    SUSPICIOUS_WIN_RATE_PROFIT_FACTOR,
    TRUST_SCORE_GRADES,
    TRUTH_VERDICTS,
    Grade,
    RiskLevelLiteral,
)

if TYPE_CHECKING:
    from app.strategy_engine.backtest.costs import CostSettings
    from app.strategy_engine.reliability.reliability_report import (
        ReliabilityReport,
    )
    from app.strategy_engine.schema.strategy import StrategyJSON


RiskLevel = RiskLevelLiteral


# ─── Output boundary ───────────────────────────────────────────────────


class TruthReport(BaseModel):
    """Truth-score verdict — JSON-serialised with the master-prompt aliases."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    truth_score: int = Field(..., ge=0, le=100, alias="truthScore")
    grade: Grade
    verdict: str = Field(..., min_length=1, max_length=128)
    risk_level: RiskLevel = Field(..., alias="riskLevel")
    fake_backtest_warnings: tuple[str, ...] = Field(
        default_factory=tuple, alias="fakeBacktestWarnings"
    )
    overfitting_warnings: tuple[str, ...] = Field(
        default_factory=tuple, alias="overfittingWarnings"
    )
    execution_warnings: tuple[str, ...] = Field(
        default_factory=tuple, alias="executionWarnings"
    )
    cost_warnings: tuple[str, ...] = Field(default_factory=tuple, alias="costWarnings")
    strengths: tuple[str, ...] = Field(default_factory=tuple)
    weaknesses: tuple[str, ...] = Field(default_factory=tuple)
    recommended_next_actions: tuple[str, ...] = Field(
        default_factory=tuple, alias="recommendedNextActions"
    )


# ─── Public API ────────────────────────────────────────────────────────


def evaluate_strategy_truth(
    *,
    strategy: StrategyJSON,
    reliability: ReliabilityReport,
    cost_settings: CostSettings,
    ambiguity_mode: AmbiguityMode = AmbiguityMode.CONSERVATIVE,
    pre_cost_pnl: float | None = None,
) -> TruthReport:
    """Score the truthfulness of ``reliability``'s headline backtest.

    Args:
        strategy: User-built DSL — informs operator-readable warning
            phrasing (e.g. "fewer indicators") but is not otherwise
            mutated or persisted.
        reliability: Pre-computed Phase 4
            :class:`~app.strategy_engine.reliability.ReliabilityReport`
            (the backtest, the trust score, optional OOS / sensitivity).
        cost_settings: Cost model used for the backtest. Drives the
            "frictionless" execution warning when zero, and the cost-
            impact heuristic when non-zero.
        ambiguity_mode: Same-bar resolution mode used in the backtest.
            ``OPTIMISTIC`` triggers the execution warning.
        pre_cost_pnl: Gross (pre-cost) P&L if the caller has it. When
            supplied AND positive, the cost warning fires whenever post-
            cost P&L is more than 20 % below pre-cost.

    Returns:
        :class:`TruthReport` with the deterministic truth score and
        bucketed warnings. Inputs are not mutated.
    """
    # Phase 1 strategy is consumed for completeness of the public
    # contract — current heuristics derive from backtest + reliability,
    # but Phase 9 may consult ``strategy.execution`` or indicator count
    # for further checks. Reference it explicitly so static-analysis
    # tooling does not flag the parameter as unused.
    _ = strategy

    backtest = reliability.backtest

    score = 100
    fake_warnings: list[str] = []
    over_warnings: list[str] = []
    exec_warnings: list[str] = []
    cost_warnings: list[str] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    actions: list[str] = []

    # ─── 1. High win-rate trap ─────────────────────────────────────
    high_winrate_flag = backtest.win_rate > HIGH_WIN_RATE_WARNING_THRESHOLD and (
        not _pf_at_least(backtest.profit_factor, SUSPICIOUS_WIN_RATE_PROFIT_FACTOR)
        or _avg_loss_bigger_than_win(backtest.average_win, backtest.average_loss)
    )
    if high_winrate_flag:
        score -= DEDUCT_HIGH_WIN_RATE_RISK
        fake_warnings.append(
            f"Win rate is high ({backtest.win_rate * 100:.1f} %), but average loss "
            "is much larger than average win or profit factor is weak. This "
            "strategy may look good but can fail badly in live conditions."
        )
        weaknesses.append("High win-rate trap")
        actions.append(
            "Compare averageWin to averageLoss; a high win rate with a low "
            "profit factor often signals small wins and rare large losses."
        )

    # ─── 2. Low trade count ────────────────────────────────────────
    if backtest.total_trades < LOW_TRADE_COUNT_THRESHOLD:
        score -= DEDUCT_LOW_TRADE_COUNT
        fake_warnings.append(
            f"Only {backtest.total_trades} trade(s) in the backtest; statistics "
            f"are noisy below {LOW_TRADE_COUNT_THRESHOLD} trades."
        )
        weaknesses.append("Low trade count")
        actions.append(
            "Backtest a longer period or relax the entry rules to gather at "
            f"least {LOW_TRADE_COUNT_THRESHOLD} trades."
        )

    # ─── 3. Poor risk/reward ───────────────────────────────────────
    rr = _risk_reward(backtest.average_win, backtest.average_loss)
    if rr is not None and rr < BAD_RISK_REWARD_RATIO:
        score -= DEDUCT_POOR_RISK_REWARD
        fake_warnings.append(
            f"Risk-reward ratio {rr:.2f} is below 1.0; the strategy needs a high "
            "win rate just to break even."
        )
        weaknesses.append("Poor risk-reward")

    # ─── 4. Average loss bigger than average win (asymmetry trap) ──
    if _avg_loss_bigger_than_win(backtest.average_win, backtest.average_loss):
        score -= DEDUCT_AVG_LOSS_DOMINATES
        fake_warnings.append(
            f"Average loss ({backtest.average_loss:.2f}) is more than "
            f"{AVG_LOSS_RATIO_THRESHOLD:.1f}x average win ({backtest.average_win:.2f}); "
            "rare large losers can wipe out many small winners."
        )
        weaknesses.append("Average loss dominates average win")

    # ─── 5. High max drawdown ──────────────────────────────────────
    if backtest.max_drawdown > HIGH_DRAWDOWN_THRESHOLD:
        score -= DEDUCT_HIGH_DRAWDOWN
        fake_warnings.append(
            f"Max drawdown {backtest.max_drawdown * 100:.1f} % is high; few "
            "traders can sit through a peak-to-trough decline this large."
        )
        weaknesses.append("High max drawdown")
        actions.append(
            "Reduce position size or tighten the stop loss to cap drawdown."
        )

    # ─── 6. Weak profit factor ─────────────────────────────────────
    if not _pf_at_least(backtest.profit_factor, MARGINAL_PROFIT_FACTOR):
        score -= DEDUCT_WEAK_PROFIT_FACTOR
        fake_warnings.append(
            f"Profit factor {_format_pf(backtest.profit_factor)} is weak; small "
            "slippage / cost changes could flip the strategy negative."
        )
        weaknesses.append("Weak profit factor")

    # ─── 7. Out-of-sample degradation ──────────────────────────────
    oos_flag = False
    if reliability.out_of_sample is not None:
        deg = reliability.out_of_sample.degradation_percent
        if deg > OOS_DEGRADATION_WARNING_THRESHOLD:
            oos_flag = True
            score -= DEDUCT_OOS_DEGRADATION
            over_warnings.append(
                f"Training result is strong, but out-of-sample result dropped "
                f"{deg * 100:.1f} %. Overfitting risk is high."
            )
            weaknesses.append("Out-of-sample degradation")
            actions.append(
                "Simplify the strategy (fewer indicators) or extend the "
                "training window before deploying."
            )

    # ─── 8. Fragile parameters ─────────────────────────────────────
    fragile_flag = False
    if reliability.sensitivity is not None and reliability.sensitivity.fragile:
        fragile_flag = True
        score -= DEDUCT_FRAGILE_PARAMETERS
        over_warnings.append(
            "Small ±20 % parameter perturbations cause large score swings — "
            "the strategy is fragile / over-fit to specific values."
        )
        weaknesses.append("Fragile parameters")
        actions.append(
            "Pick parameter values that perform well across a range, not the "
            "single best in-sample tuning."
        )

    # ─── 11. Overfitting stack ─────────────────────────────────────
    if oos_flag and fragile_flag:
        score -= DEDUCT_OVERFITTING_STACK
        over_warnings.append(
            "Out-of-sample degradation and parameter fragility both fired — "
            "the combined evidence of over-fitting is stronger than either "
            "signal alone."
        )

    # ─── 10. Same-bar ambiguity bias ───────────────────────────────
    if ambiguity_mode is AmbiguityMode.OPTIMISTIC:
        score -= DEDUCT_AMBIGUITY_OPTIMISTIC
        exec_warnings.append(
            "Backtest used the optimistic same-bar resolution; live fills will "
            "rarely match this best-case ordering."
        )
        weaknesses.append("Optimistic same-bar resolution")
        actions.append(
            "Re-run the backtest with ambiguityMode='conservative' before "
            "trusting the equity curve."
        )

    # ─── 12. Unrealistic frictionless execution ────────────────────
    frictionless = (
        cost_settings.fixed_cost == 0
        and cost_settings.percent_cost == 0
        and cost_settings.slippage_percent == 0
    )
    if frictionless:
        score -= DEDUCT_UNREALISTIC_FRICTIONLESS
        exec_warnings.append(
            "Cost settings are zero — the backtest assumes free trading. Real "
            "fills include broker fees and slippage."
        )
        weaknesses.append("Frictionless execution assumption")
        actions.append(
            "Configure broker fees, percent cost, and slippage before trusting "
            "the equity curve."
        )

    # ─── 9. Cost impact ────────────────────────────────────────────
    cost_flag = False
    if pre_cost_pnl is not None and pre_cost_pnl > 0:
        impact = (pre_cost_pnl - backtest.total_pnl) / pre_cost_pnl
        if impact > COST_IMPACT_FRACTION_THRESHOLD:
            cost_flag = True
            cost_warnings.append(
                f"Cost-adjusted performance is weak: charges and slippage took "
                f"{impact * 100:.1f} % of gross profit ({pre_cost_pnl:.2f} → "
                f"{backtest.total_pnl:.2f})."
            )
    elif (
        not frictionless
        and _pf_at_least(backtest.profit_factor, 1.0)
        and not _pf_at_least(backtest.profit_factor, MARGINAL_PROFIT_FACTOR)
    ):
        cost_flag = True
        cost_warnings.append(
            f"Costs are configured and profit factor is marginal "
            f"({_format_pf(backtest.profit_factor)}); fees and slippage may "
            "remove most profits in live trading."
        )
    if cost_flag:
        score -= DEDUCT_COST_IMPACT
        weaknesses.append("Cost-impact risk")
        actions.append(
            "Trade less frequently, use a lower-cost broker, or widen targets "
            "to absorb round-trip costs."
        )

    # ─── Strengths ─────────────────────────────────────────────────
    if backtest.total_trades >= LOW_TRADE_COUNT_THRESHOLD:
        strengths.append("Sufficient trade count for statistical confidence")
    if _pf_at_least(backtest.profit_factor, SUSPICIOUS_WIN_RATE_PROFIT_FACTOR):
        strengths.append("Strong profit factor")
    if backtest.max_drawdown <= HIGH_DRAWDOWN_THRESHOLD / 2:
        strengths.append("Drawdown is contained")
    if reliability.out_of_sample is not None and not oos_flag:
        strengths.append("Out-of-sample performance held up")
    if reliability.sensitivity is not None and not fragile_flag:
        strengths.append("Robust to ±20 % parameter perturbations")
    if (
        not frictionless
        and ambiguity_mode is AmbiguityMode.CONSERVATIVE
    ):
        strengths.append("Realistic costs + conservative same-bar resolution")

    # ─── Final clamp + grade + verdict + risk level ────────────────
    final_score = max(0, min(100, score))
    grade = _grade_for(final_score)
    verdict = TRUTH_VERDICTS[grade]
    risk = _risk_level(
        warning_count=len(fake_warnings)
        + len(over_warnings)
        + len(exec_warnings)
        + len(cost_warnings)
    )

    return TruthReport(
        truth_score=final_score,
        grade=grade,
        verdict=verdict,
        risk_level=risk,
        fake_backtest_warnings=tuple(fake_warnings),
        overfitting_warnings=tuple(over_warnings),
        execution_warnings=tuple(exec_warnings),
        cost_warnings=tuple(cost_warnings),
        strengths=tuple(strengths),
        weaknesses=tuple(weaknesses),
        recommended_next_actions=tuple(actions),
    )


# ─── Internal helpers ──────────────────────────────────────────────────


def _grade_for(score: int) -> Grade:
    """Map 0-100 → A-F per :data:`TRUST_SCORE_GRADES`."""
    clamped = max(0, min(100, score))
    for grade, (low, high) in TRUST_SCORE_GRADES.items():
        if low <= clamped <= high:
            return grade
    raise ValueError(  # pragma: no cover — TRUST_SCORE_GRADES covers 0-100
        f"No grade range covers score={score}."
    )


def _risk_level(*, warning_count: int) -> Literal["low", "medium", "high", "extreme"]:
    """Map total warning count to a four-band risk level."""
    low_max, medium_max, high_max = RISK_LEVEL_THRESHOLDS
    if warning_count <= low_max:
        return "low"
    if warning_count <= medium_max:
        return "medium"
    if warning_count <= high_max:
        return "high"
    return "extreme"


def _pf_at_least(pf: float, threshold: float) -> bool:
    """``math.inf`` (no losses) trivially exceeds any finite threshold."""
    if math.isinf(pf):
        return True
    return pf >= threshold


def _format_pf(pf: float) -> str:
    """Display 'inf' rather than '0.00' for the wins-only edge case."""
    return "inf" if math.isinf(pf) else f"{pf:.2f}"


def _risk_reward(avg_win: float, avg_loss: float) -> float | None:
    """``avg_win / avg_loss`` when both are non-zero; ``None`` otherwise."""
    if avg_loss == 0 or avg_win == 0:
        return None
    return avg_win / avg_loss


def _avg_loss_bigger_than_win(avg_win: float, avg_loss: float) -> bool:
    """``avg_loss > AVG_LOSS_RATIO_THRESHOLD x avg_win`` — the asymmetry trap."""
    if avg_win <= 0 or avg_loss <= 0:
        return False
    return avg_loss > AVG_LOSS_RATIO_THRESHOLD * avg_win


__all__ = [
    "RiskLevel",
    "TruthReport",
    "evaluate_strategy_truth",
]
