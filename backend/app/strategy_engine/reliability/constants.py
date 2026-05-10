"""Locked numerical thresholds for the reliability engine.

Every magic number used by the scoring / OOS / walk-forward / sensitivity
modules lives here so reviews don't have to chase across files. Changing
a value here changes behaviour everywhere — call out the rationale in
the commit message.

The grade ranges and warning thresholds are the **product-locked**
defaults from the Phase 4 approval message; do not invent new ones in
sibling modules.
"""

from __future__ import annotations

from typing import Final, Literal

# ─── Warning thresholds ────────────────────────────────────────────────


#: Win rate above which we suspect a "win-rate trap" — high-frequency
#: small wins masking large losses. Triggers a deep-dive check against
#: profit factor, drawdown, and trade count.
HIGH_WIN_RATE_WARNING_THRESHOLD: Final[float] = 0.85

#: Out-of-sample degradation that signals over-fitting. Computed as
#: ``(train_return - test_return) / abs(train_return)``. Above 25 % the
#: strategy likely memorised the training set.
OOS_DEGRADATION_WARNING_THRESHOLD: Final[float] = 0.25

#: Number of tumbling windows the walk-forward engine produces. Each
#: window has its own internal 70/30 train/test split.
WALK_FORWARD_WINDOWS: Final[int] = 5

#: Per-window train fraction (0.7 = first 70 % of the window's data).
WALK_FORWARD_TRAIN_FRACTION: Final[float] = 0.70

#: Out-of-sample train fraction (full-data 70/30).
OOS_TRAIN_FRACTION: Final[float] = 0.70

#: Fraction by which each numeric parameter is varied in the sensitivity
#: test. The variants are at ``[-VAR, -VAR/2, +VAR/2, +VAR]`` of the
#: base value (i.e. -20 %, -10 %, +10 %, +20 % when VAR = 0.20).
PARAMETER_SENSITIVITY_VARIATION: Final[float] = 0.20

#: Fraction of fragile variants that triggers the "fragile strategy"
#: warning. > 30 % of tested variants degraded -> fragile.
PARAMETER_SENSITIVITY_FRAGILE_THRESHOLD: Final[float] = 0.30

#: Trust-score drop (in score points) that marks a single variant as
#: degraded. > 20 points worse than the base score -> degraded.
SENSITIVITY_DEGRADATION_POINTS: Final[int] = 20


# ─── Trust-score grade ranges ─────────────────────────────────────────

Grade = Literal["A", "B", "C", "D", "F"]

#: Inclusive ``[low, high]`` ranges for each grade. The function
#: :func:`app.strategy_engine.reliability.trust_score.grade_for` consumes
#: these. Keep the lower bounds non-overlapping and contiguous.
TRUST_SCORE_GRADES: Final[dict[Grade, tuple[int, int]]] = {
    "A": (85, 100),
    "B": (70, 84),
    "C": (55, 69),
    "D": (40, 54),
    "F": (0, 39),
}

#: Human-readable verdict shown alongside the grade.
GRADE_VERDICTS: Final[dict[Grade, str]] = {
    "A": "Excellent — strong reliability across checks",
    "B": "Good — moderately reliable",
    "C": "Fair — proceed with caution",
    "D": "Risky — paper trade extensively before live",
    "F": "Unreliable — do not deploy",
}


# ─── Trust-score deductions ───────────────────────────────────────────


#: Deduction for trade counts below :data:`LOW_TRADE_COUNT_THRESHOLD` —
#: small samples produce noisy stats.
DEDUCT_LOW_TRADE_COUNT: Final[int] = 20
LOW_TRADE_COUNT_THRESHOLD: Final[int] = 30

#: Deduction when win rate is suspiciously high without a profit-factor
#: cushion. Triggered ONLY when both conditions hold (win rate elevated
#: AND profit factor below the cushion threshold).
DEDUCT_SUSPICIOUS_WIN_RATE: Final[int] = 25
SUSPICIOUS_WIN_RATE_PROFIT_FACTOR: Final[float] = 1.5

#: Profit-factor deductions.
DEDUCT_UNPROFITABLE: Final[int] = 30
UNPROFITABLE_PROFIT_FACTOR: Final[float] = 1.0
DEDUCT_MARGINAL_PROFIT: Final[int] = 10
MARGINAL_PROFIT_FACTOR: Final[float] = 1.3

#: Drawdown deductions.
DEDUCT_HIGH_DRAWDOWN: Final[int] = 25
HIGH_DRAWDOWN_THRESHOLD: Final[float] = 0.30
DEDUCT_MEDIUM_DRAWDOWN: Final[int] = 10
MEDIUM_DRAWDOWN_THRESHOLD: Final[float] = 0.20

#: Risk-reward (avg_win / avg_loss) deduction. < 1.0 -> winners are
#: smaller than losers, requires a high win rate to be profitable.
DEDUCT_BAD_RISK_REWARD: Final[int] = 15
BAD_RISK_REWARD_RATIO: Final[float] = 1.0

#: Reserved for the cost-adjusted check (Phase 4 accepts the deduction
#: but the simulator already applies costs in-line; the check fires
#: only when caller-supplied "pre-cost" PnL is positive while the
#: backtest's post-cost PnL is negative).
DEDUCT_COSTS_EAT_PROFITS: Final[int] = 20

#: Optional-input deductions — only applied when the corresponding
#: result is supplied to :func:`calculate_trust_score`.
DEDUCT_OOS_DEGRADATION: Final[int] = 20
DEDUCT_WF_INCONSISTENT: Final[int] = 15
DEDUCT_FRAGILE_PARAMS: Final[int] = 15

#: Walk-forward consistency below which the strategy is judged
#: inconsistent. 0.60 = at least 3 of 5 windows must be profitable.
WF_CONSISTENCY_THRESHOLD: Final[float] = 0.60


__all__ = [
    "BAD_RISK_REWARD_RATIO",
    "DEDUCT_BAD_RISK_REWARD",
    "DEDUCT_COSTS_EAT_PROFITS",
    "DEDUCT_FRAGILE_PARAMS",
    "DEDUCT_HIGH_DRAWDOWN",
    "DEDUCT_LOW_TRADE_COUNT",
    "DEDUCT_MARGINAL_PROFIT",
    "DEDUCT_MEDIUM_DRAWDOWN",
    "DEDUCT_OOS_DEGRADATION",
    "DEDUCT_SUSPICIOUS_WIN_RATE",
    "DEDUCT_UNPROFITABLE",
    "DEDUCT_WF_INCONSISTENT",
    "GRADE_VERDICTS",
    "HIGH_DRAWDOWN_THRESHOLD",
    "HIGH_WIN_RATE_WARNING_THRESHOLD",
    "LOW_TRADE_COUNT_THRESHOLD",
    "MARGINAL_PROFIT_FACTOR",
    "MEDIUM_DRAWDOWN_THRESHOLD",
    "OOS_DEGRADATION_WARNING_THRESHOLD",
    "OOS_TRAIN_FRACTION",
    "PARAMETER_SENSITIVITY_FRAGILE_THRESHOLD",
    "PARAMETER_SENSITIVITY_VARIATION",
    "SENSITIVITY_DEGRADATION_POINTS",
    "SUSPICIOUS_WIN_RATE_PROFIT_FACTOR",
    "TRUST_SCORE_GRADES",
    "UNPROFITABLE_PROFIT_FACTOR",
    "WALK_FORWARD_TRAIN_FRACTION",
    "WALK_FORWARD_WINDOWS",
    "WF_CONSISTENCY_THRESHOLD",
    "Grade",
]
