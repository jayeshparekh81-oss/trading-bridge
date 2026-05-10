"""Locked numerical thresholds + deductions for the Truth Engine.

Every magic number used by :mod:`truth_score` lives here so reviews
have a single page to audit. Values overlap with Phase 4's reliability
constants where the Truth Engine consults the same metric (win rate,
drawdown, trade count) — those are *re-imported* rather than copied so
a future tightening in Phase 4 propagates automatically.

Deduction values are chosen so:

    * A clean strategy (no triggers) → 100.
    * A single severe red flag (e.g. unprofitable, OOS overfit) shaves
      the score into the C/D band on its own.
    * Stacking multiple red flags reaches F (< 40) without forcing
      individual deductions to be unrealistically large.
"""

from __future__ import annotations

from typing import Final, Literal

from app.strategy_engine.reliability.constants import (  # re-exported for cohesion
    BAD_RISK_REWARD_RATIO,
    HIGH_DRAWDOWN_THRESHOLD,
    HIGH_WIN_RATE_WARNING_THRESHOLD,
    LOW_TRADE_COUNT_THRESHOLD,
    MARGINAL_PROFIT_FACTOR,
    OOS_DEGRADATION_WARNING_THRESHOLD,
    SUSPICIOUS_WIN_RATE_PROFIT_FACTOR,
    TRUST_SCORE_GRADES,
    Grade,
)

# ─── Truth-specific thresholds ─────────────────────────────────────────


#: Average loss / average win ratio above which the asymmetry flags a
#: "small wins, rare large losses" trap. ``avg_loss > 1.5 x avg_win``
#: means a single losing trade undoes 1.5 winning trades.
AVG_LOSS_RATIO_THRESHOLD: Final[float] = 1.5

#: Cost-impact warning: when the caller supplies ``pre_cost_pnl``, the
#: warning fires if costs ate more than this fraction of the gross.
#: Pre-cost > 0 and (pre - post) / pre > 0.20 → warning.
COST_IMPACT_FRACTION_THRESHOLD: Final[float] = 0.20

#: Heuristic cost warning when ``pre_cost_pnl`` is not supplied: costs
#: are configured (non-zero) AND profit factor sits in the marginal
#: range (1.0 ≤ pf < 1.3). Below 1.0 the unprofitability check fires
#: instead — costs are not the headline issue.


# ─── Deductions ────────────────────────────────────────────────────────

# Fake-backtest bucket
DEDUCT_HIGH_WIN_RATE_RISK: Final[int] = 20
DEDUCT_LOW_TRADE_COUNT: Final[int] = 15
DEDUCT_POOR_RISK_REWARD: Final[int] = 10
DEDUCT_AVG_LOSS_DOMINATES: Final[int] = 12
DEDUCT_HIGH_DRAWDOWN: Final[int] = 15
DEDUCT_WEAK_PROFIT_FACTOR: Final[int] = 12

# Overfitting bucket
DEDUCT_OOS_DEGRADATION: Final[int] = 20
DEDUCT_FRAGILE_PARAMETERS: Final[int] = 15
#: Stacking penalty: when both OOS degradation AND parameter fragility
#: trigger, the combined evidence of overfitting is stronger than the
#: sum of parts — apply a small extra deduction.
DEDUCT_OVERFITTING_STACK: Final[int] = 8

# Execution bucket
DEDUCT_AMBIGUITY_OPTIMISTIC: Final[int] = 6
DEDUCT_UNREALISTIC_FRICTIONLESS: Final[int] = 8

# Cost bucket
DEDUCT_COST_IMPACT: Final[int] = 12


# ─── Verdict + risk-level mapping ──────────────────────────────────────


#: Verdict shown alongside the truth score. Three bands so the UI can
#: show a single primary call-to-action without reading every warning.
TRUTH_VERDICTS: Final[dict[Grade, str]] = {
    "A": "Ready for paper trading",
    "B": "Ready for paper trading",
    "C": "Needs improvement",
    "D": "Needs improvement",
    "F": "Not ready",
}

RiskLevelLiteral = Literal["low", "medium", "high", "extreme"]

#: Risk level is an orthogonal axis to grade — it counts triggered
#: warnings (across all four buckets). ``[low_max, medium_max, high_max]``
#: define inclusive upper bounds; > high_max → "extreme".
RISK_LEVEL_THRESHOLDS: Final[tuple[int, int, int]] = (1, 3, 5)


__all__ = [
    "AVG_LOSS_RATIO_THRESHOLD",
    "BAD_RISK_REWARD_RATIO",
    "COST_IMPACT_FRACTION_THRESHOLD",
    "DEDUCT_AMBIGUITY_OPTIMISTIC",
    "DEDUCT_AVG_LOSS_DOMINATES",
    "DEDUCT_COST_IMPACT",
    "DEDUCT_FRAGILE_PARAMETERS",
    "DEDUCT_HIGH_DRAWDOWN",
    "DEDUCT_HIGH_WIN_RATE_RISK",
    "DEDUCT_LOW_TRADE_COUNT",
    "DEDUCT_OOS_DEGRADATION",
    "DEDUCT_OVERFITTING_STACK",
    "DEDUCT_POOR_RISK_REWARD",
    "DEDUCT_UNREALISTIC_FRICTIONLESS",
    "DEDUCT_WEAK_PROFIT_FACTOR",
    "HIGH_DRAWDOWN_THRESHOLD",
    "HIGH_WIN_RATE_WARNING_THRESHOLD",
    "LOW_TRADE_COUNT_THRESHOLD",
    "MARGINAL_PROFIT_FACTOR",
    "OOS_DEGRADATION_WARNING_THRESHOLD",
    "RISK_LEVEL_THRESHOLDS",
    "SUSPICIOUS_WIN_RATE_PROFIT_FACTOR",
    "TRUST_SCORE_GRADES",
    "TRUTH_VERDICTS",
    "Grade",
    "RiskLevelLiteral",
]
