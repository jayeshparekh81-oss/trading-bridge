"""Base AI Advisor — deterministic, rule-based strategy guidance.

Walks ten rules from the Phase 7 spec and emits typed
:class:`Advice` records the UI can render into a checklist:

    1. Indicator suggestions (only-trend → add momentum; only-momentum
       → add trend).
    2. Missing stop loss.
    3. Missing exit primitive (defensive — Phase 1 schema enforces at
       least one, but the advisor surfaces it anyway in case a future
       schema relaxation lands).
    4. Indicator overload (> N indicators).
    5. High win-rate caution.
    6. Low trust score → paper trade extensively.
    7. Poor truth score → kill any live recommendation.
    8. Overfitting (OOS degradation surfaced via TruthReport).
    9. High drawdown → reduce position size.
    10. Market regime mismatch (when caller supplies a regime hint).
    11. Live deviation warning (when caller supplies a deviation report).

The output also exposes two derived booleans the UI can consult to
gate buttons: ``paper_trading_recommended`` and
``live_trading_recommended``. The latter is **conservatively false**
unless the strategy has all of: a stop loss, a sufficient trust score,
a sufficient truth score, no overfitting flag, and no critical advice.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.advisor.constants import (
    HIGH_DRAWDOWN_ADVISORY_THRESHOLD,
    INDICATOR_OVERLOAD_THRESHOLD,
    LIVE_READY_TRUTH_SCORE,
    LOW_TRUST_SCORE_THRESHOLD,
    MOMENTUM_INDICATOR_TYPES,
    POOR_TRUTH_SCORE_THRESHOLD,
    TREND_INDICATOR_TYPES,
)
from app.strategy_engine.reliability.constants import (
    HIGH_WIN_RATE_WARNING_THRESHOLD,
)

if TYPE_CHECKING:
    from app.strategy_engine.backtest.runner import BacktestResult
    from app.strategy_engine.reliability.reliability_report import (
        ReliabilityReport,
    )
    from app.strategy_engine.schema.strategy import StrategyJSON
    from app.strategy_engine.truth.truth_score import TruthReport


class AdviceCategory(StrEnum):
    """Bucket for routing advice to the correct UI surface."""

    INDICATOR_SUGGESTION = "indicator_suggestion"
    INDICATOR_OVERLOAD = "indicator_overload"
    MISSING_STOP_LOSS = "missing_stop_loss"
    MISSING_EXIT = "missing_exit"
    HIGH_WIN_RATE_CAUTION = "high_win_rate_caution"
    LOW_TRUST_SCORE = "low_trust_score"
    POOR_TRUTH_SCORE = "poor_truth_score"
    OVERFITTING = "overfitting"
    HIGH_DRAWDOWN = "high_drawdown"
    PAPER_TRADING = "paper_trading"
    REGIME_MISMATCH = "regime_mismatch"
    LIVE_DEVIATION = "live_deviation"


class AdviceSeverity(StrEnum):
    """Severity scale for routing into UI affordances."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Advice(BaseModel):
    """One piece of advice — category + severity + human-readable text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: AdviceCategory
    severity: AdviceSeverity
    message: str = Field(..., min_length=1, max_length=512)


class AdvisorReport(BaseModel):
    """All advice plus paper / live recommendations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    advice: tuple[Advice, ...] = Field(default_factory=tuple)
    paper_trading_recommended: bool = True
    live_trading_recommended: bool = False


def generate_advice(
    *,
    strategy: StrategyJSON,
    backtest: BacktestResult | None = None,
    reliability: ReliabilityReport | None = None,
    truth: TruthReport | None = None,
    market_regime: str | None = None,
    deviation_report: dict[str, Any] | None = None,
) -> AdvisorReport:
    """Build an :class:`AdvisorReport` for ``strategy``.

    All optional inputs activate their corresponding rules. The function
    is pure: same inputs → same output.
    """
    advice: list[Advice] = []

    advice.extend(_indicator_rules(strategy))
    advice.extend(_exit_rules(strategy))

    if backtest is not None:
        advice.extend(_backtest_rules(backtest))

    if reliability is not None:
        advice.extend(_reliability_rules(reliability))

    if truth is not None:
        advice.extend(_truth_rules(truth))

    if market_regime is not None:
        advice.extend(_regime_rules(strategy, market_regime))

    if deviation_report is not None:
        advice.extend(_deviation_rules(deviation_report))

    paper_recommended, live_recommended = _recommendation_gates(
        strategy=strategy,
        truth=truth,
        reliability=reliability,
        advice=advice,
    )
    if not live_recommended:
        advice.append(
            Advice(
                category=AdviceCategory.PAPER_TRADING,
                severity=AdviceSeverity.INFO,
                message=(
                    "Paper trade this strategy first. Live capital deserves "
                    "evidence the edge survives real fills."
                ),
            )
        )

    return AdvisorReport(
        advice=tuple(advice),
        paper_trading_recommended=paper_recommended,
        live_trading_recommended=live_recommended,
    )


