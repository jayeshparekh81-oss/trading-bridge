"""Trust-score engine — deterministic strategy reliability scoring.

The score starts at 100 and each check below subtracts a fixed
deduction when its condition is met. The final score is floored at 0,
capped at 100, and mapped to an A-F grade via
:data:`constants.TRUST_SCORE_GRADES`.

Every threshold and deduction lives in :mod:`constants`. **Do not
duplicate values here.**

The engine is **AI-free**: no LLM call, no random draws, no clock reads.
The function is pure — same ``BacktestResult`` (and same optional inputs)
always produces the same :class:`TrustScore`. The
``test_trust_score_determinism.py`` test enforces this.

Scoring rules (each fires independently; deductions accumulate):

    Trade count        < LOW_TRADE_COUNT_THRESHOLD            -> -DEDUCT_LOW_TRADE_COUNT
    Suspicious win     win_rate > HIGH_WIN_RATE_WARNING        -> -DEDUCT_SUSPICIOUS_WIN_RATE
    rate trap          AND profit_factor < SUSPICIOUS_WIN_PF
    Unprofitable       profit_factor < UNPROFITABLE_PF        -> -DEDUCT_UNPROFITABLE
    Marginal profit    UNPROFITABLE <= profit_factor < MARGINAL -> -DEDUCT_MARGINAL_PROFIT
    High drawdown      max_drawdown > HIGH_DD                  -> -DEDUCT_HIGH_DRAWDOWN
    Medium drawdown    MEDIUM_DD < max_drawdown <= HIGH_DD     -> -DEDUCT_MEDIUM_DRAWDOWN
    Bad risk-reward    avg_win/avg_loss < 1.0                  -> -DEDUCT_BAD_RISK_REWARD
    Costs eat profits  pre-cost > 0 but post-cost < 0          -> -DEDUCT_COSTS_EAT_PROFITS
                       (only when caller supplies pre_cost_pnl)
    OOS degradation    oos.degradation_percent > 0.25          -> -DEDUCT_OOS_DEGRADATION
                       (only when oos result supplied)
    Walk-fwd inconsist consistency_score < 0.60                -> -DEDUCT_WF_INCONSISTENT
                       (only when wf result supplied)
    Fragile params     fragile = True                          -> -DEDUCT_FRAGILE_PARAMS
                       (only when sensitivity result supplied)

The check ordering is documented (and tested) for stability — a future
edit that re-orders should not change scores, but the *messages* are
emitted in the order checks fire so the audit trail is predictable.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.reliability.constants import (
    BAD_RISK_REWARD_RATIO,
    DEDUCT_BAD_RISK_REWARD,
    DEDUCT_COSTS_EAT_PROFITS,
    DEDUCT_FRAGILE_PARAMS,
    DEDUCT_HIGH_DRAWDOWN,
    DEDUCT_LOW_TRADE_COUNT,
    DEDUCT_MARGINAL_PROFIT,
    DEDUCT_MEDIUM_DRAWDOWN,
    DEDUCT_OOS_DEGRADATION,
    DEDUCT_SUSPICIOUS_WIN_RATE,
    DEDUCT_UNPROFITABLE,
    DEDUCT_WF_INCONSISTENT,
    GRADE_VERDICTS,
    HIGH_DRAWDOWN_THRESHOLD,
    HIGH_WIN_RATE_WARNING_THRESHOLD,
    LOW_TRADE_COUNT_THRESHOLD,
    MARGINAL_PROFIT_FACTOR,
    MEDIUM_DRAWDOWN_THRESHOLD,
    OOS_DEGRADATION_WARNING_THRESHOLD,
    SUSPICIOUS_WIN_RATE_PROFIT_FACTOR,
    TRUST_SCORE_GRADES,
    UNPROFITABLE_PROFIT_FACTOR,
    WF_CONSISTENCY_THRESHOLD,
    Grade,
)

if TYPE_CHECKING:
    from app.strategy_engine.backtest.runner import BacktestResult


class TrustScore(BaseModel):
    """Result of :func:`calculate_trust_score`. Frozen + JSON-friendly."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score: int = Field(..., ge=0, le=100)
    grade: Grade
    verdict: str = Field(..., min_length=1, max_length=256)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    passed_checks: tuple[str, ...] = Field(default_factory=tuple)
    failed_checks: tuple[str, ...] = Field(default_factory=tuple)
    suggestions: tuple[str, ...] = Field(default_factory=tuple)


def grade_for(score: int) -> Grade:
    """Map a 0-100 score to its A-F grade per :data:`TRUST_SCORE_GRADES`."""
    clamped = max(0, min(100, score))
    for grade, (low, high) in TRUST_SCORE_GRADES.items():
        if low <= clamped <= high:
            return grade
    raise ValueError(  # pragma: no cover — ranges are contiguous, tested in test_constants
        f"No grade range covers score={score}."
    )


# ─── Optional input shapes (forward refs to sibling modules) ──────────


