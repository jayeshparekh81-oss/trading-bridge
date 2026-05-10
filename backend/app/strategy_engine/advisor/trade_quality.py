"""Trade Quality Score — Phase 7 advisor add-on.

Pure deterministic 0-100 scorer that reads a Phase 3
:class:`BacktestResult` and answers:

> "Are the actual trades well-structured?"

Distinct from the Phase 4 Trust Score (reliability of the result) and
the Phase 6 Truth Score (fake-detection of the backtest). Trade
Quality looks at the *trades themselves* — risk-reward, dispersion,
drawdown discipline, cost survival, and exit hygiene.

Five locked components, each scored 0-100 and combined as a weighted
average:

    1. Risk-Reward         (weight 0.25)
    2. Win-Loss Consistency (weight 0.20)
    3. Drawdown Discipline (weight 0.20)
    4. Cost Survival       (weight 0.20)
    5. Exit Discipline     (weight 0.15)

The cost-survival component requires the gross (pre-cost) P&L to
compute a ratio; ``BacktestResult`` does not currently carry that
field, so the public entry point accepts an optional ``gross_pnl``
keyword. When omitted, component 4 returns the documented unknown-
sentinel (50) and flags the gap in its Hinglish tip.

The module is **AI-free**: no LLM calls, no network, no clock reads.
Same inputs always produce the same :class:`TradeQualityReport`.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.strategy_engine.backtest.runner import BacktestResult

# ─── Locked constants ──────────────────────────────────────────────────

MIN_TRADES_FOR_QUALITY: Final[int] = 10
"""Below this trade count the score is statistically meaningless. The
report degrades to a placeholder F-grade with an "insufficient data"
summary instead of inventing a verdict."""

COMPONENT_WEIGHTS: Final[tuple[float, float, float, float, float]] = (
    0.25,  # risk_reward
    0.20,  # consistency
    0.20,  # drawdown
    0.20,  # cost_survival
    0.15,  # exit_discipline
)
"""Per-component weights. Validated at module import to sum to ``1.0``."""

GRADE_BOUNDS: Final[dict[str, float]] = {
    "A": 90.0,
    "B": 75.0,
    "C": 60.0,
    "D": 45.0,
}
"""Lower bound (inclusive) for each letter grade. Anything below
``GRADE_BOUNDS["D"]`` is grade F."""

# Canonical structured exit reasons — match
# :class:`app.strategy_engine.engines.exit.ExitType` string values.
_STRUCTURED_EXITS: Final[frozenset[str]] = frozenset({"target", "stop_loss", "trailing_stop"})


# Module-load assertion — the weighted-average rollup assumes the
# weights sum to 1.0; a typo here would silently distort every score.
if not math.isclose(sum(COMPONENT_WEIGHTS), 1.0, abs_tol=1e-9):
    raise RuntimeError(f"COMPONENT_WEIGHTS must sum to 1.0; got {sum(COMPONENT_WEIGHTS)}")


# ─── Models ────────────────────────────────────────────────────────────

OverallGrade = Literal["A", "B", "C", "D", "F"]


class TradeQualityComponent(BaseModel):
    """One component's contribution to the overall trade-quality score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_name: str = Field(..., min_length=1, max_length=64)
    score: float = Field(..., ge=0.0, le=100.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    hinglish_tip: str = Field(..., min_length=1, max_length=512)


class TradeQualityReport(BaseModel):
    """Top-level trade-quality output.

    ``components`` is empty only when the backtest had fewer than
    :data:`MIN_TRADES_FOR_QUALITY` trades — the report still parses,
    but every numeric field is the insufficient-data sentinel.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall_score: float = Field(..., ge=0.0, le=100.0)
    grade: OverallGrade
    components: tuple[TradeQualityComponent, ...] = Field(default_factory=tuple)
    overall_summary_hinglish: str = Field(..., min_length=1, max_length=512)
    strengths: tuple[str, ...] = Field(default_factory=tuple)
    weaknesses: tuple[str, ...] = Field(default_factory=tuple)


# ─── Public API ────────────────────────────────────────────────────────


def compute_trade_quality(
    backtest: BacktestResult,
    *,
    gross_pnl: float | None = None,
) -> TradeQualityReport:
    """Compute the 0-100 :class:`TradeQualityReport` for ``backtest``.

    Args:
        backtest: Phase 3 backtest result. Read-only.
        gross_pnl: Pre-cost P&L for the same backtest, when available.
            Enables the Cost Survival component to compute the
            survival ratio ``backtest.total_pnl / gross_pnl``. When
            ``None``, component 4 returns the unknown sentinel (50)
            and the Hinglish tip flags the missing data.

    Returns:
        :class:`TradeQualityReport` with overall score, grade,
        per-component breakdown, and strengths / weaknesses.
    """
    if backtest.total_trades < MIN_TRADES_FOR_QUALITY:
        return _insufficient_data_report(backtest.total_trades)

    components: list[TradeQualityComponent] = [
        _risk_reward_component(backtest),
        _consistency_component(backtest),
        _drawdown_component(backtest),
        _cost_survival_component(backtest, gross_pnl=gross_pnl),
        _exit_discipline_component(backtest),
    ]

    overall = _weighted_average(components)
    grade = _grade_for(overall)

    return TradeQualityReport(
        overall_score=round(overall, 2),
        grade=grade,
        components=tuple(components),
        overall_summary_hinglish=_overall_summary(grade),
        strengths=tuple(_strengths(components)),
        weaknesses=tuple(_weaknesses(components)),
    )


# ─── Component 1 — Risk-Reward ─────────────────────────────────────────


def _risk_reward_component(backtest: BacktestResult) -> TradeQualityComponent:
    """``avg_win / abs(avg_loss)`` mapped onto a six-band score.

    Phase 3 stores ``average_loss`` as a magnitude already; we still
    take ``abs`` defensively in case a future runner change flips the
    sign convention.
    """
    avg_win = backtest.average_win
    avg_loss = abs(backtest.average_loss)

    if avg_loss == 0.0:
        # No losing trades. Treat as the highest band — ``inf`` is a
        # legitimate "perfect" reading but suspicious; the tip
        # surfaces that.
        rr = float("inf")
        score = 100.0
        tip = "RR infinite hai - koi loss nahi. Sample size verify karo before trusting this."
    else:
        rr = avg_win / avg_loss
        score = _rr_score_band(rr)
        tip = _rr_tip(rr, score)

    return TradeQualityComponent(
        component_name="risk_reward",
        score=score,
        weight=COMPONENT_WEIGHTS[0],
        hinglish_tip=tip,
    )


def _rr_score_band(rr: float) -> float:
    if rr >= 2.5:
        return 100.0
    if rr >= 2.0:
        return 85.0
    if rr >= 1.5:
        return 70.0
    if rr >= 1.0:
        return 50.0
    if rr >= 0.5:
        return 30.0
    return 10.0


def _rr_tip(rr: float, score: float) -> str:
    rr_str = f"{rr:.2f}"
    if score >= 85.0:
        comment = "Strong edge - winners losers se kaafi bade hain."
    elif score >= 70.0:
        comment = "Achha hai. >2.0 excellent hota hai."
    elif score >= 50.0:
        comment = "Tight hai. Stop loss tighter ya target wider karo."
    else:
        comment = "Average loss winners se bada hai - structure galat hai."
    return f"Aap ₹1 risk leke ₹{rr_str} kama rahe ho. {comment}"


# ─── Component 2 — Win-Loss Consistency ────────────────────────────────


def _consistency_component(backtest: BacktestResult) -> TradeQualityComponent:
    """Coefficient of variation on per-trade pnl: lower is better.

    ``cv = std(pnls) / |mean(pnls)|``. When ``|mean|`` is below a tiny
    epsilon the metric is degenerate (the strategy is effectively
    break-even on average), so we return the 50 sentinel rather than
    a numerically unstable score.
    """
    pnls = [t.pnl for t in backtest.trades]
    n = len(pnls)
    if n < 2:
        # Single-trade case — variance is undefined.
        return TradeQualityComponent(
            component_name="consistency",
            score=50.0,
            weight=COMPONENT_WEIGHTS[1],
            hinglish_tip=(
                f"Sirf {n} trade hai - consistency measure karne ke liye 2+ trades chahiye."
            ),
        )

    mean = sum(pnls) / n
    variance = sum((p - mean) ** 2 for p in pnls) / n
    std = math.sqrt(variance)

    if abs(mean) < 1e-9:
        # Break-even strategy — cv blows up; fall back to the unknown
        # sentinel and call it out.
        return TradeQualityComponent(
            component_name="consistency",
            score=50.0,
            weight=COMPONENT_WEIGHTS[1],
            hinglish_tip=(
                "Average pnl lagbhag zero hai - consistency ratio "
                "meaningfully calculate nahi ho sakta."
            ),
        )

    cv = std / abs(mean)
    score = _cv_score_band(cv)
    tip = _cv_tip(cv, score, n)

    return TradeQualityComponent(
        component_name="consistency",
        score=score,
        weight=COMPONENT_WEIGHTS[1],
        hinglish_tip=tip,
    )


def _cv_score_band(cv: float) -> float:
    if cv < 1.0:
        return 100.0
    if cv < 2.0:
        return 80.0
    if cv < 3.0:
        return 60.0
    if cv < 5.0:
        return 40.0
    return 20.0


def _cv_tip(cv: float, score: float, n: int) -> str:
    cv_str = f"{cv:.2f}"
    if score >= 80.0:
        return f"Trades consistent hain - {n} trades mein variance kam hai (cv={cv_str})."
    if score >= 60.0:
        return (
            f"Variance manageable hai (cv={cv_str}). Kuch trades bade, kuch chhote - normal range."
        )
    return (
        f"Trades zyada wild hain - kuch bahut bade, kuch bahut chhote "
        f"(cv={cv_str}). Position sizing tighten karo."
    )


# ─── Component 3 — Drawdown Discipline ─────────────────────────────────


def _drawdown_component(backtest: BacktestResult) -> TradeQualityComponent:
    """``max_drawdown`` (0-1 fraction) mapped onto a six-band score."""
    dd = backtest.max_drawdown
    score = _dd_score_band(dd)
    dd_pct = dd * 100.0
    tip = _dd_tip(dd_pct, score)
    return TradeQualityComponent(
        component_name="drawdown",
        score=score,
        weight=COMPONENT_WEIGHTS[2],
        hinglish_tip=tip,
    )


def _dd_score_band(dd: float) -> float:
    if dd < 0.05:
        return 100.0
    if dd < 0.10:
        return 90.0
    if dd < 0.15:
        return 75.0
    if dd < 0.25:
        return 50.0
    if dd < 0.40:
        return 25.0
    return 10.0


def _dd_tip(dd_pct: float, score: float) -> str:
    dd_str = f"{dd_pct:.1f}"
    if score >= 90.0:
        comment = "Capital safe hai - position sizing strong hai."
    elif score >= 75.0:
        comment = "Manageable hai - stop loss strict rakho."
    elif score >= 50.0:
        comment = "Border line hai - risk per trade kam karo."
    else:
        comment = (
            f"Bahut zyada - har ₹100 par ~₹{round(dd_pct)} loss. Risk parameters re-check karo."
        )
    return f"Worst loss period {dd_str}% tha. {comment}"


# ─── Component 4 — Cost Survival ───────────────────────────────────────


def _cost_survival_component(
    backtest: BacktestResult,
    *,
    gross_pnl: float | None,
) -> TradeQualityComponent:
    """``backtest.total_pnl / gross_pnl`` mapped onto a six-band score.

    When ``gross_pnl`` is ``None`` we cannot compute a ratio and the
    component returns the unknown sentinel (50). When ``gross_pnl <=
    0`` the ratio is undefined (or paradoxical) so we also return the
    sentinel and explain why.
    """
    if gross_pnl is None:
        return TradeQualityComponent(
            component_name="cost_survival",
            score=50.0,
            weight=COMPONENT_WEIGHTS[3],
            hinglish_tip=(
                "Cost data uplabdh nahi hai - gross (pre-cost) pnl "
                "pass karo to cost survival measure ho sake."
            ),
        )
    if gross_pnl <= 0:
        return TradeQualityComponent(
            component_name="cost_survival",
            score=50.0,
            weight=COMPONENT_WEIGHTS[3],
            hinglish_tip=(
                "Gross pnl non-positive hai - cost survival ratio calculate nahi ho sakta."
            ),
        )

    ratio = backtest.total_pnl / gross_pnl
    score = _cost_survival_score_band(ratio)
    tip = _cost_survival_tip(ratio, score)
    return TradeQualityComponent(
        component_name="cost_survival",
        score=score,
        weight=COMPONENT_WEIGHTS[3],
        hinglish_tip=tip,
    )


def _cost_survival_score_band(ratio: float) -> float:
    if ratio > 0.85:
        return 100.0
    if ratio >= 0.70:
        return 80.0
    if ratio >= 0.50:
        return 60.0
    if ratio >= 0.30:
        return 40.0
    if ratio >= 0.10:
        return 20.0
    return 10.0


def _cost_survival_tip(ratio: float, score: float) -> str:
    pct = max(0.0, ratio * 100.0)
    pct_str = f"{pct:.1f}"
    if score >= 80.0:
        comment = "Costs ka impact kam hai - strategy strong hai."
    elif score >= 60.0:
        comment = "Costs notable hain but strategy abhi profitable."
    elif score >= 40.0:
        comment = "Charges bahut khaa rahe hain - profit factor check karo."
    else:
        comment = "Strategy costs ke baad mushkil se survive kar rahi."
    return f"Charges ke baad {pct_str}% profit reh raha hai. {comment}"


# ─── Component 5 — Exit Discipline ─────────────────────────────────────


def _exit_discipline_component(backtest: BacktestResult) -> TradeQualityComponent:
    """Fraction of trades that exited via target / stop_loss /
    trailing_stop. Higher = more disciplined."""
    total = backtest.total_trades
    structured = sum(1 for t in backtest.trades if t.exit_reason in _STRUCTURED_EXITS)
    fraction = structured / total if total > 0 else 0.0
    score = _exit_score_band(fraction)
    pct_str = f"{fraction * 100:.0f}"
    tip = _exit_tip(fraction, score, pct_str)
    return TradeQualityComponent(
        component_name="exit_discipline",
        score=score,
        weight=COMPONENT_WEIGHTS[4],
        hinglish_tip=tip,
    )


def _exit_score_band(fraction: float) -> float:
    if fraction >= 0.95:
        return 100.0
    if fraction >= 0.85:
        return 85.0
    if fraction >= 0.70:
        return 70.0
    if fraction >= 0.50:
        return 50.0
    return 30.0


def _exit_tip(fraction: float, score: float, pct_str: str) -> str:
    if score >= 85.0:
        comment = "Strong discipline - rules clear hain."
    elif score >= 70.0:
        comment = "Theek hai - kuch trades indicator ya time exits par chhoot rahi."
    elif score >= 50.0:
        comment = "Half trades structured exits ke bahar nikal rahi - rules tighten karo."
    else:
        comment = "Bahut kam trades target ya stop par band hue - risk plan weak hai."
    return f"{pct_str}% trades structured exits se band hue. {comment}"


# ─── Aggregation ───────────────────────────────────────────────────────


def _weighted_average(components: list[TradeQualityComponent]) -> float:
    return sum(c.score * c.weight for c in components)


def _grade_for(score: float) -> OverallGrade:
    if score >= GRADE_BOUNDS["A"]:
        return "A"
    if score >= GRADE_BOUNDS["B"]:
        return "B"
    if score >= GRADE_BOUNDS["C"]:
        return "C"
    if score >= GRADE_BOUNDS["D"]:
        return "D"
    return "F"


_OVERALL_SUMMARIES: Final[dict[OverallGrade, str]] = {
    "A": (
        "Trade quality strong hai. Stop loss + target discipline aur consistency dono achhi hain."
    ),
    "B": ("Trade quality theek hai. Kuch components improvement chahte hain."),
    "C": ("Trade quality concerning. Risk-reward ya consistency ya drawdown - kuch toh galat hai."),
    "D": ("Trade quality concerning. Risk-reward ya consistency ya drawdown - kuch toh galat hai."),
    "F": "Trade quality bahut kharab. Strategy revisit karo.",
}


def _overall_summary(grade: OverallGrade) -> str:
    return _OVERALL_SUMMARIES[grade]


_COMPONENT_LABELS: Final[dict[str, tuple[str, str]]] = {
    # name → (strength label, weakness label)
    "risk_reward": ("Strong risk-reward ratio", "Risk-reward ratio too low"),
    "consistency": ("Consistent trade outcomes", "Trade outcomes too variable"),
    "drawdown": ("Drawdown well-controlled", "Drawdown too high"),
    "cost_survival": ("Costs survive well", "Costs erode profit"),
    "exit_discipline": ("Strong exit discipline", "Weak exit discipline"),
}


def _strengths(components: list[TradeQualityComponent]) -> list[str]:
    out: list[str] = []
    for c in components:
        if c.score >= 80.0:
            label = _COMPONENT_LABELS.get(c.component_name, (c.component_name, ""))[0]
            out.append(label)
    return out


def _weaknesses(components: list[TradeQualityComponent]) -> list[str]:
    out: list[str] = []
    for c in components:
        if c.score < 50.0:
            label = _COMPONENT_LABELS.get(c.component_name, ("", c.component_name))[1]
            out.append(label)
    return out


# ─── Insufficient-data placeholder ─────────────────────────────────────


def _insufficient_data_report(observed_trades: int) -> TradeQualityReport:
    return TradeQualityReport(
        overall_score=0.0,
        grade="F",
        components=(),
        overall_summary_hinglish=(
            f"Sample chhota hai ({observed_trades} trades). Trade "
            "quality measure ke liye 30+ trades chahiye."
        ),
        strengths=(),
        weaknesses=(),
    )


__all__ = [
    "COMPONENT_WEIGHTS",
    "GRADE_BOUNDS",
    "MIN_TRADES_FOR_QUALITY",
    "OverallGrade",
    "TradeQualityComponent",
    "TradeQualityReport",
    "compute_trade_quality",
]