# ─── Rule implementations ──────────────────────────────────────────────


def _indicator_rules(strategy: StrategyJSON) -> list[Advice]:
    out: list[Advice] = []
    types = {ind.type for ind in strategy.indicators}

    only_trend = types and types.issubset(TREND_INDICATOR_TYPES)
    only_momentum = types and types.issubset(MOMENTUM_INDICATOR_TYPES)

    if only_trend:
        out.append(
            Advice(
                category=AdviceCategory.INDICATOR_SUGGESTION,
                severity=AdviceSeverity.INFO,
                message=(
                    "Only trend indicators are configured. Add RSI or MACD "
                    "for momentum confirmation."
                ),
            )
        )
    elif only_momentum:
        out.append(
            Advice(
                category=AdviceCategory.INDICATOR_SUGGESTION,
                severity=AdviceSeverity.INFO,
                message=(
                    "Only momentum indicators are configured. Add an EMA or "
                    "VWAP to anchor the trend direction."
                ),
            )
        )

    if len(strategy.indicators) > INDICATOR_OVERLOAD_THRESHOLD:
        out.append(
            Advice(
                category=AdviceCategory.INDICATOR_OVERLOAD,
                severity=AdviceSeverity.WARNING,
                message=(
                    f"{len(strategy.indicators)} indicators is more than "
                    f"the {INDICATOR_OVERLOAD_THRESHOLD}-indicator overload "
                    "threshold. Many indicators tend to over-fit and produce "
                    "conflicting signals."
                ),
            )
        )

    return out


def _exit_rules(strategy: StrategyJSON) -> list[Advice]:
    out: list[Advice] = []

    has_stop_loss = (
        strategy.exit.stop_loss_percent is not None
        or strategy.exit.trailing_stop_percent is not None
    )
    if not has_stop_loss:
        out.append(
            Advice(
                category=AdviceCategory.MISSING_STOP_LOSS,
                severity=AdviceSeverity.CRITICAL,
                message=(
                    "Stop loss is missing. Add a stopLossPercent or "
                    "trailingStopPercent before paper or live trading."
                ),
            )
        )

    # Phase 1's ExitRules._at_least_one_exit() makes a fully empty exit
    # block impossible — the advisor surfaces this defensively in case
    # a future schema relaxation removes that guard.
    if not _has_any_exit(strategy):
        out.append(
            Advice(
                category=AdviceCategory.MISSING_EXIT,
                severity=AdviceSeverity.CRITICAL,
                message=(
                    "No exit primitive configured. The engine cannot open a "
                    "position without a documented way out."
                ),
            )
        )

    return out


def _backtest_rules(backtest: BacktestResult) -> list[Advice]:
    out: list[Advice] = []

    if backtest.win_rate > HIGH_WIN_RATE_WARNING_THRESHOLD:
        out.append(
            Advice(
                category=AdviceCategory.HIGH_WIN_RATE_CAUTION,
                severity=AdviceSeverity.WARNING,
                message=(
                    f"{backtest.win_rate * 100:.0f} % win rate looks "
                    "attractive, but reliability and truth checks are "
                    "required before trusting it."
                ),
            )
        )

    if backtest.max_drawdown > HIGH_DRAWDOWN_ADVISORY_THRESHOLD:
        out.append(
            Advice(
                category=AdviceCategory.HIGH_DRAWDOWN,
                severity=AdviceSeverity.WARNING,
                message=(
                    f"Max drawdown {backtest.max_drawdown * 100:.1f} % is "
                    "high. Reduce position size or tighten the stop loss to "
                    "cap drawdown."
                ),
            )
        )

    return out


def _reliability_rules(reliability: ReliabilityReport) -> list[Advice]:
    out: list[Advice] = []
    score = reliability.trust_score.score
    if score < LOW_TRUST_SCORE_THRESHOLD:
        out.append(
            Advice(
                category=AdviceCategory.LOW_TRUST_SCORE,
                severity=AdviceSeverity.WARNING,
                message=(
                    f"Trust score {score} is below {LOW_TRUST_SCORE_THRESHOLD}. "
                    "Paper trade extensively before any live deployment."
                ),
            )
        )
    return out