class _OOSInput(BaseModel):
    """Minimal OOS shape — full OOSResult lives in :mod:`out_of_sample`."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    degradation_percent: float


class _WFInput(BaseModel):
    """Minimal walk-forward shape — full WalkForwardResult in :mod:`walk_forward`."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    consistency_score: float = Field(..., ge=0, le=1)


class _SensitivityInput(BaseModel):
    """Minimal sensitivity shape — full SensitivityResult in :mod:`parameter_sensitivity`."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    fragile: bool


# ─── Public API ────────────────────────────────────────────────────────


def calculate_trust_score(
    backtest: BacktestResult,
    *,
    oos_degradation: float | None = None,
    walk_forward_consistency: float | None = None,
    sensitivity_fragile: bool | None = None,
    pre_cost_pnl: float | None = None,
) -> TrustScore:
    """Score the backtest. Optional inputs activate their checks.

    Args:
        backtest: Phase 3 ``BacktestResult`` (pure-Python source of truth).
        oos_degradation: Train→test degradation as a fraction (e.g. 0.30
            for a 30 % drop). When ``None`` the OOS check is skipped.
        walk_forward_consistency: Fraction of WF windows that passed
            (0-1). When ``None`` the WF check is skipped.
        sensitivity_fragile: ``True`` if more than the fragile threshold
            of variants degraded. When ``None`` the sensitivity check
            is skipped.
        pre_cost_pnl: When supplied, enables the "costs eat profits"
            check — flags strategies whose pre-cost P&L was positive
            but whose post-cost P&L (the backtest's ``total_pnl``) is
            negative.

    Returns:
        :class:`TrustScore` with the deterministic score, grade, and
        the human-readable check breakdown.
    """
    score = 100
    warnings: list[str] = []
    passed: list[str] = []
    failed: list[str] = []
    suggestions: list[str] = []

    # ─── 1. Trade count ─────────────────────────────────────────────
    label = f"Trade count >= {LOW_TRADE_COUNT_THRESHOLD}"
    if backtest.total_trades < LOW_TRADE_COUNT_THRESHOLD:
        score -= DEDUCT_LOW_TRADE_COUNT
        failed.append(label)
        warnings.append(
            f"Low trade count ({backtest.total_trades}); statistics are noisy "
            f"below {LOW_TRADE_COUNT_THRESHOLD} trades."
        )
        suggestions.append(
            "Backtest a longer period or relax the entry rules to gather at least 30 trades."
        )
    else:
        passed.append(label)

    # ─── 2. Suspicious win-rate trap ────────────────────────────────
    label = f"Win rate not suspicious (<= {HIGH_WIN_RATE_WARNING_THRESHOLD:.2f})"
    if backtest.win_rate > HIGH_WIN_RATE_WARNING_THRESHOLD and not _profit_factor_is_at_least(
        backtest.profit_factor, SUSPICIOUS_WIN_RATE_PROFIT_FACTOR
    ):
        score -= DEDUCT_SUSPICIOUS_WIN_RATE
        failed.append(label)
        warnings.append(
            "Win rate is high, but the strategy may still be unreliable. "
            "Check average loss, drawdown, cost impact, and out-of-sample result."
        )
        suggestions.append(
            "High win rates with a low profit factor often signal small wins "
            "and rare large losses. Compare averageWin to averageLoss."
        )
    else:
        passed.append(label)

    # ─── 3. Profit factor — unprofitable / marginal ────────────────
    label_unp = f"Profit factor >= {UNPROFITABLE_PROFIT_FACTOR}"
    if backtest.profit_factor < UNPROFITABLE_PROFIT_FACTOR:
        score -= DEDUCT_UNPROFITABLE
        failed.append(label_unp)
        warnings.append(
            f"Profit factor {_format_pf(backtest.profit_factor)} indicates "
            "the strategy is losing money in aggregate."
        )
        suggestions.append(
            "Re-examine entry / exit rules; consider a tighter stop loss or a "
            "wider target before deploying."
        )
    elif backtest.profit_factor < MARGINAL_PROFIT_FACTOR:
        score -= DEDUCT_MARGINAL_PROFIT
        failed.append(f"Profit factor >= {MARGINAL_PROFIT_FACTOR}")
        warnings.append(
            f"Profit factor {_format_pf(backtest.profit_factor)} is marginal; "
            "small slippage / cost changes could flip the strategy negative."
        )
    else:
        passed.append(label_unp)

    # ─── 4. Drawdown ────────────────────────────────────────────────
    label_dd = f"Max drawdown <= {int(HIGH_DRAWDOWN_THRESHOLD * 100)} %"
    if backtest.max_drawdown > HIGH_DRAWDOWN_THRESHOLD:
        score -= DEDUCT_HIGH_DRAWDOWN
        failed.append(label_dd)
        warnings.append(
            f"Max drawdown {backtest.max_drawdown * 100:.1f} % is high; "
            "few traders can sit through this."
        )
        suggestions.append("Reduce position size or tighten the stop loss to cap drawdown.")
    elif backtest.max_drawdown > MEDIUM_DRAWDOWN_THRESHOLD:
        score -= DEDUCT_MEDIUM_DRAWDOWN
        failed.append(f"Max drawdown <= {int(MEDIUM_DRAWDOWN_THRESHOLD * 100)} %")
    else:
        passed.append(label_dd)

    # ─── 5. Risk-reward ─────────────────────────────────────────────
    label_rr = f"Risk-reward ratio >= {BAD_RISK_REWARD_RATIO}"
    rr = _risk_reward(backtest.average_win, backtest.average_loss)
    if rr is not None and rr < BAD_RISK_REWARD_RATIO:
        score -= DEDUCT_BAD_RISK_REWARD
        failed.append(label_rr)
        warnings.append(
            f"Average win ({backtest.average_win:.2f}) is smaller than average "
            f"loss ({backtest.average_loss:.2f}); the strategy needs a high "
            "win rate just to break even."
        )
    elif rr is not None:
        passed.append(label_rr)
    # rr is None (e.g. no losses yet) -> neither passed nor failed; the
    # profit-factor / win-rate checks already cover that case.

    # ─── 6. Costs eat profits (only if caller supplied pre-cost) ────
    if pre_cost_pnl is not None:
        label_cost = "Costs do not eat profits"
        if pre_cost_pnl > 0 and backtest.total_pnl < 0:
            score -= DEDUCT_COSTS_EAT_PROFITS
            failed.append(label_cost)
            warnings.append(
                "Strategy is profitable before costs but loses money after — "
                "fees and slippage are eating the edge."
            )
            suggestions.append(
                "Trade less frequently or use a broker / order type with lower round-trip costs."
            )
        else:
            passed.append(label_cost)

    # ─── 7. OOS degradation ─────────────────────────────────────────
    if oos_degradation is not None:
        label_oos = f"Out-of-sample degradation <= {int(OOS_DEGRADATION_WARNING_THRESHOLD * 100)} %"
        if oos_degradation > OOS_DEGRADATION_WARNING_THRESHOLD:
            score -= DEDUCT_OOS_DEGRADATION
            failed.append(label_oos)
            warnings.append(
                f"Out-of-sample performance degraded {oos_degradation * 100:.1f} % "
                "from training to testing; possible over-fitting."
            )
            suggestions.append(
                "Simplify the strategy (fewer indicators) or extend the training "
                "window before deploying."
            )
        else:
            passed.append(label_oos)

    # ─── 8. Walk-forward consistency ────────────────────────────────
    if walk_forward_consistency is not None:
        label_wf = f"Walk-forward consistency >= {int(WF_CONSISTENCY_THRESHOLD * 100)} %"
        if walk_forward_consistency < WF_CONSISTENCY_THRESHOLD:
            score -= DEDUCT_WF_INCONSISTENT
            failed.append(label_wf)
            warnings.append(
                f"Only {walk_forward_consistency * 100:.0f} % of walk-forward "
                "windows were profitable; the edge is inconsistent."
            )
            suggestions.append(
                "Stress-test on more recent data — consistency below 60 % means "
                "the strategy's edge depended on a specific regime."
            )
        else:
            passed.append(label_wf)

    # ─── 9. Parameter sensitivity ───────────────────────────────────
    if sensitivity_fragile is not None:
        label_sens = "Strategy is robust to parameter perturbations"
        if sensitivity_fragile:
            score -= DEDUCT_FRAGILE_PARAMS
            failed.append(label_sens)
            warnings.append(
                "Small ±20 % parameter perturbations cause large score swings "
                "— the strategy is fragile / over-fit to specific values."
            )
            suggestions.append(
                "Pick parameter values that perform well across a range, not the "
                "single best in-sample tuning."
            )
        else:
            passed.append(label_sens)

    # ─── Final clamp and grade ──────────────────────────────────────
    final_score = max(0, min(100, score))
    grade = grade_for(final_score)

    return TrustScore(
        score=final_score,
        grade=grade,
        verdict=GRADE_VERDICTS[grade],
        warnings=tuple(warnings),
        passed_checks=tuple(passed),
        failed_checks=tuple(failed),
        suggestions=tuple(suggestions),
    )


# ─── Internal helpers ──────────────────────────────────────────────────


def _profit_factor_is_at_least(pf: float, threshold: float) -> bool:
    """``math.inf`` (no losses) trivially exceeds any finite threshold."""
    if math.isinf(pf):
        return True
    return pf >= threshold


def _format_pf(pf: float) -> str:
    """Display 'inf' rather than '0.00' for the wins-only edge case."""
    return "inf" if math.isinf(pf) else f"{pf:.2f}"


def _risk_reward(avg_win: float, avg_loss: float) -> float | None:
    """avg_win / avg_loss when both are non-zero; None otherwise.

    ``avg_loss`` from Phase 3's :mod:`metrics` is the magnitude (positive
    number), so the ratio direction is correct as written.
    """
    if avg_loss == 0 or avg_win == 0:
        return None
    return avg_win / avg_loss


__all__ = ["TrustScore", "calculate_trust_score", "grade_for"]