def _truth_rules(truth: TruthReport) -> list[Advice]:
    out: list[Advice] = []

    if truth.truth_score < POOR_TRUTH_SCORE_THRESHOLD:
        out.append(
            Advice(
                category=AdviceCategory.POOR_TRUTH_SCORE,
                severity=AdviceSeverity.CRITICAL,
                message=(
                    f"Truth score {truth.truth_score} is below "
                    f"{POOR_TRUTH_SCORE_THRESHOLD}. Do not recommend live "
                    "trading until the underlying issues are resolved."
                ),
            )
        )

    if truth.overfitting_warnings:
        out.append(
            Advice(
                category=AdviceCategory.OVERFITTING,
                severity=AdviceSeverity.WARNING,
                message=(
                    "Overfitting indicators fired in the truth report. "
                    "Simplify the strategy or extend the training window."
                ),
            )
        )

    return out


def _regime_rules(strategy: StrategyJSON, market_regime: str) -> list[Advice]:
    """Cheap heuristic — flag pure-trend strategies in sideways regimes
    and pure-momentum strategies in trending regimes."""
    out: list[Advice] = []
    types = {ind.type for ind in strategy.indicators}
    regime = market_regime.lower()

    if regime == "sideways" and types.issubset(TREND_INDICATOR_TYPES):
        out.append(
            Advice(
                category=AdviceCategory.REGIME_MISMATCH,
                severity=AdviceSeverity.WARNING,
                message=(
                    "Trend-only strategy in a sideways market regime. "
                    "Consider a regime filter or pause this strategy."
                ),
            )
        )
    elif regime == "trending" and types.issubset(MOMENTUM_INDICATOR_TYPES):
        out.append(
            Advice(
                category=AdviceCategory.REGIME_MISMATCH,
                severity=AdviceSeverity.WARNING,
                message=(
                    "Momentum-only strategy in a strongly trending regime. "
                    "Add a trend anchor (EMA/VWAP) for confirmation."
                ),
            )
        )

    return out


def _deviation_rules(deviation_report: dict[str, Any]) -> list[Advice]:
    """The deviation report shape is owned by Phase 8 reconciliation —
    we just surface a generic warning when one is supplied with a
    truthy ``has_deviation`` flag."""
    out: list[Advice] = []
    if deviation_report.get("has_deviation"):
        out.append(
            Advice(
                category=AdviceCategory.LIVE_DEVIATION,
                severity=AdviceSeverity.WARNING,
                message=(
                    "Live execution deviated from the backtest. Review the "
                    "deviation report before scaling up size."
                ),
            )
        )
    return out


# ─── Recommendation gates ──────────────────────────────────────────────


def _recommendation_gates(
    *,
    strategy: StrategyJSON,
    truth: TruthReport | None,
    reliability: ReliabilityReport | None,
    advice: list[Advice],
) -> tuple[bool, bool]:
    """Decide paper / live recommendations. Live is conservatively gated."""
    has_critical = any(a.severity is AdviceSeverity.CRITICAL for a in advice)

    has_stop_loss = (
        strategy.exit.stop_loss_percent is not None
        or strategy.exit.trailing_stop_percent is not None
    )

    truth_ok = truth is not None and truth.truth_score >= LIVE_READY_TRUTH_SCORE
    trust_ok = (
        reliability is not None
        and reliability.trust_score.score >= LIVE_READY_TRUTH_SCORE
    )
    no_overfit = truth is not None and not truth.overfitting_warnings

    live_recommended = (
        has_stop_loss
        and truth_ok
        and trust_ok
        and no_overfit
        and not has_critical
    )
    paper_recommended = has_stop_loss and not has_critical

    return paper_recommended, live_recommended


# ─── Helpers ───────────────────────────────────────────────────────────


def _has_any_exit(strategy: StrategyJSON) -> bool:
    rules = strategy.exit
    return any(
        (
            rules.target_percent is not None,
            rules.stop_loss_percent is not None,
            rules.trailing_stop_percent is not None,
            bool(rules.partial_exits),
            rules.square_off_time is not None,
            bool(rules.indicator_exits),
            rules.reverse_signal_exit,
        )
    )


__all__ = [
    "Advice",
    "AdviceCategory",
    "AdviceSeverity",
    "AdvisorReport",
    "generate_advice",
]
